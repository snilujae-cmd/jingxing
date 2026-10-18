# 来源：景区工作人员电话访谈

VEHICLE_TYPES = {
    "小型": {"capacity": 22},
    "中型": {"capacity": 36},
    "大型": {"capacity": 40},
}

SPEED_RANGE_KMH = (5, 20)

DEFAULT_FLEET = {"A": 5, "B": 3}

DISPATCH_POLICY = {
    "interval_min": (15, 20),
    "cross_route_dispatch": False,
    "source": "景区工作人员电话访谈",
}