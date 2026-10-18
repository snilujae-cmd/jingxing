"""景行智调 | 滚动优化器：短期需求预测 + 束搜索（近似 MPC）。

规划层使用按站点/线路方向聚合的**期望排队数**及保守的车辆上客容量预测；
真实游客 OD、上下客、车辆行驶和守恒均由 simulation.py 的离散事件引擎执行。
只接受当前已经观测的队列/车辆状态及已知车辆运行事件，不读取未来真实乘客事件。

此模块用于研究型模拟，束搜索仅提供近似可行决策，不保证全局最优。
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from itertools import combinations
import math

from data.routes import ROUTES
from data.segments import SEGMENTS
from core.demand import demand_multiplier, outbound_fraction, origin_weights

_DIST = {(e["from"], e["to"]): e["distance_km"] for e in SEGMENTS}


def _travel(a, b, speed):
    d = _DIST.get((a, b), _DIST.get((b, a)))
    if d is None or d <= 0:
        raise ValueError(f"优化器缺少路段距离 {a}->{b}")
    return 60.0 * float(d) / speed


@dataclass
class PredictionVehicle:
    route: str
    capacity: int
    available_at: float
    endpoint: int   # 0 或线路最后站的索引


@dataclass
class PredictedTrip:
    route: str
    direction: int
    remaining_capacity: float
    visits: list[tuple[float, str]]
    cursor: int = 0


@dataclass
class SearchState:
    q: dict[tuple[str, int], float]
    oldest: dict[tuple[str, int], float]
    vehicles: list[PredictionVehicle]
    trips: list[PredictedTrip]
    last: dict[tuple[str, int], float]
    time: float
    cost: float = 0.0
    first_action: tuple[int, ...] = ()
    departure_count: int = 0


def _visits(route, direction, idx, t, speed, dwell):
    sids = ROUTES[route]["stations"]
    out = [(t, sids[idx])]
    while 0 <= idx + direction < len(sids):
        next_idx = idx + direction
        t += dwell + _travel(sids[idx], sids[next_idx], speed)
        out.append((t, sids[next_idx]))
        idx = next_idx
    return out


def _forecast_arrivals(mid_t, dt, context, q):
    """按仿真引擎的同一需求假设预测期望到达数（绝不读取未来客流事件）。"""
    total = context["arrival_rate"] / 60 * dt * demand_multiplier(mid_t, context)
    outbound = outbound_fraction(mid_t, context)
    for rid, route_weight in context["route_weights"].items():
        for direction, weight in ((1, outbound), (-1, 1 - outbound)):
            for idx, station_weight in origin_weights(rid, direction):
                sid = ROUTES[rid]["stations"][idx]
                key = (sid, direction)
                q[key] = q.get(key, 0.0) + total * route_weight * weight * station_weight


def _forward(state, to_t, context):
    """推进预测层；未乘客真实到达事件只使用期望强度。"""
    start = state.time
    future_visits = ((vis_t, k, trip) for trip in state.trips for k, (vis_t, _) in
                     enumerate(trip.visits) if k >= trip.cursor and start - 1e-8 <= vis_t < to_t - 1e-8)
    # 最早事件时刻及区间端点；相同时间多个车次依次处理。
    visits = sorted(future_visits, key=lambda x: x[0])
    cur = start
    waiting_penalty = context["waiting_weight"]

    def advance_arrival(end_t):
        nonlocal cur
        if end_t <= cur:
            return
        dt = end_t - cur
        before = sum(state.q.values())
        overdue_before = sum(value for key, value in state.q.items()
                             if value > 0 and cur - state.oldest.get(key, cur) >= context["long_wait_threshold_min"])
        empty_before = {key for key, value in state.q.items() if value <= 1e-10}
        _forecast_arrivals((cur + end_t) / 2, dt, context, state.q)
        for key in empty_before:
            if state.q.get(key, 0) > 0:
                state.oldest[key] = cur
        after = sum(state.q.values())
        overdue_after = sum(value for key, value in state.q.items()
                            if value > 0 and end_t - state.oldest.get(key, end_t) >= context["long_wait_threshold_min"])
        state.cost += waiting_penalty * 0.5 * (before + after) * dt
        state.cost += context["fairness_weight"] * 0.5 * (overdue_before + overdue_after) * dt
        cur = end_t

    for vis_t, visit_i, trip in visits:
        advance_arrival(vis_t)
        key = (trip.visits[visit_i][1], trip.direction)
        board = min(state.q.get(key, 0.0), trip.remaining_capacity)
        state.q[key] = max(0.0, state.q.get(key, 0.0) - board)
        if state.q[key] <= 1e-10:
            state.oldest[key] = vis_t
        trip.remaining_capacity -= board  # 预测层假设途中无下客释放容量，保守估算
        trip.cursor = visit_i + 1
    advance_arrival(to_t)
    state.time = to_t
    state.trips = [tr for tr in state.trips if tr.cursor < len(tr.visits)]


def _available_actions(state, context, now):
    # 同线路、同方向同一决策时刻只允许一辆发车：每组保留容量最大的可用车，
    # 避免车队规模增加时进行 O(N²) 无意义的车辆ID组合搜索。
    best_by_lane = {}
    for i, v in enumerate(state.vehicles):
        if v.available_at > now + 1e-8:
            continue
        direction = 1 if v.endpoint == 0 else -1
        lane = (v.route, direction)
        if now - state.last[lane] < context["min_dispatch_gap_min"]:
            continue
        sids = ROUTES[v.route]["stations"]
        origins = sids[:-1] if direction == 1 else sids[1:]
        if sum(state.q.get((sid, direction), 0.0) for sid in origins) < 0.05:
            continue
        if lane not in best_by_lane or v.capacity > state.vehicles[best_by_lane[lane]].capacity:
            best_by_lane[lane] = i
    choices = list(best_by_lane.values())
    actions = [()]
    for n in range(1, min(context["max_departures_per_decision"], len(choices)) + 1):
        actions.extend(combinations(choices, n))
    return actions


def _apply_action(st, action, t, context):
    for i in action:
        v = st.vehicles[i]
        direction = 1 if v.endpoint == 0 else -1
        visits = _visits(v.route, direction, v.endpoint, t,
                         context["speed_kmh"], context["stop_dwell_min"])
        st.trips.append(PredictedTrip(v.route, direction, v.capacity, visits))
        # 到终点后至少需完成规定的折返准备，才能再次发车。
        v.available_at = visits[-1][0] + context["turnaround_min"]
        v.endpoint = (len(ROUTES[v.route]["stations"]) - 1) if direction == 1 else 0
        st.last[(v.route, direction)] = t
        st.departure_count += 1
        st.cost += context["dispatch_penalty"]


def _rank(st, end_t, ctx):
    # 不直接使用仿真结束时真实需求作为预测：仅以当前期望排队余额评分。
    remaining = max(0, end_t - st.time)
    return st.cost + ctx["terminal_backlog_weight"] * sum(st.q.values()) * (remaining + ctx["decision_interval_min"])


def propose_departures(*, now, stations, vehicles, events, last_departure, params,
                       route_weights, max_action=2):
    """返回当前时刻可立即发车的车辆 id 列表（通常0～2辆）。

    - stations: 当前已实际到达旅客的队列；vehicles: 当前车辆真实状态。
    - events: 仿真队列，只读取已知车辆后续到站/准备就绪事件，**不读取未来arrival事件**。
    - 运行前置条件：该策略由仿真引擎每5分钟调用一次。
    """
    H = float(params.get("prediction_horizon_min", 45))
    step = float(params.get("decision_interval_min", 5))
    beam_width = int(params.get("beam_width", 5))
    if H <= 0 or step <= 0 or beam_width < 1:
        raise ValueError("优化器预测时域、决策间隔及束宽不合法")
    current_end = min(float(params["duration_min"]), now + H)
    if current_end <= now + 1e-6:
        return []
    ctx = {
        "arrival_rate": float(params["arrival_rate"]),
        "scenario_type": params.get("scenario_type", "平峰"),
        "duration_min": params["duration_min"],
        "tidal": params.get("tidal", False),
        "disruption": params.get("disruption", False),
        "disruption_type": params.get("disruption_type", "客流突增"),
        "disruption_center": params.get("disruption_center", params["duration_min"] / 2),
        "disruption_sigma": params.get("disruption_sigma", 30),
        "disruption_intensity": params.get("disruption_intensity", 2.0),
        "peak_multiplier": float(params.get("peak_multiplier", 2.0)),
        "start_hour": float(params.get("start_hour", 8)),
        "route_weights": route_weights,
        "speed_kmh": float(params.get("speed_kmh", 15)),
        "stop_dwell_min": float(params.get("stop_dwell_min", 0.5)),
        "turnaround_min": float(params.get("turnaround_min", 2.0)),
        "min_dispatch_gap_min": float(params.get("min_dispatch_gap_min", 2.0)),
        "decision_interval_min": step,
        "max_departures_per_decision": int(params.get("max_departures_per_decision", 2)),
        "dispatch_penalty": float(params.get("dispatch_penalty", 15)),
        "terminal_backlog_weight": float(params.get("terminal_backlog_weight", 1.0)),
        "waiting_weight": 1.0,
        "fairness_weight": float(params.get("fairness_weight", 0.35)),
        "long_wait_threshold_min": float(params.get("long_wait_threshold_min", 15)),
    }
    q = {(sid, direction): float(len(st.queues[direction]))
         for sid, st in stations.items() for direction in (1, -1)}
    oldest = {(sid, direction): (st.queues[direction][0].arrival_t
                                 if st.queues[direction] else now)
              for sid, st in stations.items() for direction in (1, -1)}

    # 将运行中的车作为已承诺的未来服务：仅查看未来 VEHICLE 事件，不查看arrival。
    pending = {}
    for rec in events:
        event_t, _, typ, payload = rec
        if typ == "arrive":
            vid, next_idx = payload
            if vid not in pending or event_t < pending[vid][0]:
                pending[vid] = (event_t, "arrive", next_idx)
        elif typ in {"service", "ready"}:
            vid = payload
            if vid not in pending or event_t < pending[vid][0]:
                pending[vid] = (event_t, typ, None)

    future_vehicles = []
    trips = []
    for v in vehicles:
        last_index = len(ROUTES[v.route_id]["stations"]) - 1
        endpoint = 0 if v.idx == 0 else last_index
        available_at = now
        if v.status == "idle":
            endpoint = v.idx
        elif v.status == "turnaround":
            available_at = pending.get(v.id, (now + H + 100, None, None))[0]
            endpoint = v.idx
        elif v.status == "running":
            p = pending.get(v.id)
            if p is None:
                raise ValueError(f"运行中的车辆{v.id}缺少后续已计划到站事件")
            first_time, event_type, next_idx = p
            begin_idx = v.idx if event_type == "service" else next_idx
            visits = _visits(v.route_id, v.direction, begin_idx, first_time,
                             ctx["speed_kmh"], ctx["stop_dwell_min"])
            # 车辆实际当前占座量在预测层中保守占用剩余行程容量。
            trips.append(PredictedTrip(v.route_id, v.direction,
                                       max(0, v.capacity - len(v.onboard)), visits))
            available_at = visits[-1][0] + ctx["turnaround_min"]
            endpoint = last_index if v.direction == 1 else 0
        else:
            raise ValueError(f"未知车辆状态 {v.status}")
        future_vehicles.append(PredictionVehicle(v.route_id, v.capacity, available_at, endpoint))

    beam = [SearchState(q, oldest, future_vehicles, trips, dict(last_departure), now)]
    depth = int(math.ceil((current_end - now) / step))
    for layer in range(depth):
        t = now + layer * step
        to = min(current_end, t + step)
        expanded = []
        for st in beam:
            acts = _available_actions(st, ctx, t)
            for action in acts:
                child = deepcopy(st)
                _apply_action(child, action, t, ctx)
                if layer == 0:
                    child.first_action = tuple(action)
                _forward(child, to, ctx)
                expanded.append(child)
        # 剪枝时以剩余排队预估作排序，避免只偏好“当前不发车”。
        expanded.sort(key=lambda s: _rank(s, current_end, ctx))
        beam = expanded[:beam_width]
        if not beam:
            return []
    chosen = min(beam, key=lambda st: _rank(st, current_end, ctx))
    result = []
    for i in chosen.first_action[:max_action]:
        v = vehicles[i]
        if v.status == "idle":
            result.append(v.id)
    return result
