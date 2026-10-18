"""The published result must be readable from a separate session/process."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from core.simulation import run_simulation
from shared_run_store import load_shared_run, publish_result


ROOT = Path(__file__).resolve().parents[1]


class SharedRunStoreTests(unittest.TestCase):
    def test_latest_run_is_complete_and_replaced(self):
        stations = pd.read_csv(ROOT / "data/network_v1/stations.csv", encoding="utf-8-sig")
        params = {"duration_min": 30, "arrival_rate": 120,
                  "fleet": {"A": 2, "B": 1}, "speed_kmh": 15}
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as temp:
            path = Path(temp) / "latest.zip"
            self.assertIsNone(load_shared_run(stations, path))
            first = run_simulation(params, "fixed", seed=1)
            second = run_simulation(params, "fixed", seed=2)
            with patch("shared_run_store.assert_admin") as authorization:
                publish_result(first, path)
                self.assertEqual(load_shared_run(stations, path).run_id, first["run_id"])
                publish_result(second, path)
                self.assertEqual(load_shared_run(stations, path).run_id, second["run_id"])
            self.assertEqual(authorization.call_count, 2)


if __name__ == "__main__":
    unittest.main()
