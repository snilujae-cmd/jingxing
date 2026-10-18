import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
from admin_auth import require_admin_page

require_admin_page()

st.title("📊 Admin端 · 实验效果分析")

if "experiments" not in st.session_state:
    st.session_state.experiments = []

col1, col2 = st.columns([1, 3])
with col1:
    if st.button("📝 保存当前实验", type="primary", use_container_width=True):
        if "last_result" in st.session_state:
            r = st.session_state["last_result"]
            st.session_state.experiments.append({
                "编号": f"E{len(st.session_state.experiments)+1:03d}",
                "时间": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "运行编号": r["run_id"],
                "策略": r["strategy"],
                "A线车辆": r["params"]["fleet"].get("A", 0),
                "B线车辆": r["params"]["fleet"].get("B", 0),
                "车队总数": sum(r["params"]["fleet"].values()),
                "单车容量": ",".join(str(x) for x in sorted({c for cs in r["params"]["vehicle_capacities"].values() for c in cs})),
                "行驶速度": r["params"]["speed_kmh"],
                "场景": r["scenario_type"],
                "随机种子": r["seed"],
                "客流签名": r["demand_signature"],
                "总到达": r["total_arrivals"],
                "已上车": r["served"],
                "未上车": r["unserved"],
                "服务率(%)": round(r["service_rate"] * 100, 1),
                "平均等待": round(r["avg_wait"], 1) if r["served"] else None,
                "已观察总候车（人·分钟）": r["total_wait_person_min"],
                "全体已观察均值": r["avg_observed_wait_all"],
                "预测范围（分钟）": r["params"].get("prediction_horizon_min"),
                "束宽": r["params"].get("beam_width"),
                "P95等待": round(r["p95_wait"], 1) if r["served"] else None,
                "发车趟数": r["total_departures"],
                "车辆运行时间": round(r["vehicle_busy_minutes"], 1),
            })
            st.success("已保存（本次会话）")
        else:
            st.warning("请先运行仿真")

    if st.button("🗑️ 清空", use_container_width=True):
        st.session_state.experiments = []
        st.rerun()

with col2:
    if st.session_state.experiments:
        df = pd.DataFrame(st.session_state.experiments)
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.download_button("⬇️ 导出 CSV", df.to_csv(index=False).encode("utf-8-sig"),
                           "experiments.csv", "text/csv", use_container_width=True)
        st.caption("同组算法对比须保持客流签名、车队规模、座位数、速度和场景一致；仅比较已上车者的等待均值可能产生偏差。")
    else:
        st.info("暂无实验记录")

if st.session_state.experiments:
    with st.container(border=True):
        st.subheader("📊 已上车游客等待时间对比")
        df = pd.DataFrame(st.session_state.experiments)
        fig = go.Figure()
        fig.add_trace(go.Bar(name="平均等待", x=df["编号"], y=df["平均等待"], marker_color="#5B8FF9"))
        fig.add_trace(go.Bar(name="P95等待", x=df["编号"], y=df["P95等待"], marker_color="#F6BD16"))
        fig.update_layout(barmode="group", height=350, yaxis_title="分钟")
        st.plotly_chart(fig, use_container_width=True)

st.markdown('<div class="footer-text">⚠️ 所有结果由程序生成，不代表景区实测。</div>', unsafe_allow_html=True)
