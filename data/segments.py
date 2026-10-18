# ============================================================
# 路段数据（来源：景行智调仿真参数表_V2）
# - 距离：高德地图线路图估算（C类）
# - 时间：按 20 km/h 理论速度计算
# - 不提供"全程总时间"
# ============================================================

THEORETICAL_SPEED_KMH = 20

def theoretical_time(distance_km):
    if distance_km is None:
        return None
    return round(distance_km / THEORETICAL_SPEED_KMH * 60, 1)

_RAW = [
    # A线路
    {"edge_id": "A-E1", "route": "A", "from": "A0", "to": "A1", "distance_km": 0.9,  "status": "估算值"},
    {"edge_id": "A-E2", "route": "A", "from": "A1", "to": "A2", "distance_km": 0.92, "status": "估算值"},
    {"edge_id": "A-E3", "route": "A", "from": "A2", "to": "A3", "distance_km": 0.98, "status": "估算值"},
    {"edge_id": "A-E4", "route": "A", "from": "A3", "to": "A4", "distance_km": 0.3,  "status": "估算值"},
    # B线路
    {"edge_id": "B-E1", "route": "B", "from": "B0", "to": "B1", "distance_km": 5.2,  "status": "待核实"},
    {"edge_id": "B-E2", "route": "B", "from": "B1", "to": "B2", "distance_km": 0.98, "status": "假设"},
    {"edge_id": "B-E3", "route": "B", "from": "B2", "to": "B3", "distance_km": 0.3,  "status": "假设"},
]

SEGMENTS = []
for s in _RAW:
    seg = dict(s)
    seg["travel_time_min"] = theoretical_time(s["distance_km"])
    seg["is_estimated"] = True
    SEGMENTS.append(seg)