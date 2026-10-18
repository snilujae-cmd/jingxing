"""One validated scenario contract for the Admin editor and simulator."""

from __future__ import annotations

import math
from collections.abc import Mapping, MutableMapping
from numbers import Integral, Real


SCENARIO_KEY = "scenario"
SCENARIO_TYPES = ("平峰", "上午高峰", "下午高峰")
DISRUPTION_TYPES = ("客流突增", "客流骤降", "双向高峰")

_DEFAULT_SCENARIO = {
    "type": "平峰",
    "arrival_rate": 120,
    "duration_min": 600,
    "seed": 42,
    "tidal": False,
    "disruption": False,
    "disruption_type": "客流突增",
    "disruption_center": 300,
    "disruption_sigma": 30,
    "disruption_intensity": 2.0,
}


def default_scenario() -> dict:
    return dict(_DEFAULT_SCENARIO)


def _integer(value: object, name: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise ValueError(f"{name}必须是整数")
    number = int(value)
    if not minimum <= number <= maximum:
        raise ValueError(f"{name}超出允许范围")
    return number


def validate_scenario(candidate: Mapping) -> dict:
    """Return a detached, complete scenario or reject invalid saved data."""
    if not isinstance(candidate, Mapping):
        raise ValueError("客流场景格式无效")
    try:
        scenario_type = candidate["type"]
        disruption_type = candidate["disruption_type"]
        tidal = candidate["tidal"]
        disruption = candidate["disruption"]
        intensity = candidate["disruption_intensity"]
        duration = _integer(candidate["duration_min"], "仿真时长", 60, 720)
        scenario = {
            "type": scenario_type,
            "arrival_rate": _integer(candidate["arrival_rate"], "基准到达率", 30, 600),
            "duration_min": duration,
            "seed": _integer(candidate["seed"], "随机种子", 0, 9999),
            "tidal": tidal,
            "disruption": disruption,
            "disruption_type": disruption_type,
            "disruption_center": _integer(candidate["disruption_center"], "触发时刻", 0, duration),
            "disruption_sigma": _integer(candidate["disruption_sigma"], "持续宽度", 5, 180),
        }
    except KeyError as exc:
        raise ValueError(f"客流场景缺少字段：{exc.args[0]}") from exc
    if scenario_type not in SCENARIO_TYPES:
        raise ValueError("客流模式无效")
    if disruption_type not in DISRUPTION_TYPES:
        raise ValueError("突发类型无效")
    if not isinstance(tidal, bool) or not isinstance(disruption, bool):
        raise ValueError("客流开关无效")
    if isinstance(intensity, bool) or not isinstance(intensity, Real):
        raise ValueError("突发影响强度无效")
    intensity = float(intensity)
    if not math.isfinite(intensity) or not 1.0 <= intensity <= 5.0:
        raise ValueError("突发影响强度超出允许范围")
    scenario["disruption_intensity"] = intensity
    return scenario


def save_scenario(state: MutableMapping, candidate: Mapping) -> dict:
    """Commit one valid snapshot; never leave a partially edited dict saved."""
    scenario = validate_scenario(candidate)
    state[SCENARIO_KEY] = scenario
    return dict(scenario)


def load_scenario(state: Mapping) -> dict | None:
    """Read the same saved snapshot used by the editor and dispatch page."""
    candidate = state.get(SCENARIO_KEY)
    if candidate is None:
        return None
    try:
        return validate_scenario(candidate)
    except ValueError:
        return None


def simulation_scenario_params(scenario: Mapping) -> dict:
    """Map the validated saved scenario to simulation engine parameters."""
    saved = validate_scenario(scenario)
    return {
        "duration_min": saved["duration_min"],
        "arrival_rate": saved["arrival_rate"],
        "scenario_type": saved["type"],
        "peak_multiplier": 2.0,
        "tidal": saved["tidal"],
        "disruption": saved["disruption"],
        "disruption_type": saved["disruption_type"],
        "disruption_center": saved["disruption_center"],
        "disruption_sigma": saved["disruption_sigma"],
        "disruption_intensity": saved["disruption_intensity"],
    }
