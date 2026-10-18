"""The Admin editor, preview and simulator share one saved scenario contract."""

import unittest

from core.simulation import run_simulation
from scenario_state import (default_scenario, load_scenario, save_scenario,
                            simulation_scenario_params)


class ScenarioStateTests(unittest.TestCase):
    def test_saved_scenario_is_the_one_used_by_simulation(self):
        state = {}
        edited = default_scenario()
        edited.update({
            "type": "下午高峰",
            "arrival_rate": 230,
            "duration_min": 90,
            "seed": 73,
            "tidal": True,
            "disruption": True,
            "disruption_type": "客流骤降",
            "disruption_center": 45,
            "disruption_sigma": 20,
            "disruption_intensity": 2.5,
        })
        save_scenario(state, edited)
        edited["arrival_rate"] = 600
        saved = load_scenario(state)
        self.assertIsNotNone(saved)
        self.assertEqual(saved["arrival_rate"], 230)
        params = simulation_scenario_params(saved)
        self.assertEqual(params, {
            "duration_min": 90,
            "arrival_rate": 230,
            "scenario_type": "下午高峰",
            "peak_multiplier": 2.0,
            "tidal": True,
            "disruption": True,
            "disruption_type": "客流骤降",
            "disruption_center": 45,
            "disruption_sigma": 20,
            "disruption_intensity": 2.5,
        })
        result = run_simulation({**params, "fleet": {"A": 2, "B": 1}},
                                strategy="fixed", seed=saved["seed"])
        self.assertEqual(result["seed"], 73)
        self.assertEqual(result["scenario_type"], "下午高峰")
        for key, value in params.items():
            self.assertEqual(result["params"][key], value)

    def test_missing_or_invalid_scenario_cannot_be_loaded(self):
        state = {}
        self.assertIsNone(load_scenario(state))
        with self.assertRaises(ValueError):
            save_scenario(state, {"type": "平峰"})
        self.assertNotIn("scenario", state)
        state["scenario"] = {**default_scenario(), "arrival_rate": -1}
        self.assertIsNone(load_scenario(state))

    def test_loaded_scenario_is_detached_from_saved_snapshot(self):
        state = {}
        save_scenario(state, default_scenario())
        loaded = load_scenario(state)
        loaded["seed"] = 9999
        self.assertEqual(state["scenario"]["seed"], 42)


if __name__ == "__main__":
    unittest.main()
