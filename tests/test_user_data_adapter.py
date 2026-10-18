"""可离线运行的接口检查，无需安装 Streamlit。"""
import io
from pathlib import Path
import unittest
from zipfile import ZIP_DEFLATED, ZipFile
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from user_data_adapter import load_run_folder, load_run_zip, normalize_tables, DataContractError


class TestUserAdapter(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stations = pd.read_csv(ROOT / "data/network_v1/stations.csv", encoding="utf-8-sig")
        cls.example = next((ROOT / "data/runs").iterdir())

    def test_old_csv_compatible(self):
        run = load_run_folder(self.example, self.stations)
        self.assertEqual(run.schema_kind, "user_legacy")
        self.assertEqual(len(run.passenger_results), 1190)
        self.assertEqual(run.station_state.time_min.max(), 180.0)
        self.assertTrue({"waiting_total", "waiting_forward", "waiting_reverse"} <= set(run.station_state))
        self.assertTrue({"segment_progress", "onboard"} <= set(run.vehicle_state))

    def test_in_memory_wrong_run_id_rejected(self):
        paths = ["od_flow.csv", "station_state.csv", "vehicle_state.csv", "passenger_results.csv"]
        tables = {n: pd.read_csv(self.example / n) for n in paths}
        tables["vehicle_state.csv"].loc[0, "run_id"] = "another_run"
        with self.assertRaises(DataContractError):
            normalize_tables(tables, self.stations, "mismatch")

    def test_zip_import_original_csv(self):
        stream = io.BytesIO()
        with ZipFile(stream, "w", ZIP_DEFLATED) as z:
            for name in ("od_flow.csv", "station_state.csv", "vehicle_state.csv", "passenger_results.csv"):
                z.write(self.example / name, arcname=name)
        run = load_run_zip(stream.getvalue(), self.stations)
        self.assertEqual(run.schema_kind, "user_legacy")


if __name__ == "__main__":
    unittest.main()
