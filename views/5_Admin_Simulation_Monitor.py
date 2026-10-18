"""读取页面4的同一次模拟输出；绝不单独生成展示数据。"""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from admin_auth import require_admin_page

require_admin_page()

st.title("📡 Admin端 · 仿真监测")
r = st.session_state.get("last_result")
if r is None:
    st.info("👉 请先在「智能调度控制」运行一次仿真")
    st.stop()
st.caption(f"运行编号：{r['run_id']} · 策略：{r['strategy']} · 仿真生成数据，非景区实时状态")
with st.container(border=True):
    st.subheader("各站点期末排队")
    values = r["stations"]
    fig = go.Figure(go.Bar(x=list(values), y=list(values.values()),
                           marker_color="#1E6F5C", text=list(values.values()), textposition="outside"))
    fig.update_layout(height=350, yaxis_title="未上车人数")
    st.plotly_chart(fig, use_container_width=True)

with st.container(border=True):
    st.subheader("已上车游客等待时间分布")
    fig = go.Figure(go.Histogram(x=r["waits"], nbinsx=30, marker_color="#F6BD16"))
    fig.update_layout(height=350, xaxis_title="候车（分钟）")
    st.plotly_chart(fig, use_container_width=True)

if r["station_state"]:
    with st.container(border=True):
        st.subheader("站点排队时序（每5分钟，按线路站序区分）")
        df = pd.DataFrame(r["station_state"])
        timeline = df.groupby(["time_min", "route_station_seq"], as_index=False)["queue_length"].sum()
        pivot = timeline.pivot(index="time_min", columns="route_station_seq", values="queue_length")
        st.line_chart(pivot)

st.caption("⚠️ 未上车的游客不计入已上车者候车分布，不能把这个分布当作全部游客的完整等待时间。")
