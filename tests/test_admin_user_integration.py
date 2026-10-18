"""Check the real Admin simulation result against the User data contract."""

import unittest
from pathlib import Path

import pandas as pd

from core.exporter import zip_content
from core.simulation import run_simulation
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


if __name__ == "__main__":
    unittest.main()
