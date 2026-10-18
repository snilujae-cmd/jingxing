"""景行智调 · 游客端。既能单独测试，也能在未来并入 Admin V1 单网站。"""
from pathlib import Path
import sys

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from user_data_adapter import (DataContractError, load_admin_result,
                               load_run_folder, load_run_zip)
from shared_run_store import load_shared_run, shared_run_path
from route_recommendation import recommend_direct_routes


@st.cache_data(show_spinner=False)
def load_base_data():
    stations = pd.read_csv(ROOT / "data/network_v1/stations.csv", encoding="utf-8-sig")
    stop_order = pd.read_csv(ROOT / "data/network_v1/route_stop_order.csv", encoding="utf-8-sig")
    return stations, stop_order


stations, stop_order = load_base_data()
station_names = stations.set_index("station_id")["station_name"].to_dict()
station_options = [f"{r.station_id} {r.station_name}" for r in stations.itertuples()]
station_map = {f"{r.station_id} {r.station_name}": r.station_id for r in stations.itertuples()}


st.title("🚌 景行智调 · 游客端")
st.caption("⚠️ 所有运行结果均为科研情景仿真，不代表景区实时车辆、真实排队或官方运营数据。")
st.write("选择出行站点、查看线路，或回放不同仿真参数下的车辆和排队情况。")

with st.expander("🗂️ 仿真数据来源 / 切换运行结果", expanded=True):
    in_same_session = st.session_state.get("last_result") is not None
    has_shared_run = shared_run_path().is_file()
    choices = ["最新共享仿真", "内置演示样例", "上传Admin导出的ZIP"]
    mode = st.radio("选择数据来源", choices,
                    index=(0 if has_shared_run or in_same_session else 1), horizontal=True)
    st.caption("共享仿真来自本网站Admin最近一次成功写入的完整结果。其他浏览器或设备打开同一服务器后，"
               "选择此项并刷新页面即可读取；多服务器部署需要配置共同的存储。")
    run = None
    if mode == "最新共享仿真":
        st.button("刷新共享结果")
        try:
            run = load_shared_run(stations)
            if run is None and in_same_session:
                run = load_admin_result(st.session_state["last_result"], stations)
        except (DataContractError, ValueError, KeyError, OSError) as exc:
            st.error(f"读取最新仿真失败：{exc}")
            st.stop()
        if run is None:
            st.info("尚无共享仿真结果。请先在Admin端运行并成功发布，或选择演示样例。")
            st.stop()
    if mode == "上传Admin导出的ZIP":
        uploaded_zip = st.file_uploader("上传Admin端『下载4份联调CSV』生成的ZIP", type=["zip"],
                                        accept_multiple_files=False)
        if uploaded_zip is not None:
            try:
                run = load_run_zip(uploaded_zip.getvalue(), stations)
            except (DataContractError, ValueError, KeyError, OSError) as exc:
                st.error(f"导入失败：{exc}")
                st.stop()
        else:
            st.info("请选择Admin端下载的ZIP。上传后本页面将使用该次仿真数据。")
            st.stop()
    if mode == "内置演示样例":
        demo_root = ROOT / "data/runs"
        sample_folders = sorted(p for p in demo_root.iterdir() if p.is_dir()) if demo_root.exists() else []
        if not sample_folders:
            st.error("找不到内置演示数据文件夹。")
            st.stop()
        try:
            run = load_run_folder(sample_folders[0], stations)
        except (DataContractError, ValueError, OSError) as exc:
            st.error(f"演示数据读取失败：{exc}")
            st.stop()

    st.success(f"当前数据：{run.source_label}｜运行编号：{run.run_id}")
    if run.schema_kind == "admin_v1":
        st.caption("已识别为 Admin V1 输出，自动适配排队方向和载客字段。"
                   "该格式只有车辆最近站点快照，没有路段实时行驶进度，页面不会捏造GPS位置。")
    else:
        st.caption("已识别为 User 原始联调样例。该样例是静态文件，不能随独立Admin网站参数变化自动更新。")

station_state = run.station_state
vehicle_state = run.vehicle_state
passengers = run.passenger_results

# 以数据里的真实快照时刻为准，不再硬编码 0--180 分钟。
all_times = sorted(set(station_state["time_min"].dropna().astype(float)) &
                   set(vehicle_state["time_min"].dropna().astype(float)))
if not all_times:
    st.error("仿真数据缺少站点与车辆共同的时间点，无法播放。")
    st.stop()


def format_t(t):
    # 08:00只是回放演示相对时钟，不是景区真实运营时刻。
    mins = round(8 * 60 + float(t))
    return f"{mins // 60:02d}:{mins % 60:02d}（仿真{t:g}分钟）"


def direction_norm(value):
    if str(value) in ("1", "1.0", "去程", "OUT", "out"):
        return "去程"
    if str(value) in ("-1", "-1.0", "返程", "IN", "in"):
        return "返程"
    return str(value)


def display_minutes(value):
    return round(value, 1) if value is not None else None


default_index = min(range(len(all_times)), key=lambda i: abs(all_times[i] - 60))
t = st.select_slider("选择仿真回放时刻", options=all_times, value=all_times[default_index],
                     format_func=format_t)
st.caption("此时刻仅用于已完成仿真的回放与线路比较，不代表现在的运营时间。")

tab1, tab2, tab3 = st.tabs(["🗺️ 线路拓扑与查询", "⏱️ 仿真回放与候车", "📊 趋势分析"])

with tab1:
    with st.container(border=True):
        st.subheader("线路拓扑示意图")
        dot = """
        digraph {
          rankdir=LR;
          nodesep=0.8;
          node [shape=box, style="rounded,filled", fillcolor="#f0f2f6", fontsize=12];
          N01 [label="N01 地铁钟灵街站"];
          N02 [label="N02 体育公园"];
          N03 [label="N03 灵谷景区（A/B共线）"];
          N04 [label="N04 流徽榭（A/B共线）"];
          N05 [label="N05 孙中山纪念馆"];
          N06 [label="N06 紫金·钟爱里"];
          N01 -> N02 [label="A"];
          N02 -> N03 [label="A"];
          N03 -> N04 [label="A/B"];
          N04 -> N05 [label="A/B"];
          N06 -> N03 [label="B"];
        }
        """
        st.graphviz_chart(dot)
        st.caption("这是站序拓扑图，不是GPS导航图；道路/返程方向尚需核验。")
    with st.container(border=True):
        st.subheader("直达线路比较（仿真回放）")
        c1, c2 = st.columns(2)
        with c1:
            origin_label = st.selectbox("起点", station_options, index=2, key="od_origin")
        with c2:
            dest_label = st.selectbox("终点", station_options, index=4, key="od_dest")
        start, stop = station_map[origin_label], station_map[dest_label]
        if start == stop:
            st.warning("起点和终点相同，请重新选择。")
        else:
            routes = recommend_direct_routes(stop_order, run, start, stop, t)
            if routes:
                rows = []
                for item in routes:
                    rows.append({
                        "线路": item["route_id"], "方向": item["direction"],
                        "下次同OD上车记录间隔(分钟)": display_minutes(item["replay_wait_min"]),
                        "该乘客乘车(分钟)": display_minutes(item["ride_time_min"]),
                        "到该乘客下车共(分钟)": display_minutes(item["total_replay_min"]),
                        "记录情况": "完整仿真记录" if item["total_replay_min"] is not None else "无完整同OD记录",
                    })
                st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
                if routes[0]["total_replay_min"] is not None:
                    st.info(f"按本次仿真中下一名完成该OD行程的乘客记录，{routes[0]['route_id']}线"
                            f"{routes[0]['direction']}的回放总间隔最短。")
                st.caption("比较只使用同一次仿真中完整的同起终点乘客记录。"
                           "空白表示没有可比较记录；不代表实时到站预测或座位保证。"
                           "返程道路与站序仍待核验。")
            else:
                st.info("当前范围内没有支持该OD的直达线路；换乘功能待开发。")

with tab2:
    with st.container(border=True):
        st.subheader("仿真回放控制")
        st.caption(f"当前回放：{format_t(t)}")
        snap = station_state[station_state["time_min"] == t]
        v_snap = vehicle_state[vehicle_state["time_min"] == t]
        arrived = int((passengers["arrival_time_min"] <= t + 1e-9).sum())
        waiting = int(snap["waiting_total"].sum())
        moving = int(v_snap["status"].isin(["moving", "running"]).sum())
        onboard = pd.to_numeric(v_snap["onboard"], errors="coerce")
        capacity = pd.to_numeric(v_snap["capacity"], errors="coerce")
        full = int((onboard >= capacity * .9).sum())
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("当前总排队人数", f"{waiting} 人")
        m2.metric("运行中车辆", f"{moving} 辆")
        m3.metric("高载客车辆（≥90%）", f"{full} 辆")
        m4.metric("截至此刻累计到达", f"{arrived} 人")

    col_wait, col_veh = st.columns([1, 1.15])
    with col_wait:
        with st.container(border=True):
            st.subheader("各站排队")
            if snap.empty:
                st.info("当前时刻无站点快照。")
            else:
                table = snap[["route_id", "station_name", "waiting_forward", "waiting_reverse", "waiting_total"]]
                st.dataframe(table.rename(columns={"route_id": "线路", "station_name": "站点",
                                                     "waiting_forward": "去程", "waiting_reverse": "返程",
                                                     "waiting_total": "排队合计"}),
                             hide_index=True, use_container_width=True)
    with col_veh:
        with st.container(border=True):
            st.subheader("车辆仿真状态快照")
            if v_snap.empty:
                st.info("当前时刻无车辆快照。")
            for row in v_snap.itertuples():
                proportion = max(0., min(1., float(row.onboard) / max(1., float(row.capacity))))
                st.markdown(f"**{row.vehicle_id}**  · {row.route_id}线 · {row.status} · {direction_norm(row.direction)}")
                st.progress(proportion, text=f"载客 {int(row.onboard)}/{int(row.capacity)}")
                dest = getattr(row, "to_station_id", None)
                start = getattr(row, "from_station_id", None)
                progress = getattr(row, "segment_progress", None)
                if pd.notna(dest) and pd.notna(start) and pd.notna(progress) and str(dest) != str(start):
                    st.caption(f"仿真路段：{station_names.get(str(start), start)} → "
                               f"{station_names.get(str(dest), dest)}（进度约{float(progress) * 100:.0f}%）")
                else:
                    st.caption(f"仿真最近记录站点：{row.station_name}。当前数据不提供GPS或路段精确进度。")
                st.divider()

    with st.container(border=True):
        st.subheader("同OD候车记录（仿真回放）")
        st.caption("依据完整仿真中同起终点乘客的上车与下车记录比较；不是实时班次预测，也不保证有座位。")
        c1, c2 = st.columns(2)
        with c1:
            wo = station_map[st.selectbox("候车起点", station_options, index=2, key="wait_start")]
        with c2:
            wd = station_map[st.selectbox("乘车终点", station_options, index=4, key="wait_end")]
        if st.button("查询后续上车记录"):
            if wo == wd:
                st.warning("起终点相同。")
            else:
                routes = recommend_direct_routes(stop_order, run, wo, wd, t)
                if not routes:
                    st.info("无可用直达线路。")
                else:
                    observed = [item for item in routes if item["replay_wait_min"] is not None]
                    if observed:
                        rows = [{"线路": item["route_id"], "方向": item["direction"],
                                 "同OD上车记录间隔(分钟)": round(item["replay_wait_min"], 1),
                                 "该乘客乘车(分钟)": round(item["ride_time_min"], 1)}
                                for item in observed]
                        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
                        st.caption("这些是已完成模拟中后续乘客的历史记录，不能保证新乘客同样时间上车。")
                    else:
                        st.info("当前时刻之后没有完整的同OD乘车记录，无法提供候车参考。")

with tab3:
    with st.container(border=True):
        st.subheader("各站点排队人数趋势")
        trends = station_state.pivot_table(index="time_min", columns=["route_id", "station_name"],
                                          values="waiting_total", aggfunc="sum", fill_value=0)
        trends.columns = [f"{r}线·{s}" for r, s in trends.columns]
        st.line_chart(trends, height=450)
        st.caption(f"当前回放时间范围：{min(all_times):g}～{max(all_times):g}分钟；"
                   "曲线数据来自当前选择的同一次仿真，不同参数会产生不同结果。")
