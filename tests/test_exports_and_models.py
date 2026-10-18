"""修复版回归测试：输出守恒、共享站点、数据格式、异常参数与场景效果。"""
import csv
import io
import unittest
import zipfile
from core.exporter import SCHEMAS, csv_content, zip_content
from core.demand import demand_multiplier
from core.simulation import PHYSICAL_IDS, run_simulation

BASE = {"duration_min": 90, "arrival_rate": 120, "fleet": {"A": 3, "B": 2},
        "speed_kmh": 15, "scenario_type": "上午高峰", "peak_multiplier": 2}

class ContractTests(unittest.TestCase):
    def test_same_seed_is_reproducible_and_different_strategies_share_demand(self):
        a = run_simulation(BASE, "fixed", seed=24)
        b = run_simulation(BASE, "fixed", seed=24)
        c = run_simulation(BASE, "optimized", seed=24)
        self.assertEqual(a, b)
        self.assertEqual(a["demand_signature"], c["demand_signature"])
        self.assertNotEqual(a["run_id"], c["run_id"])

    def test_passenger_conservation_and_od(self):
        r = run_simulation(BASE, "optimized", seed=55)
        self.assertEqual(sum(row["passengers"] for row in r["od_flow"]), r["total_arrivals"])
        self.assertEqual(r["served"] + r["unserved"], r["total_arrivals"])
        self.assertEqual(r["served"], r["completed"] + r["onboard_end"])
        counts = {}
        for x in r["passenger_results"]:
            counts[x["status"]] = counts.get(x["status"], 0) + 1
        self.assertEqual(counts.get("completed", 0), r["completed"])
        self.assertEqual(counts.get("waiting", 0), r["unserved"])
        self.assertEqual(counts.get("onboard", 0), r["onboard_end"])
        self.assertEqual(len(r["passenger_results"]), r["total_arrivals"])
        self.assertTrue(all(x["board_time_min"] is None or
                            x["board_time_min"] >= x["arrival_time_min"]
                            for x in r["passenger_results"]))

    def test_csv_schemas_round_trip_and_shared_station_mapping(self):
        self.assertEqual(PHYSICAL_IDS["A2"], PHYSICAL_IDS["B1"])
        self.assertEqual(PHYSICAL_IDS["A3"], PHYSICAL_IDS["B2"])
        r = run_simulation(BASE, "dynamic", seed=66)
        archive = zipfile.ZipFile(io.BytesIO(zip_content(r)))
        self.assertCountEqual(archive.namelist(), SCHEMAS)
        for name, header in SCHEMAS.items():
            rows = list(csv.DictReader(io.StringIO(archive.read(name).decode("utf-8-sig"))))
            self.assertTrue(rows or name == "od_flow.csv")
            self.assertEqual(list(rows[0]) if rows else archive.read(name).decode("utf-8-sig").strip().split(','), header)
            self.assertEqual(archive.read(name), csv_content(r, name))
            self.assertTrue(all(row["run_id"] == r["run_id"] for row in rows))

    def test_unsupported_strategy_and_broken_parameters_raise_errors(self):
        with self.assertRaises(ValueError):
            run_simulation(BASE, "guess")
        with self.assertRaises(ValueError):
            run_simulation({**BASE, "speed_kmh": 21})
        with self.assertRaises(ValueError):
            run_simulation({**BASE, "fleet": {"A": 2, "B": 0},
                            "vehicle_capacities": {"A": [36], "B": []}})

    def test_disruption_and_tidal_switch_change_demand_signature(self):
        p1 = run_simulation(BASE, "fixed", seed=42)
        p2 = run_simulation({**BASE, "disruption": True, "disruption_type": "客流突增",
                             "disruption_intensity": 3.0, "disruption_center": 35}, "fixed", seed=42)
        self.assertNotEqual(p1["demand_signature"], p2["demand_signature"])
        p3 = run_simulation({**BASE, "tidal": True}, "fixed", seed=42)
        self.assertNotEqual(p1["demand_signature"], p3["demand_signature"])

    def test_disruption_drop_actually_drops_arrivals(self):
        p = {"duration_min": 120, "scenario_type": "平峰",
             "disruption": True, "disruption_type": "客流骤降",
             "disruption_intensity": 2, "disruption_center": 60,
             "disruption_sigma": 10}
        self.assertAlmostEqual(demand_multiplier(60, p), 0.5)
        self.assertGreater(demand_multiplier(0, p), demand_multiplier(60, p))

    def test_route_occupancy_limit_and_no_teleport(self):
        r = run_simulation(BASE, "optimized", seed=14)
        self.assertTrue(all(0 <= x["load"] <= x["capacity"] for x in r["vehicle_state"]))
        # 调度日志的方向与当前线路端点一致：车辆不能凭空调往另一条线路。
        self.assertTrue(all(x["vehicle_id"].startswith(x["route"] + "-")
                            for x in r["dispatch_log"]))

if __name__ == "__main__":
    unittest.main()
