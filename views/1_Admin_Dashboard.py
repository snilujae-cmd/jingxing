import streamlit as st
import plotly.graph_objects as go
from admin_auth import require_admin_page
from data.routes import ROUTES
from data.vehicles import DEFAULT_FLEET
from utils.style import apply_plotly_theme, page_header, section_header

require_admin_page()

page_header("调度控制台", "集中查看模型配置与本会话最近一次仿真，辅助研究场景中的调度决策。", "ADMIN · OVERVIEW")
section_header("模型配置", "以下为当前会话配置及访谈参考值，均非实时运营监控指标。")
fleet = st.session_state.get("fleet", dict(DEFAULT_FLEET))
c1, c2, c3, c4 = st.columns(4)
c1.metric("A线模拟车队", f"{fleet.get('A', 0)} 辆")
c2.metric("B线模拟车队", f"{fleet.get('B', 0)} 辆")
c3.metric("模拟总车队", f"{sum(fleet.values())} 辆")
c4.metric("访谈参考间隔", "约15–20 min")
st.caption("车辆数量可以在「智能调度控制」页面调整；初始5+3仅是演示值，不是景区实际车队。")
last_result = st.session_state.get("last_result")
section_header("本次仿真", "指标来自当前会话最近一次已完成的运行；已发布结果由游客端独立读取。")
if last_result is None:
    st.info("尚未运行仿真。请在「客流场景」完成配置后进入「智能调度」。")
else:
    st.caption(f"运行编号：{last_result['run_id']} · 策略：{last_result['strategy']}")
    r1, r2, r3, r4 = st.columns(4)
    r1.metric("已上车平均候车", f"{last_result['avg_wait']:.1f} 分钟" if last_result["served"] else "—")
    r2.metric("已上车 P95 候车", f"{last_result['p95_wait']:.1f} 分钟" if last_result["served"] else "—")
    r3.metric("期末未上车", f"{last_result['unserved']} 人")
    r4.metric("服务率", f"{last_result['service_rate'] * 100:.1f}%")
    st.caption("平均与 P95 候车只统计已上车游客；需结合未上车人数和服务率解读。")
section_header("研究线路与数据边界")
left, right = st.columns([2, 1])
with left:
    with st.container(border=True):
        st.subheader("📈 线路长度对比")
        fig = go.Figure(go.Bar(
            x=[f"{rid}线 {v['name']}" for rid, v in ROUTES.items()],
            y=[v["total_length_km"] for v in ROUTES.values()],
            marker_color=["#1E6F5C", "#C6A15A"],
            text=[v["total_length_km"] for v in ROUTES.values()],
            textposition="outside"))
        fig.update_layout(height=300, yaxis_title="距离（km）")
        st.plotly_chart(apply_plotly_theme(fig), use_container_width=True)
with right:
    with st.container(border=True):
        st.subheader("📢 数据来源与边界")
        st.success("A/B主线路来自公开资料及口头核实")
        st.warning("分段距离、周转、客流和车队规模含仿真假设")
        st.info("B线约6.5公里为模型估算，不是景区实测距离。")
section_header("继续工作")
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
