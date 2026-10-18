"""滚动优化 + 可调车队：正确性与复现性测试。"""
import unittest
from collections import deque

from core.optimizer import propose_departures
from core.simulation import run_simulation, Station, Vehicle
from data.routes import ROUTES
from data.stations import STATIONS

BASE = {
    'duration_min': 120, 'arrival_rate': 160, 'fleet': {'A': 4, 'B': 3},
    'speed_kmh': 15, 'scenario_type': '上午高峰', 'peak_multiplier': 2.0,
    'fixed_interval': 17, 'queue_threshold': 20,
    'prediction_horizon_min': 30, 'decision_interval_min': 5, 'beam_width': 4,
}


class OptimizedSimulationTests(unittest.TestCase):
    def check(self, r):
        self.assertEqual(r['total_arrivals'], r['served'] + r['unserved'])
        self.assertEqual(r['served'], r['completed'] + r['onboard_end'])
        self.assertGreaterEqual(r['total_wait_person_min'], 0.0)
        self.assertTrue(0 <= r['service_rate'] <= 1)
        self.assertEqual(r['total_departures'], len(r['dispatch_log']))
        fleet = r['params']['fleet']
        for item in r['dispatch_log']:
            self.assertTrue(item['vehicle_id'].startswith(item['route']))
            self.assertLessEqual(int(item['vehicle_id'].split('-')[-1]), fleet[item['route']])

    def test_three_policies_fair_input(self):
        results = [run_simulation(BASE, strategy=s, seed=42)
                   for s in ('fixed', 'dynamic', 'optimized')]
        self.assertEqual(len({r['demand_signature'] for r in results}), 1)
        for r in results:
            self.check(r)
            self.assertEqual(r['params']['fleet'], BASE['fleet'])
        self.assertGreater(results[-1]['total_departures'], 0)

    def test_scalable_fleet(self):
        for fleet in ({'A': 1, 'B': 1}, {'A': 5, 'B': 3}, {'A': 12, 'B': 6}):
            r = run_simulation({**BASE, 'duration_min': 80, 'fleet': fleet}, 'optimized', seed=5)
            self.check(r)
            self.assertEqual(r['params']['fleet'], fleet)

    def test_zero_vehicle_no_ghost_service(self):
        r = run_simulation({**BASE, 'fleet': {'A': 0, 'B': 0}}, 'optimized', seed=42)
        self.check(r)
        self.assertEqual(r['served'], 0)
        self.assertEqual(r['total_departures'], 0)
        self.assertEqual(r['unserved'], r['total_arrivals'])

    def test_zero_arrivals_no_dispatch(self):
        r = run_simulation({**BASE, 'arrival_rate': 0}, 'optimized', seed=42)
        self.check(r)
        self.assertEqual(r['total_departures'], 0)
        self.assertEqual(r['total_wait_person_min'], 0.0)

    def test_optimized_repeatable(self):
        p = {**BASE, 'duration_min': 65}
        self.assertEqual(run_simulation(p, 'optimized', seed=50),
                         run_simulation(p, 'optimized', seed=50))

    def test_forecast_never_reads_future_passenger_events(self):
        # 直接对规划器传入未发生的客流事件；不能影响当前发车决策。
        stations = {sid: Station(sid, s['name']) for sid, s in STATIONS.items()}
        from core.simulation import Passenger
        for _ in range(30):
            stations['A0'].add(Passenger(-1.0, 4), 1)
        vehicles = [Vehicle('A-01', 'A', 36, 0), Vehicle('B-01', 'B', 36, 0)]
        last = {(rid, d): -float('inf') for rid in ROUTES for d in (1, -1)}
        params = {**BASE, 'fleet': {'A': 1, 'B': 1}}
        keyword = dict(now=0.0, stations=stations, vehicles=vehicles,
                       last_departure=last, params=params, route_weights={'A': 0.6, 'B': 0.4})
        a = propose_departures(events=[], **keyword)
        b = propose_departures(events=[(10.0, 999, 'arrival', ('A0', 1, None))], **keyword)
        self.assertEqual(a, b)


if __name__ == '__main__':
    unittest.main()
