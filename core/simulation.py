"""景行智调：可复现的乘客OD/上下车/折返仿真引擎（研究型原型）。

统一 run_simulation API 支持 fixed / dynamic / optimized；状态CSV由本次仿真
直接产生，而非页面单独编造。正反向均假定可沿相同道路通行，需景区确认。
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import hashlib
import heapq
import json
from typing import Optional

import numpy as np

from core.demand import demand_multiplier, outbound_fraction, origin_weights, route_weights as get_route_weights
from data.routes import ROUTES
from data.stations import STATIONS
from data.segments import SEGMENTS
from data.vehicles import VEHICLE_TYPES

# 与User端数据接口隔离：此映射为待核对的临时编号，不属于实测资料。
from data.station_id_map import PHYSICAL_IDS
_DISTANCE = {(e["from"], e["to"]): e["distance_km"] for e in SEGMENTS}


@dataclass
class Passenger:
    arrival_t: float
    dest_idx: int
    pid: int = 0
    route_id: str = ""
    origin: str = ""
    destination: str = ""
    direction: int = 1
    board_t: Optional[float] = None
    alight_t: Optional[float] = None


class Station:
    def __init__(self, sid, name):
        self.id, self.name = sid, name
        self.queues = {1: deque(), -1: deque()}
        self.wait_records = []

    def add(self, passenger, direction=None):
        direction = passenger.direction if direction is None else direction
        self.queues[direction].append(passenger)

    def board(self, capacity, t, direction=1):
        boarded = []
        q = self.queues[direction]
        while q and len(boarded) < capacity:
            p = q.popleft()
            p.board_t = t
            self.wait_records.append(t - p.arrival_t)
            boarded.append(p)
        return boarded

    def size(self):
        return sum(len(q) for q in self.queues.values())


class Vehicle:
    def __init__(self, vid, route_id, capacity, endpoint=0):
        self.id, self.route_id, self.capacity = vid, route_id, capacity
        self.idx = endpoint
        self.direction = 1 if endpoint == 0 else -1
        self.onboard = []
        self.status = "idle"
        self.running_since = None

    def current(self):
        return ROUTES[self.route_id]["stations"][self.idx]


def get_travel_time(frm, to, speed_kmh):
    distance = _DISTANCE.get((frm, to), _DISTANCE.get((to, frm)))
    if distance is None or distance <= 0:
        raise ValueError(f"缺少已确认的路段距离: {frm} ↔ {to}")
    return 60.0 * distance / speed_kmh


def _params(params):
    p = dict(params)
    p.setdefault("fleet", {"A": 5, "B": 3})
    p["fleet"] = {rid: int(p["fleet"].get(rid, 0)) for rid in ROUTES}
    p.setdefault("duration_min", 120)
    p.setdefault("arrival_rate", 120)
    p.setdefault("speed_kmh", 15)
    p.setdefault("fixed_interval", 17)
    p.setdefault("queue_threshold", 20)
    p.setdefault("peak_multiplier", 2.0)
    p.setdefault("scenario_type", "平峰")
    p.setdefault("tidal", False)
    p.setdefault("disruption", False)
    p.setdefault("disruption_type", "客流突增")
    p.setdefault("stop_dwell_min", 0.5)
    p.setdefault("turnaround_min", 2.0)
    p.setdefault("min_dispatch_gap_min", 2.0)
    p.setdefault("decision_interval_min", 5.0)
    p.setdefault("prediction_horizon_min", 30.0)
    p.setdefault("beam_width", 4)
    p.setdefault("max_departures_per_decision", 2)
    p.setdefault("snapshot_interval_min", 5.0)
    p.setdefault("vehicle_capacities", {
        rid: [VEHICLE_TYPES["中型"]["capacity"]] * n for rid, n in p["fleet"].items()
    })
    if set(p["fleet"]) != set(ROUTES) or any(n < 0 for n in p["fleet"].values()):
        raise ValueError("车辆数必须为非负整数，覆盖A/B线路")
    if not (0 < float(p["speed_kmh"]) <= 20):
        raise ValueError("模拟速度须位于0~20 km/h（20为假设速度上限）")
    for key in ("duration_min", "fixed_interval", "decision_interval_min", "prediction_horizon_min", "snapshot_interval_min"):
        if float(p[key]) <= 0:
            raise ValueError(f"{key}必须大于0")
    if int(p["beam_width"]) < 1 or int(p["max_departures_per_decision"]) < 1:
        raise ValueError("束搜索宽度和单次最大发车数必须为正整数")
    if float(p["min_dispatch_gap_min"]) < 0 or float(p["queue_threshold"]) < 0:
        raise ValueError("最小发车间隔和排队阈值不能为负")
    if float(p["arrival_rate"]) < 0 or float(p["peak_multiplier"]) < 0:
        raise ValueError("客流与高峰倍数不能为负")
    if float(p["stop_dwell_min"]) < 0 or float(p["turnaround_min"]) < 0:
        raise ValueError("停站与折返时长不能为负")
    for rid, number in p["fleet"].items():
        capacities = p["vehicle_capacities"].get(rid, [])
        if len(capacities) != number or any(int(c) <= 0 for c in capacities):
            raise ValueError(f"{rid}线的逐车载客量必须与车辆数一致，且全部为正数")
    p["route_weights"] = get_route_weights(p)
    return p


def _passengers(p, rng):
    """先用固定seed一次性生成全场客流，之后三种策略共享完全相同的输入。"""
    passengers = []
    rid_list = list(ROUTES)
    rid_probs = [p["route_weights"][rid] for rid in rid_list]
    duration = float(p["duration_min"])
    for minute in range(int(np.ceil(duration))):
        end = min(duration, minute + 1)
        rate = p["arrival_rate"] / 60 * (end - minute) * demand_multiplier((minute + end) / 2, p)
        for _ in range(rng.poisson(rate)):
            t = float(rng.uniform(minute, end))
            rid = str(rng.choice(rid_list, p=rid_probs))
            direction = 1 if rng.random() < outbound_fraction(t, p) else -1
            choices = origin_weights(rid, direction)
            idx = int(rng.choice([x[0] for x in choices], p=[x[1] for x in choices]))
            n = len(ROUTES[rid]["stations"])
            possible_dest = list(range(idx + 1, n)) if direction == 1 else list(range(idx - 1, -1, -1))
            dest_idx = int(rng.choice(possible_dest))
            stops = ROUTES[rid]["stations"]
            passengers.append(Passenger(t, dest_idx, len(passengers) + 1, rid,
                                        stops[idx], stops[dest_idx], direction))
    # 将全部乘客按到达时刻排序再统一编号，方便外部对齐和复现
    passengers.sort(key=lambda x: x.arrival_t)
    for i, passenger in enumerate(passengers, 1):
        passenger.pid = i
    return passengers


def run_simulation(params, strategy="fixed", seed=42):
    """运行一次仿真；返回可视化指标及全部站点、车辆、OD、乘客的记录行。"""
    if strategy == "optimizer":  # 兼容旧UI曾使用的名称，但实际采用优化策略
        strategy = "optimized"
    if strategy not in {"fixed", "dynamic", "optimized"}:
        raise ValueError(f"未知调度策略: {strategy}")
    p = _params(params)
    rng = np.random.default_rng(seed)
    people = _passengers(p, rng)
    signature = hashlib.sha256(json.dumps(
        [(round(x.arrival_t, 9), x.origin, x.destination) for x in people],
        ensure_ascii=False).encode("utf-8")).hexdigest()[:16]
    p_signature = hashlib.sha256(json.dumps(p, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:8]
    run_id = f"sim-{signature[:8]}-{p_signature}-{strategy}-s{seed}"
    stations = {sid: Station(sid, item["name"]) for sid, item in STATIONS.items()}
    vehicles = [Vehicle(f"{rid}-{i+1:02d}", rid, int(cap))
                for rid in ROUTES for i, cap in enumerate(p["vehicle_capacities"][rid])]
    vmap = {v.id: v for v in vehicles}
    last_departure = {(rid, d): -float("inf") for rid in ROUTES for d in (1, -1)}
    dispatch_log, station_records, vehicle_records = [], [], []
    events = []
    seq = 0

    def emit(t, typ, payload):
        nonlocal seq
        seq += 1
        heapq.heappush(events, (float(t), seq + (10**8 if typ == "snapshot" else 0), typ, payload))

    for person in people:
        emit(person.arrival_t, "arrival", person)
    duration = float(p["duration_min"])
    interval = float(p["snapshot_interval_min"])
    for t in np.arange(0, duration + interval * 0.5, interval):
        if t <= duration + 1e-8:
            emit(t, "snapshot", None)
    if strategy == "fixed":
        for rid in ROUTES:
            for t in np.arange(0, duration, p["fixed_interval"]):
                emit(t, "fixed_check", rid)
    elif strategy == "dynamic":
        for t in np.arange(0, duration, 1.0):
            emit(t, "dynamic_check", None)
    else:
        for t in np.arange(0, duration, p["decision_interval_min"]):
            emit(t, "optimized_check", None)
    # 约定：相同时刻发车、车辆到站等即时事件总在快照之前处理。
    # 因为 snapshot 事件预先插入队列，这里在记录快照时聚合所有同一时刻事件。
    busy_minutes = 0.0

    def dispatch(v, t):
        lane = (v.route_id, 1 if v.idx == 0 else -1)
        if v.status != "idle" or t - last_departure[lane] < p["min_dispatch_gap_min"] - 1e-9:
            return False
        v.direction = lane[1]
        v.status = "running"
        v.running_since = t
        last_departure[lane] = t
        dispatch_log.append({"run_id": run_id, "time_min": round(t, 6),
                             "vehicle_id": v.id, "route": v.route_id,
                             "direction": v.direction, "origin": v.current()})
        emit(t, "service", v.id)
        return True

    while events:
        t, _, kind, payload = heapq.heappop(events)
        if t > duration + 1e-8:
            break
        if kind == "arrival":
            person = payload
            stations[person.origin].add(person)

        elif kind == "fixed_check":
            candidates = [v for v in vehicles if v.route_id == payload and v.status == "idle"]
            if candidates:
                # 保持线路固定发车节奏；不因低需求而刻意取消班次
                dispatch(candidates[0], t)

        elif kind == "dynamic_check":
            threshold = p["queue_threshold"]
            # 各线路/方向排队达到阈值，才允许有对应端点空闲车出发。
            dispatched_lanes = set()
            for v in vehicles:
                if v.status != "idle":
                    continue
                direction = 1 if v.idx == 0 else -1
                lane = (v.route_id, direction)
                if lane in dispatched_lanes:
                    continue
                route_stops = ROUTES[v.route_id]["stations"]
                origins = route_stops[:-1] if direction == 1 else route_stops[1:]
                demand = sum(len(stations[sid].queues[direction]) for sid in origins)
                if demand >= threshold and dispatch(v, t):
                    dispatched_lanes.add(lane)

        elif kind == "optimized_check":
            from core.optimizer import propose_departures
            chosen = propose_departures(now=t, stations=stations, vehicles=vehicles,
                                        events=events, last_departure=last_departure,
                                        params=p, route_weights=p["route_weights"])
            for vid in chosen:
                if vid not in vmap or not dispatch(vmap[vid], t):
                    raise RuntimeError(f"优化器给出非法的发车指令: {vid}")

        elif kind == "service":
            v = vmap[payload]
            if v.status != "running":
                raise RuntimeError("车辆到站服务时不在运行状态")
            sid = v.current()
            # 先下车腾出座位，再有向地上车（不同线路不混乘）
            onboard = []
            for person in v.onboard:
                if person.destination == sid:
                    person.alight_t = t
                else:
                    onboard.append(person)
            v.onboard = onboard
            boarded = stations[sid].board(v.capacity - len(v.onboard), t, v.direction)
            v.onboard.extend(boarded)
            next_index = v.idx + v.direction
            if not 0 <= next_index < len(ROUTES[v.route_id]["stations"]):
                # 车辆完成单方向行程；准备折返，空载后从另一侧发车
                if v.onboard:
                    raise RuntimeError("行程终点出现未下车乘客，OD或方向模型不合法")
                busy_minutes += max(0, t - v.running_since)
                v.running_since = None
                v.status = "turnaround"
                emit(t + float(p["turnaround_min"]), "ready", v.id)
            else:
                end_sid = ROUTES[v.route_id]["stations"][next_index]
                tt = get_travel_time(sid, end_sid, p["speed_kmh"])
                emit(t + float(p["stop_dwell_min"]) + tt, "arrive", (v.id, next_index))

        elif kind == "arrive":
            vid, idx = payload
            v = vmap[vid]
            v.idx = idx
            emit(t, "service", v.id)

        elif kind == "ready":
            v = vmap[payload]
            v.status = "idle"
            v.direction = 1 if v.idx == 0 else -1

        elif kind == "snapshot":
            for rid, route in ROUTES.items():
                for sid in route["stations"]:
                    station = stations[sid]
                    for direction in (1, -1):
                        queue = station.queues[direction]
                        station_records.append({
                            "run_id": run_id, "time_min": round(t, 4),
                            "station_id": PHYSICAL_IDS[sid], "route_station_seq": sid,
                            "route_id": rid, "direction": direction,
                            "queue_length": len(queue),
                            "oldest_wait_min": round(max(0, t - queue[0].arrival_t), 4) if queue else 0.0,
                        })
            for v in vehicles:
                vehicle_records.append({
                    "run_id": run_id, "time_min": round(t, 4),
                    "vehicle_id": v.id, "route_id": v.route_id,
                    "station_id": PHYSICAL_IDS[v.current()], "route_station_seq": v.current(),
                    "direction": v.direction, "status": v.status,
                    "load": len(v.onboard), "capacity": v.capacity,
                })
        else:
            raise RuntimeError(f"未知仿真事件: {kind}")

    # 期末指标：每一个到达者的等待都至少计至上车或模拟截止时
    waiting_person_minutes = sum(
        (person.board_t if person.board_t is not None else duration) - person.arrival_t
        for person in people
    )
    for v in vehicles:
        if v.running_since is not None:
            busy_minutes += duration - v.running_since
    waits = [round(x.board_t - x.arrival_t, 8) for x in people if x.board_t is not None]
    arrivals = len(people)
    served = len(waits)
    completed = sum(x.alight_t is not None for x in people)
    onboard_end = sum(len(v.onboard) for v in vehicles)
    unserved = arrivals - served
    if served != completed + onboard_end or unserved != sum(s.size() for s in stations.values()):
        raise RuntimeError("乘客守恒校验失败，请勿展示本次结果")
    od_aggregated = {}
    passenger_records = []
    for x in people:
        key = (int(x.arrival_t // 15) * 15, x.route_id, x.origin, x.destination)
        od_aggregated[key] = od_aggregated.get(key, 0) + 1
        passenger_records.append({
            "run_id": run_id, "passenger_id": x.pid, "route_id": x.route_id,
            "origin_station_id": PHYSICAL_IDS[x.origin], "origin_route_station_seq": x.origin,
            "destination_station_id": PHYSICAL_IDS[x.destination],
            "destination_route_station_seq": x.destination,
            "direction": x.direction, "arrival_time_min": round(x.arrival_t, 5),
            "board_time_min": round(x.board_t, 5) if x.board_t is not None else None,
            "alight_time_min": round(x.alight_t, 5) if x.alight_t is not None else None,
            "wait_min": round(x.board_t - x.arrival_t, 5) if x.board_t is not None else None,
            "status": "completed" if x.alight_t is not None else
                      "onboard" if x.board_t is not None else "waiting",
        })
    od_records = [{"run_id": run_id, "window_start_min": win, "route_id": rid,
                   "origin_station_id": PHYSICAL_IDS[origin], "origin_route_station_seq": origin,
                   "destination_station_id": PHYSICAL_IDS[dest], "destination_route_station_seq": dest,
                   "passengers": count}
                  for (win, rid, origin, dest), count in sorted(od_aggregated.items())]
    return {
        "strategy": strategy, "seed": seed, "scenario_type": p["scenario_type"],
        "params": p, "run_id": run_id, "demand_signature": signature,
        "avg_wait": float(np.mean(waits)) if waits else 0.0,
        "max_wait": float(np.max(waits)) if waits else 0.0,
        "p95_wait": float(np.percentile(waits, 95)) if waits else 0.0,
        "over_ratio": float(np.mean(np.array(waits) > 15)) if waits else 0.0,
        "waits": waits, "total_arrivals": arrivals, "served": served, "boarded": served,
        "completed": completed, "onboard_end": onboard_end, "unserved": unserved,
        "queue_end": unserved, "stations": {sid: st.size() for sid, st in stations.items()},
        "service_rate": served / arrivals if arrivals else 0.0,
        "total_trips": len(dispatch_log), "total_departures": len(dispatch_log),
        "dispatch_log": dispatch_log, "total_wait_person_min": max(0.0, waiting_person_minutes),
        "avg_observed_wait_all": waiting_person_minutes / arrivals if arrivals else 0.0,
        "vehicle_busy_minutes": max(0.0, busy_minutes),
        "od_flow": od_records, "station_state": station_records,
        "vehicle_state": vehicle_records, "passenger_results": passenger_records,
    }
