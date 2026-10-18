"""Check one Admin simulation through export, isolated publish, and User loading."""

from io import BytesIO
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

import numpy as np
import pandas as pd

from core.exporter import zip_content
from core.simulation import run_simulation
from shared_run_store import load_shared_run, publish_result
from user_data_adapter import load_admin_result, load_run_zip


ROOT = Path(__file__).resolve().parents[1]


class AdminUserIntegrationTests(unittest.TestCase):
    def test_admin_result_loads_in_user_from_memory_and_zip(self):
        params = {
            "duration_min": 90,
            "arrival_rate": 120,
            "fleet": {"A": 3, "B": 2},
            "speed_kmh": 15,
            "scenario_type": "上午高峰",
            "peak_multiplier": 2,
        }
        result = run_simulation(params, "fixed", seed=24)
        stations = pd.read_csv(ROOT / "data/network_v1/stations.csv", encoding="utf-8-sig")
        memory = load_admin_result(result, stations)
        archive = load_run_zip(zip_content(result), stations)

        self.assertEqual(memory.run_id, result["run_id"])
        self.assertEqual(archive.run_id, result["run_id"])
        self.assertEqual(memory.schema_kind, "admin_v1")
        self.assertEqual(len(memory.passenger_results), result["total_arrivals"])
        self.assertSetEqual(set(memory.station_state["station_id"]),
                            set(archive.station_state["station_id"]))
        self.assertTrue(set(memory.station_state["station_id"]).issubset(
            set(stations["station_id"])))
        self.assertTrue(memory.station_state["station_name"].notna().all())

    def test_isolated_publish_preserves_records_and_recomputed_metrics(self):
        params = {
            "duration_min": 90,
            "arrival_rate": 120,
            "fleet": {"A": 3, "B": 2},
            "speed_kmh": 15,
            "scenario_type": "上午高峰",
            "peak_multiplier": 2,
        }
        result = run_simulation(params, "fixed", seed=24)
        stations = pd.read_csv(ROOT / "data/network_v1/stations.csv", encoding="utf-8-sig")
        exported = zip_content(result)

        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as temp_dir:
            isolated_path = Path(temp_dir) / "current_run.zip"
            with patch("shared_run_store.assert_admin"):
                publish_result(result, isolated_path)
            shared = load_shared_run(stations, isolated_path)
            downloaded = load_run_zip(exported, stations)
            with ZipFile(BytesIO(exported)) as export_zip, ZipFile(isolated_path) as shared_zip:
                expected_names = {"od_flow.csv", "station_state.csv",
                                  "vehicle_state.csv", "passenger_results.csv"}
                self.assertEqual(set(export_zip.namelist()), expected_names)
                self.assertEqual(set(shared_zip.namelist()), expected_names)
                for name in expected_names:
                    # ZIP timestamps may differ; the CSV data must be identical.
                    self.assertEqual(export_zip.read(name), shared_zip.read(name))
                    table = pd.read_csv(BytesIO(shared_zip.read(name)), encoding="utf-8-sig")
                    self.assertEqual(set(table["run_id"]), {result["run_id"]})

        self.assertIsNotNone(shared)
        self.assertEqual(shared.run_id, result["run_id"])
        self.assertEqual(downloaded.run_id, result["run_id"])
        self.assertEqual(shared.schema_kind, "admin_v1")

        # A User session sees the same vehicle snapshot fields, with load renamed.
        raw_vehicle = pd.DataFrame(result["vehicle_state"])
        vehicle = shared.vehicle_state
        for raw_name, user_name in [
            ("time_min", "time_min"), ("vehicle_id", "vehicle_id"),
            ("route_id", "route_id"), ("station_id", "station_id"),
            ("status", "status"), ("load", "onboard"),
            ("capacity", "capacity"),
        ]:
            self.assertEqual(raw_vehicle[raw_name].tolist(), vehicle[user_name].tolist())
        self.assertEqual(vehicle["direction"].tolist(),
                         raw_vehicle["direction"].map({1: "去程", -1: "返程"}).tolist())
        pd.testing.assert_frame_equal(vehicle, downloaded.vehicle_state)

        # Admin has one row per direction; User combines both at each route stop.
        keys = ["run_id", "time_min", "route_id", "station_id", "route_station_seq"]
        raw_station = pd.DataFrame(result["station_state"])
        queue = raw_station.pivot_table(index=keys, columns="direction",
                                        values="queue_length", aggfunc="sum", fill_value=0)
        queue = queue.rename(columns={1: "waiting_forward", -1: "waiting_reverse"}).reset_index()
        station = shared.station_state.merge(queue, on=keys, validate="one_to_one",
                                             suffixes=("", "_raw"), indicator=True)
        self.assertEqual(len(station), len(shared.station_state))
        self.assertTrue(station["_merge"].eq("both").all())
        for direction in ("waiting_forward", "waiting_reverse"):
            self.assertEqual(station[direction].tolist(), station[f"{direction}_raw"].tolist())
        self.assertEqual(shared.station_state["waiting_total"].tolist(),
                         (shared.station_state["waiting_forward"] +
                          shared.station_state["waiting_reverse"]).tolist())
        pd.testing.assert_frame_equal(shared.station_state, downloaded.station_state)

        # The shared passenger event rows, not snapshot estimates, reproduce metrics.
        raw_passenger = pd.DataFrame(result["passenger_results"])
        passenger = shared.passenger_results
        self.assertEqual(raw_passenger["passenger_id"].tolist(), passenger["passenger_id"].tolist())
        self.assertEqual(raw_passenger["status"].tolist(), passenger["status"].tolist())
        self.assertEqual(raw_passenger["origin_station_id"].tolist(),
                         passenger["origin_station_id"].tolist())
        for raw_name, user_name in [
            ("arrival_time_min", "arrival_time_min"),
            ("board_time_min", "boarding_time_min"),
            ("alight_time_min", "alighting_time_min"),
            ("wait_min", "wait_time_min"),
        ]:
            np.testing.assert_allclose(raw_passenger[raw_name].to_numpy(dtype=float),
                                       passenger[user_name].to_numpy(dtype=float),
                                       rtol=0, atol=1e-5, equal_nan=True)
        pd.testing.assert_frame_equal(passenger, downloaded.passenger_results)

        boarded = passenger["boarding_time_min"].notna()
        waits = passenger.loc[boarded, "wait_time_min"].to_numpy(dtype=float)
        self.assertEqual(len(passenger), result["total_arrivals"])
        self.assertEqual(int(boarded.sum()), result["served"])
        self.assertEqual(int(passenger["alighting_time_min"].notna().sum()), result["completed"])
        self.assertEqual(int(passenger["status"].eq("waiting").sum()), result["unserved"])
        self.assertEqual(int(passenger["status"].eq("onboard").sum()), result["onboard_end"])
        self.assertEqual(int(shared.od_flow["demand_count"].sum()), result["total_arrivals"])
        self.assertAlmostEqual(float(waits.mean()), result["avg_wait"], places=4)
        self.assertAlmostEqual(float(np.percentile(waits, 95)), result["p95_wait"], places=4)
        self.assertAlmostEqual(float((waits > 15).mean()), result["over_ratio"], places=4)
        self.assertAlmostEqual(float(boarded.mean()), result["service_rate"], places=6)
        observed = passenger["boarding_time_min"].fillna(params["duration_min"])
        observed_wait = (observed - passenger["arrival_time_min"]).mean()
        self.assertAlmostEqual(float(observed_wait), result["avg_observed_wait_all"], places=4)

        last_t = params["duration_min"]
        self.assertEqual(int(shared.station_state.loc[
            shared.station_state["time_min"].eq(last_t), "waiting_total"].sum()), result["unserved"])
        self.assertEqual(int(vehicle.loc[vehicle["time_min"].eq(last_t), "onboard"].sum()),
                         result["onboard_end"])


if __name__ == "__main__":
    unittest.main()
