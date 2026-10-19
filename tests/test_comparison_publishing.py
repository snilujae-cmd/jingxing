"""Actual three-policy calculations must survive publication to an isolated User."""
from copy import deepcopy
from io import BytesIO
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile, ZIP_DEFLATED

import pandas as pd

from comparison_data import (COMPARISON_NAME, ComparisonDataError, build_comparison,
                             decode_comparison, encode_comparison)
from core.exporter import csv_content, zip_content
from core.simulation import run_simulation
from shared_run_store import load_shared_bundle, load_shared_run, publish_result
from user_data_adapter import CSV_NAMES


ROOT = Path(__file__).resolve().parents[1]


class ComparisonPublishingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stations = pd.read_csv(ROOT / "data/network_v1/stations.csv", encoding="utf-8-sig")
        params = {"duration_min": 30, "arrival_rate": 120, "fleet": {"A": 2, "B": 1},
                  "speed_kmh": 15, "scenario_type": "上午高峰", "peak_multiplier": 2.0}
        cls.results = [run_simulation(params, strategy, seed=24)
                       for strategy in ("fixed", "dynamic", "optimized")]
        cls.selected = cls.results[-1]

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / "tests")
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "shared" / "current_run.zip"

    def publish(self, selected=None, results=None):
        with patch("shared_run_store.assert_admin"):
            return publish_result(selected or self.selected, self.path,
                                  comparison_results=results if results is not None else self.results)

    def replace_metadata(self, contents: bytes):
        with ZipFile(self.path) as archive:
            tables = {name: archive.read(name) for name in CSV_NAMES}
        with ZipFile(self.path, "w", ZIP_DEFLATED) as archive:
            for name, data in tables.items():
                archive.writestr(name, data)
            archive.writestr(COMPARISON_NAME, contents)

    def test_roundtrip_preserves_all_metrics_params_and_queue_series(self):
        self.publish()
        bundle = load_shared_bundle(self.stations, self.path)
        self.assertIsNone(bundle.comparison_error)
        self.assertEqual(bundle.run.run_id, self.selected["run_id"])
        metadata = bundle.comparison
        self.assertEqual(metadata["params"], self.selected["params"])
        self.assertEqual(metadata["seed"], self.selected["seed"])
        self.assertEqual(metadata["demand_signature"], self.selected["demand_signature"])
        self.assertEqual(metadata["selected_run_id"], self.selected["run_id"])
        for item, actual in zip(metadata["strategies"], self.results):
            self.assertEqual(item["strategy"], actual["strategy"])
            self.assertEqual(item["run_id"], actual["run_id"])
            self.assertEqual(item["metrics"], {key: actual[key] for key in item["metrics"]})
            frame = pd.DataFrame(actual["station_state"])
            expected = [{"time_min": float(t), "waiting_total": int(n)} for t, n in
                        frame.groupby("time_min")["queue_length"].sum().items()]
            self.assertEqual(item["queue_series"], expected)
        self.assertEqual(load_shared_run(self.stations, self.path).run_id, self.selected["run_id"])

    def test_four_csv_contents_are_byte_identical_with_metadata_added(self):
        self.publish()
        with ZipFile(self.path) as archive, ZipFile(BytesIO(zip_content(self.selected))) as original:
            self.assertEqual(set(archive.namelist()), set(CSV_NAMES) | {COMPARISON_NAME})
            for name in CSV_NAMES:
                self.assertEqual(archive.read(name), original.read(name))
                self.assertEqual(archive.read(name), csv_content(self.selected, name))

    def test_separate_process_can_read_published_comparison_without_admin_session(self):
        self.publish()
        script = (
            "import json,sys,pandas as pd; from pathlib import Path; "
            "from shared_run_store import load_shared_bundle; "
            "s=pd.read_csv('data/network_v1/stations.csv',encoding='utf-8-sig'); "
            "b=load_shared_bundle(s,Path(sys.argv[1])); "
            "print(json.dumps({'run_id':b.run.run_id,'comparison':b.comparison,'error':b.comparison_error}))"
        )
        environment = os.environ.copy()
        environment["PYTHONPATH"] = os.pathsep.join(str(path) for path in sys.path if path)
        execution = subprocess.run([sys.executable, "-c", script, str(self.path)], cwd=ROOT,
                                   env=environment, capture_output=True, text=True,
                                   timeout=45, check=True)
        isolated = json.loads(execution.stdout.strip())
        expected = load_shared_bundle(self.stations, self.path)
        self.assertEqual(isolated["run_id"], self.selected["run_id"])
        self.assertEqual(isolated["comparison"], expected.comparison)
        self.assertIsNone(isolated["error"])

    def test_mixed_parameters_seed_and_demand_cannot_replace_previous_publish(self):
        self.publish()
        original = self.path.read_bytes()
        for field in ("params", "seed", "demand_signature"):
            results = deepcopy(self.results)
            if field == "params":
                results[0][field]["arrival_rate"] += 1
            elif field == "seed":
                results[0][field] += 1
            else:
                results[0][field] = "different-demand"
            with self.subTest(field=field), self.assertRaises(ComparisonDataError):
                self.publish(results=results)
            self.assertEqual(self.path.read_bytes(), original)

    def test_duplicate_or_incomplete_strategies_and_foreign_selected_run_are_rejected(self):
        for results in (self.results[:2], [self.results[0], self.results[0], self.results[2]]):
            with self.assertRaises(ComparisonDataError):
                build_comparison(results, self.selected)
        foreign = deepcopy(self.selected)
        foreign["run_id"] = "another-run"
        with self.assertRaises(ComparisonDataError):
            build_comparison(self.results, foreign)
        altered = deepcopy(self.selected)
        altered["total_departures"] += 1
        with self.assertRaises(ComparisonDataError):
            build_comparison(self.results, altered)

    def test_invalid_or_nonfinite_metadata_is_not_displayed(self):
        self.publish()
        pristine = load_shared_bundle(self.stations, self.path).comparison
        for kind in ("schema", "nan", "count", "queue", "checksum"):
            metadata = deepcopy(pristine)
            if kind == "schema":
                metadata["schema_version"] = 999
            elif kind == "nan":
                metadata["strategies"][0]["metrics"]["avg_wait"] = float("nan")
            elif kind == "count":
                metadata["strategies"][0]["metrics"]["served"] = -1
            elif kind == "queue":
                metadata["strategies"][0]["queue_series"][1]["time_min"] = 0
            else:
                metadata["comparison_id"] = "cmp-invalid"
            with self.subTest(kind=kind):
                self.replace_metadata(json.dumps(metadata).encode("utf-8"))
                bundle = load_shared_bundle(self.stations, self.path)
                self.assertEqual(bundle.run.run_id, self.selected["run_id"])
                self.assertIsNone(bundle.comparison)
                self.assertTrue(bundle.comparison_error)

    def test_corrupt_or_cross_run_metadata_degrades_to_valid_single_run(self):
        self.publish()
        metadata = load_shared_bundle(self.stations, self.path).comparison
        for contents in (b"broken JSON", b"\xff\xfe", json.dumps({**metadata, "selected_run_id": "other"}).encode()):
            with self.subTest(contents=contents[:20]):
                self.replace_metadata(contents)
                bundle = load_shared_bundle(self.stations, self.path)
                self.assertIsNotNone(bundle.run)
                self.assertIsNone(bundle.comparison)
                self.assertTrue(bundle.comparison_error)

    def test_unreadable_optional_metadata_degrades_without_hiding_csv_errors(self):
        self.publish()
        original_read = ZipFile.read
        for failure in (RuntimeError("encrypted comparison"), NotImplementedError("compression method")):
            def read_optional(archive, name, *args, **kwargs):
                filename = getattr(name, "filename", name)
                if filename == COMPARISON_NAME:
                    raise failure
                return original_read(archive, name, *args, **kwargs)
            with self.subTest(failure=type(failure).__name__), patch.object(ZipFile, "read", read_optional):
                bundle = load_shared_bundle(self.stations, self.path)
                self.assertEqual(bundle.run.run_id, self.selected["run_id"])
                self.assertIsNone(bundle.comparison)
                self.assertTrue(bundle.comparison_error)

    def test_changed_selected_csv_queue_is_not_attached_to_comparison(self):
        self.publish()
        metadata = load_shared_bundle(self.stations, self.path).comparison
        modified = deepcopy(self.selected)
        modified["station_state"][0]["queue_length"] += 1
        self.path.write_bytes(zip_content(modified))
        self.replace_metadata(encode_comparison(metadata))
        bundle = load_shared_bundle(self.stations, self.path)
        self.assertIsNotNone(bundle.run)
        self.assertIsNone(bundle.comparison)
        self.assertIn("站点记录", bundle.comparison_error)

    def test_changed_csv_wait_or_board_time_cannot_keep_stale_comparison_metrics(self):
        self.publish()
        metadata = load_shared_bundle(self.stations, self.path).comparison
        for field in ("wait_min", "board_time_min", "arrival_time_min"):
            modified = deepcopy(self.selected)
            boarded = next(row for row in modified["passenger_results"] if row["board_time_min"] is not None)
            boarded[field] += 1.0
            with self.subTest(field=field):
                self.path.write_bytes(zip_content(modified))
                self.replace_metadata(encode_comparison(metadata))
                bundle = load_shared_bundle(self.stations, self.path)
                self.assertIsNotNone(bundle.run)
                self.assertIsNone(bundle.comparison)
                self.assertIn("候车", bundle.comparison_error)

    def test_consistently_changed_csv_wait_and_board_time_are_detected_by_metric_recalculation(self):
        self.publish()
        metadata = load_shared_bundle(self.stations, self.path).comparison
        modified = deepcopy(self.selected)
        boarded = next(row for row in modified["passenger_results"] if row["board_time_min"] is not None)
        boarded["wait_min"] += 2.0
        boarded["board_time_min"] += 2.0
        self.path.write_bytes(zip_content(modified))
        self.replace_metadata(encode_comparison(metadata))
        bundle = load_shared_bundle(self.stations, self.path)
        self.assertIsNotNone(bundle.run)
        self.assertIsNone(bundle.comparison)
        self.assertIn("候车", bundle.comparison_error)

    def test_following_single_run_removes_stale_comparison(self):
        self.publish()
        self.assertIsNotNone(load_shared_bundle(self.stations, self.path).comparison)
        with patch("shared_run_store.assert_admin"):
            publish_result(self.results[0], self.path)
        bundle = load_shared_bundle(self.stations, self.path)
        self.assertEqual(bundle.run.run_id, self.results[0]["run_id"])
        self.assertIsNone(bundle.comparison)
        self.assertIsNone(bundle.comparison_error)
        with ZipFile(self.path) as archive:
            self.assertEqual(set(archive.namelist()), set(CSV_NAMES))

    def test_atomic_replace_failure_keeps_previous_archive_and_removes_temp_file(self):
        self.publish()
        previous = self.path.read_bytes()
        with patch("shared_run_store.os.replace", side_effect=OSError("read-only storage")):
            with self.assertRaises(OSError):
                self.publish(selected=self.results[0])
        self.assertEqual(self.path.read_bytes(), previous)
        self.assertEqual([p.name for p in self.path.parent.iterdir()], [self.path.name])

    def test_unauthorized_comparison_publish_fails_before_export_or_creating_directory(self):
        with patch("shared_run_store.assert_admin", side_effect=PermissionError("unauthorized")), \
                patch("shared_run_store.zip_content") as export:
            with self.assertRaises(PermissionError):
                publish_result(self.selected, self.path, self.results)
        export.assert_not_called()
        self.assertFalse(self.path.parent.exists())

    def test_metadata_is_detached_and_deterministic_for_identical_inputs(self):
        results = deepcopy(self.results)
        first = build_comparison(results, results[-1])
        second = build_comparison(results, results[-1])
        self.assertEqual(first["comparison_id"], second["comparison_id"])
        self.assertEqual(decode_comparison(encode_comparison(first), self.selected["run_id"]), first)
        results[0]["params"]["fleet"]["A"] += 1
        self.assertNotEqual(first["params"], results[0]["params"])

    def test_missing_publish_has_no_run_or_comparison(self):
        bundle = load_shared_bundle(self.stations, self.path)
        self.assertIsNone(bundle.run)
        self.assertIsNone(bundle.comparison)
        self.assertIsNone(bundle.comparison_error)


if __name__ == "__main__":
    unittest.main()
