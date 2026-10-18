import streamlit as st
import plotly.graph_objects as go
from admin_auth import require_admin_page
from data.routes import ROUTES
from data.vehicles import DEFAULT_FLEET

require_admin_page()

st.title("🎛️ Admin端 · 调度控制台")
st.caption("面向景区运营调度员｜仿真辅助决策原型")
fleet = st.session_state.get("fleet", dict(DEFAULT_FLEET))
c1, c2, c3, c4 = st.columns(4)
c1.metric("A线模拟车队", f"{fleet.get('A', 0)} 辆")
c2.metric("B线模拟车队", f"{fleet.get('B', 0)} 辆")
c3.metric("模拟总车队", f"{sum(fleet.values())} 辆")
c4.metric("访谈参考间隔", "约15–20 min")
st.caption("车辆数量可以在「智能调度控制」页面调整；初始5+3仅是演示值，不是景区实际车队。")
st.markdown("---")
left, right = st.columns([2, 1])
with left:
    with st.container(border=True):
        st.subheader("📈 线路长度对比")
        fig = go.Figure(go.Bar(
            x=[f"{rid}线 {v['name']}" for rid, v in ROUTES.items()],
            y=[v["total_length_km"] for v in ROUTES.values()],
            marker_color=["#1E6F5C", "#F6BD16"],
            text=[v["total_length_km"] for v in ROUTES.values()],
            textposition="outside"))
        fig.update_layout(height=300, yaxis_title="距离（km）")
        st.plotly_chart(fig, use_container_width=True)
with right:
    with st.container(border=True):
        st.subheader("📢 数据来源与边界")
        st.success("A/B主线路来自公开资料及口头核实")
        st.warning("分段距离、周转、客流和车队规模含仿真假设")
        st.info("B线约6.5公里为模型估算，不是景区实测距离。")
st.markdown("---")
st.subheader("🧭 快捷入口")
c1, c2, c3 = st.columns(3)
with c1:
    if st.button("🚌 车辆与线路", use_container_width=True):
        st.switch_page("views/2_Admin_Vehicle_Route.py")
with c2:
    if st.button("🧠 智能调度", use_container_width=True):
        st.switch_page("views/4_Admin_Smart_Dispatch.py")
with c3:
    if st.button("📊 实验分析", use_container_width=True):
        st.switch_page("views/6_Admin_Experiment_Analysis.py")
st.caption("研究型仿真结果，不代表景区实际运营效果。")
