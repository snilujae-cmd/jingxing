import streamlit as st
import pandas as pd
from admin_auth import require_admin_page
from data.stations import STATIONS
from data.routes import ROUTES
from data.segments import SEGMENTS
from utils.style import page_header

require_admin_page()

page_header("车辆与线路", "核对 A/B 研究线路、站点顺序及路段参数。公开线路信息与模型估算分别标明。", "ADMIN · NETWORK")

tab1, tab2, tab3 = st.tabs(["📍 站点", "🛤️ 线路", "📏 分段数据"])

with tab1:
    with st.container(border=True):
        st.subheader("站点列表")
        st.dataframe(pd.DataFrame([
            {"编号": k, "名称": v["name"], "线路": v["route"], "类型": v["type"]}
            for k, v in STATIONS.items()
        ]), use_container_width=True, hide_index=True)

with tab2:
    for rid, r in ROUTES.items():
        with st.container(border=True):
            st.subheader(f"{rid} 线 · {r['name']}")
            st.write(f"**站序**：{' → '.join(r['stations'])}")
            distance, service = st.columns(2)
            distance.metric("研究线路长度", f"{r['total_length_km']} km")
            service.metric("参考首末班", f"{r['first_departure']} – {r['last_departure']}")
            st.caption("线路用于本项目科研情景仿真；实际运营请以景区当日公告为准。")

with tab3:
    with st.container(border=True):
        st.subheader("分段距离与时间")
        st.caption("⚠️ 距离为高德地图线路图估算（C类），时间按 20 km/h 理论速度计算")
        st.dataframe(pd.DataFrame([
            {
                "路段": e["edge_id"],
                "线路": e["route"],
                "起点": e["from"],
                "终点": e["to"],
                "距离(km)": e["distance_km"],
                "理论时间(min)": e["travel_time_min"],
                "数据性质": e["status"],
            }
            for e in SEGMENTS
        ]), use_container_width=True, hide_index=True)

st.markdown('<div class="footer-text">⚠️ 距离为估算值，不代表实测道路距离。</div>', unsafe_allow_html=True)
