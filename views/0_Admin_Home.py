"""Admin 菜单首页；原 app.py 的入口内容移入这里。"""
import streamlit as st
from admin_auth import require_admin_page
from utils.style import page_header, section_header

require_admin_page()

page_header("景行智调 · 管理工作台", "围绕同一场景设置、运行和比较接驳调度策略，向游客提供已发布的科研仿真结果。", "ADMIN · 入口说明")
st.info("科研情景仿真：系统未接入景区真实实时车辆、排队或官方调度数据。")
section_header("从场景到出行参考", "先确认研究线路与模型边界，再设置场景、运行策略并检查结果。")

c1, c2, c3 = st.columns(3)
with c1:
    with st.container(border=True):
        st.subheader("01 · 车辆与线路")
        st.write("站点、线路及估算路段距离；车辆数可在调度页调整。")
        st.page_link("views/2_Admin_Vehicle_Route.py", label="查看研究网络", icon="🚌")
with c2:
    with st.container(border=True):
        st.subheader("02 · 智能调度")
        st.write("固定间隔、动态阈值和滚动预测三种策略。")
        st.page_link("views/4_Admin_Smart_Dispatch.py", label="进入调度工作区", icon="🧠")
with c3:
    with st.container(border=True):
        st.subheader("03 · 检查与发布")
        st.write("真实读取本轮仿真记录，支持导出四份CSV。")
        st.page_link("views/5_Admin_Simulation_Monitor.py", label="检查仿真结果", icon="📊")

st.caption("⚠️ 车队规模、客流、双向折返等属于模型假设；结果不是钟山风景区实测数据。")
