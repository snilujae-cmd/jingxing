"""景行智调：独立门户、游客端与受保护的管理端。"""

import streamlit as st

from admin_auth import is_admin
from utils.style import load_css


st.set_page_config(
    page_title="景行智调 · 景区接驳车仿真",
    page_icon="🚌",
    layout="wide",
    initial_sidebar_state="collapsed",
)
load_css()

admin_visibility = "visible" if is_admin() else "hidden"
pages = {
    "平台": [
        st.Page("views/portal.py", title="平台首页", icon="🏞️", default=True),
        st.Page("views/user.py", title="游客出行服务", icon="📍"),
        st.Page("views/admin_login.py", title="管理员登录 / 退出", icon="🔐"),
    ],
    "Admin 管理端": [
        st.Page("views/0_Admin_Home.py", title="管理工作台", icon="🏠", visibility=admin_visibility),
        st.Page("views/1_Admin_Dashboard.py", title="调度控制台", icon="🎛️", visibility=admin_visibility),
        st.Page("views/2_Admin_Vehicle_Route.py", title="车辆与线路", icon="🚌", visibility=admin_visibility),
        st.Page("views/3_Admin_Demand_Scenario.py", title="客流场景", icon="👥", visibility=admin_visibility),
        st.Page("views/4_Admin_Smart_Dispatch.py", title="智能调度", icon="🧠", visibility=admin_visibility),
        st.Page("views/5_Admin_Simulation_Monitor.py", title="仿真监测", icon="📡", visibility=admin_visibility),
        st.Page("views/6_Admin_Experiment_Analysis.py", title="实验分析", icon="📊", visibility=admin_visibility),
    ],
}

st.navigation(pages, position="hidden").run()
