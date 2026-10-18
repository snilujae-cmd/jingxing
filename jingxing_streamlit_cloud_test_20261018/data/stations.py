STATIONS = {
    # A线路
    "A0": {"name": "钟灵街地铁站", "route": "A", "type": "起点/地铁接驳入口"},
    "A1": {"name": "体育公园",     "route": "A", "type": "景区站点"},
    "A2": {"name": "灵谷景区",     "route": "A;B", "type": "换乘站"},
    "A3": {"name": "流徽榭",       "route": "A;B", "type": "换乘站"},
    "A4": {"name": "孙中山纪念馆", "route": "A;B", "type": "终点"},
    # B线路
    "B0": {"name": "紫金·钟爱里",  "route": "B", "type": "起点/外围集散中心"},
    "B1": {"name": "灵谷景区",     "route": "B", "type": "换乘站"},
    "B2": {"name": "流徽榭",       "route": "B", "type": "换乘站"},
    "B3": {"name": "孙中山纪念馆", "route": "B", "type": "终点"},
}

# 物理共用站点映射（A2与B1、A3与B2、A4与B3）
SHARED = {
    "A2": "B1",
    "A3": "B2",
    "A4": "B3",
}