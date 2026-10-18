"""Direct route comparison must use exact, complete simulation records only."""

from pathlib import Path
import sys
import unittest

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from route_recommendation import recommend_direct_routes
from user_data_adapter import RunData


class RouteRecommendationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stop_order = pd.read_csv(ROOT / "data/network_v1/route_stop_order.csv")

    def _run(self, people):
        return RunData(
            run_id="TEST", od_flow=pd.DataFrame(), station_state=pd.DataFrame(),
            vehicle_state=pd.DataFrame(), passenger_results=pd.DataFrame(people),
            schema_kind="admin_v1", source_label="测试仿真",
        )

    def test_exact_od_and_complete_future_trip_only(self):
        run = self._run([
            # Attractive but wrong OD, direction, or incomplete records must not enter comparison.
            {"passenger_id": "wrong-destination", "route_id": "A", "origin_station_id": "N03",
             "destination_station_id": "N04", "direction": 1, "boarding_time_min": 10.5,
             "alighting_time_min": 12},
            {"passenger_id": "wrong-direction", "route_id": "A", "origin_station_id": "N03",
             "destination_station_id": "N05", "direction": -1, "boarding_time_min": 11,
             "alighting_time_min": 14},
            {"passenger_id": "at-replay", "route_id": "A", "origin_station_id": "N03",
             "destination_station_id": "N05", "direction": 1, "boarding_time_min": 10,
             "alighting_time_min": 16},
            {"passenger_id": "not-alighted", "route_id": "B", "origin_station_id": "N03",
             "destination_station_id": "N05", "direction": 1, "boarding_time_min": 11,
             "alighting_time_min": None},
            {"passenger_id": "reversed-times", "route_id": "B", "origin_station_id": "N03",
             "destination_station_id": "N05", "direction": 1, "boarding_time_min": 12,
             "alighting_time_min": 11},
            {"passenger_id": "a-observed", "route_id": "A", "origin_station_id": "N03",
             "destination_station_id": "N05", "direction": 1, "boarding_time_min": 12,
             "alighting_time_min": 30},
            {"passenger_id": "b-observed", "route_id": "B", "origin_station_id": "N03",
             "destination_station_id": "N05", "direction": "去程", "boarding_time_min": 14,
             "alighting_time_min": 22},
            {"passenger_id": "b-later", "route_id": "B", "origin_station_id": "N03",
             "destination_station_id": "N05", "direction": 1, "boarding_time_min": 15,
             "alighting_time_min": 19},
        ])

        options = recommend_direct_routes(self.stop_order, run, "N03", "N05", 10)

        self.assertEqual([item["route_id"] for item in options], ["B", "A"])
        self.assertEqual(options[0]["direction"], "去程")
        self.assertEqual(options[0]["observed_passenger_id"], "b-observed")
        self.assertEqual(options[0]["replay_wait_min"], 4)
        self.assertEqual(options[0]["ride_time_min"], 8)
        self.assertEqual(options[0]["total_replay_min"], 12)
        self.assertEqual(options[1]["observed_passenger_id"], "a-observed")
        self.assertEqual(options[1]["total_replay_min"], 20)

    def test_unobserved_route_remains_without_numeric_estimate(self):
        run = self._run([
            {"passenger_id": "b-only", "route_id": "B", "origin_station_id": "N03",
             "destination_station_id": "N05", "direction": 1,
             "boarding_time_min": 18, "alighting_time_min": 25},
        ])
        options = recommend_direct_routes(self.stop_order, run, "N03", "N05", 15)

        self.assertEqual([item["route_id"] for item in options], ["B", "A"])
        self.assertEqual(options[0]["total_replay_min"], 10)
        for field in ("boarding_time_min", "alighting_time_min", "replay_wait_min",
                      "ride_time_min", "total_replay_min", "observed_passenger_id"):
            self.assertIsNone(options[1][field])

    def test_reverse_direction_uses_station_order(self):
        run = self._run([
            {"passenger_id": "reverse", "route_id": "B", "origin_station_id": "N05",
             "destination_station_id": "N03", "direction": -1,
             "boarding_time_min": 20, "alighting_time_min": 27},
            {"passenger_id": "wrong-direction", "route_id": "A", "origin_station_id": "N05",
             "destination_station_id": "N03", "direction": 1,
             "boarding_time_min": 19, "alighting_time_min": 25},
        ])
        options = recommend_direct_routes(self.stop_order, run, "N05", "N03", 15)

        self.assertEqual([item["route_id"] for item in options], ["B", "A"])
        self.assertTrue(all(item["direction"] == "返程" for item in options))
        self.assertEqual(options[0]["replay_wait_min"], 5)
        self.assertEqual(options[0]["ride_time_min"], 7)
        self.assertIsNone(options[1]["total_replay_min"])

    def test_no_direct_route_or_same_station(self):
        run = self._run([])
        self.assertEqual(recommend_direct_routes(self.stop_order, run, "N01", "N06", 0), [])
        self.assertEqual(recommend_direct_routes(self.stop_order, run, "N03", "N03", 0), [])

    def test_replay_time_must_be_finite(self):
        run = self._run([])
        with self.assertRaises(ValueError):
            recommend_direct_routes(self.stop_order, run, "N03", "N05", float("nan"))


if __name__ == "__main__":
    unittest.main()
