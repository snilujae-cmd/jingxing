"""共享的仿真假设：仿真客流生成与优化器预测使用同一需求模型。

arrival_rate 表示A+B两线合计的基础每小时到达人数，绝不是每站到达率。
本模块中的时间、人流比例均为比赛模拟假设，而非景区实测。
"""
from __future__ import annotations
import math

from data.routes import ROUTES


def route_weights(params):
    raw = params.get("route_weights", {"A": 0.6, "B": 0.4})
    if set(raw) != set(ROUTES) or any(float(v) < 0 for v in raw.values()):
        raise ValueError("route_weights需覆盖所有线路且权重非负")
    total = sum(float(v) for v in raw.values())
    if total <= 0:
        raise ValueError("route_weights之和必须大于0")
    return {rid: float(v) / total for rid, v in raw.items()}


def demand_multiplier(t, params):
    duration = float(params["duration_min"])
    scenario = params.get("scenario_type", "平峰")
    peak_mul = float(params.get("peak_multiplier", 2.0))
    u = t / duration
    if scenario == "上午高峰":
        bump = math.exp(-0.5 * ((u - 0.25) / 0.15) ** 2)
        mult = 1 + (peak_mul - 1) * bump
    elif scenario == "下午高峰":
        bump = math.exp(-0.5 * ((u - 0.75) / 0.15) ** 2)
        mult = 1 + (peak_mul - 1) * bump
    else:
        mult = 1.0
    if params.get("disruption", False):
        center = float(params.get("disruption_center", duration / 2))
        sigma = max(0.01, float(params.get("disruption_sigma", 30)))
        strength = max(0.01, float(params.get("disruption_intensity", 2.0)))
        spike = math.exp(-0.5 * ((t - center) / sigma) ** 2)
        if params.get("disruption_type") == "客流骤降":
            # “2倍影响”表示突发中心的客流降至基准的 1/2，而不是意外增加一倍。
            adjustment = 1 + (1 / strength - 1) * spike
        elif params.get("disruption_type") == "双向高峰":
            # 双向高峰改变OD方向，客流总量倍率由配置strength决定。
            adjustment = 1 + (strength - 1) * spike
        else:
            adjustment = 1 + (strength - 1) * spike
        mult *= max(0.0, adjustment)
    return max(0.0, mult)


def outbound_fraction(t, params):
    scenario = params.get("scenario_type", "平峰")
    default = 0.75 if scenario == "上午高峰" else (0.25 if scenario == "下午高峰" else 0.5)
    if params.get("tidal", False):
        duration = float(params["duration_min"])
        u = t / duration
        morning = math.exp(-0.5 * ((u - 0.25) / 0.18) ** 2)
        afternoon = math.exp(-0.5 * ((u - 0.75) / 0.18) ** 2)
        default = min(0.95, max(0.05, default + 0.2 * morning - 0.2 * afternoon))
    if params.get("disruption") and params.get("disruption_type") == "双向高峰":
        center = float(params.get("disruption_center", params["duration_min"] / 2))
        sigma = max(0.01, float(params.get("disruption_sigma", 30)))
        pulse = math.exp(-0.5 * ((t - center) / sigma) ** 2)
        default = default * (1 - pulse) + 0.5 * pulse
    return default


def origin_weights(route_id, direction):
    n = len(ROUTES[route_id]["stations"])
    indices = list(range(n - 1)) if direction == 1 else list(range(1, n))
    raw = [1 / ((i + 1) ** 1.4) if direction == 1 else 1 / ((n - i) ** 1.4)
           for i in indices]
    total = sum(raw)
    return [(i, w / total) for i, w in zip(indices, raw)]
