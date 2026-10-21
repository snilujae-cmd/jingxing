"""读取页面4的同一次模拟输出；绝不单独生成展示数据。"""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from admin_auth import require_admin_page
from utils.style import admin_navigation, apply_plotly_theme, page_header, page_surface, section_header

require_admin_page()
page_surface("admin")
admin_navigation("仿真监测")

page_header("仿真监测", "读取最近一次运行的站点排队、已上车游客候车分布与时序记录。", "ADMIN · SIMULATION")
r = st.session_state.get("last_result")
if r is None:
    st.info("👉 请先在「智能调度控制」运行一次仿真")
    st.stop()
st.caption(f"运行编号：{r['run_id']} · 策略：{r['strategy']} · 仿真生成数据，非景区实时状态")
section_header("运行概览")
m1, m2, m3, m4 = st.columns(4)
m1.metric("总到达", f"{r['total_arrivals']} 人")
m2.metric("已上车", f"{r['served']} 人")
m3.metric("期末未上车", f"{r['unserved']} 人")
m4.metric("服务率", f"{r['service_rate'] * 100:.1f}%")
section_header("站点与候车分析", "排队图是仿真期末快照，等待分布只覆盖已上车游客。")
with st.container(border=True):
    st.subheader("各站点期末排队")
    values = r["stations"]
    fig = go.Figure(go.Bar(x=list(values), y=list(values.values()),
                           marker_color="#1E6F5C", text=list(values.values()), textposition="outside"))
    fig.update_layout(height=350, yaxis_title="未上车人数")
    st.plotly_chart(apply_plotly_theme(fig), use_container_width=True)

with st.container(border=True):
    st.subheader("已上车游客等待时间分布")
    fig = go.Figure(go.Histogram(x=r["waits"], nbinsx=30, marker_color="#C6A15A"))
    fig.update_layout(height=350, xaxis_title="候车（分钟）")
    st.plotly_chart(apply_plotly_theme(fig), use_container_width=True)

if r["station_state"]:
    with st.container(border=True):
        st.subheader("站点排队时序（每5分钟，按线路站序区分）")
        df = pd.DataFrame(r["station_state"])
        timeline = df.groupby(["time_min", "route_station_seq"], as_index=False)["queue_length"].sum()
        pivot = timeline.pivot(index="time_min", columns="route_station_seq", values="queue_length")
        fig = go.Figure()
        for stop in pivot.columns:
            fig.add_trace(go.Scatter(x=pivot.index, y=pivot[stop], mode="lines", name=str(stop)))
        fig.update_layout(height=420, xaxis_title="仿真时刻（分钟）", yaxis_title="排队人数")
        st.plotly_chart(apply_plotly_theme(fig), use_container_width=True)

st.caption("⚠️ 未上车的游客不计入已上车者候车分布，不能把这个分布当作全部游客的完整等待时间。")
