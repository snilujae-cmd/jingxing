"""景行智调 · 六模块管理工作台。"""

import streamlit as st

from admin_auth import require_admin_page
from utils.style import admin_navigation, page_header, page_surface


require_admin_page()
page_surface("admin")
admin_navigation("工作台")
page_header(
    "景行智调 · 智能调度管理中心",
    "统一配置研究线路与客流场景，运行调度策略，监测仿真过程并分析实验结果。",
    "ADMIN · WORKSPACE",
)

modules = [
    ("01", "调度控制台", "集中查看当前会话的模型配置、运行状态和关键指标。",
     "views/1_Admin_Dashboard.py"),
    ("02", "车辆与线路", "查看研究站点、线路结构与路段数据。",
     "views/2_Admin_Vehicle_Route.py"),
    ("03", "客流场景", "设置客流模式、基准到达率、仿真时长及潮汐/突发条件。",
     "views/3_Admin_Demand_Scenario.py"),
    ("04", "智能调度", "配置车队与策略参数，执行单策略仿真或同场景三策略比较。",
     "views/4_Admin_Smart_Dispatch.py"),
    ("05", "仿真监测", "查看车辆、站点排队和候车时间等仿真指标。",
     "views/5_Admin_Simulation_Monitor.py"),
    ("06", "实验分析", "回顾会话内实验记录，对比已完成仿真的指标与图表。",
     "views/6_Admin_Experiment_Analysis.py"),
]

for row in (modules[:3], modules[3:]):
    for column, (number, title, description, path) in zip(st.columns(3, gap="large"), row):
        with column:
            with st.container(border=True):
                st.markdown(
                    f'<div class="jx-admin-card"><div class="jx-number">{number} / MODULE</div>'
                    f'<h3>{title}</h3><p>{description}</p></div>',
                    unsafe_allow_html=True,
                )
                st.page_link(path, label=f"进入{title} →", use_container_width=True)

st.caption("科研情景仿真结果来自真实运行；车辆、客流和调度参数不代表景区实时运营数据。")
