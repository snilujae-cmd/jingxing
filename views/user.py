"""景行智调 · 游客端。既能单独测试，也能在未来并入 Admin V1 单网站。"""
from datetime import datetime
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

import pandas as pd
import plotly.express as px
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from user_data_adapter import (DataContractError, load_admin_result,
                               load_run_folder, load_run_zip)
from shared_run_store import load_shared_bundle, shared_run_path
from route_recommendation import recommend_direct_routes
from utils.media import asset_download, render_image
from utils.style import apply_plotly_theme


@st.cache_data(show_spinner=False)
def load_base_data():
    stations = pd.read_csv(ROOT / "data/network_v1/stations.csv", encoding="utf-8-sig")
    stop_order = pd.read_csv(ROOT / "data/network_v1/route_stop_order.csv", encoding="utf-8-sig")
    return stations, stop_order


stations, stop_order = load_base_data()
station_names = stations.set_index("station_id")["station_name"].to_dict()
station_options = [f"{r.station_id} {r.station_name}" for r in stations.itertuples()]
station_map = {f"{r.station_id} {r.station_name}": r.station_id for r in stations.itertuples()}


hero_text, hero_photo = st.columns([1.05, 1.35], gap="large", vertical_alignment="center")
with hero_text:
    st.caption("南京钟山风景区 · 接驳出行科研仿真")
    st.title("景行智调·游客出行助手")
    st.write("把线路看清楚，让游览更从容。查找研究线路与站点，回看接驳车仿真，了解不同调度策略下的候车情况。")
    st.caption("线路查询 · 仿真回放 · 趋势分析与已发布策略比较")
with hero_photo:
    render_image("liuhuixie", caption="流徽榭 · 图片来源：钟山风景区")
st.info("科研情景仿真：车辆、排队、候车与策略比较均来自模拟结果，不代表景区真实实时运营数据或官方调度信息。")

published_comparison = None
comparison_error = None
with st.expander("仿真数据来源与运行切换", expanded=False):
    in_same_session = st.session_state.get("last_result") is not None
    has_shared_run = shared_run_path().is_file()
    choices = ["最新共享仿真", "内置演示样例", "上传Admin导出的ZIP"]
    mode = st.radio("选择数据来源", choices,
                    index=(0 if has_shared_run or in_same_session else 1),
                    horizontal=True, key="user_data_source")
    st.caption("共享仿真来自本网站Admin最近一次成功写入的完整结果。其他浏览器或设备打开同一服务器后，"
               "选择此项并刷新页面即可读取；多服务器部署需要配置共同的存储。")
    run = None
    if mode == "最新共享仿真":
        st.button("刷新共享结果", help="重新读取服务器最近一次成功发布的完整结果及同次比较。")
        try:
            # 一次读取同一个原子发布包，避免四份CSV与比较元数据跨发布混用。
            bundle = load_shared_bundle(stations)
            if bundle is not None:
                run = bundle.run
                published_comparison = bundle.comparison
                comparison_error = bundle.comparison_error
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

with st.container(border=True):
    st.caption("当前读取的已完成仿真")
    st.markdown(f"**{run.source_label}**")
    st.caption(f"运行编号：{run.run_id}")
    if run.schema_kind == "admin_v1":
        st.caption("Admin 仿真输出已适配排队方向和载客字段。车辆位置为最近站点快照，不提供实时 GPS。")
    else:
        st.caption("当前为静态联调样例，不能随独立 Admin 网站参数变化自动更新。")
    if comparison_error:
        st.warning(f"已发布比较结果校验未通过，仅展示有效的单次仿真：{comparison_error}")

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
with st.container(border=True):
    t = st.select_slider("选择仿真回放时刻", options=all_times, value=all_times[default_index],
                         format_func=format_t)
    st.caption("此控件同时影响线路查询中的历史记录比较与仿真回放；08:00为相对演示时钟，不代表景区实际运营时刻。")

tab1, tab2, tab3 = st.tabs(["线路查询", "仿真回放与候车", "趋势分析与策略比较"])

with tab1:
    st.subheader("先了解线路，再选择出发站点")
    st.caption("研究范围为 A、B 两条接驳线路。地图提供景区总体参考；可查询站点以系统研究站序为准。")
    line_a, line_b = st.columns(2)
    with line_a, st.container(border=True):
        st.markdown("**A 线 · 5 个研究站点**")
        st.write("地铁钟灵街站 → 体育公园 → 灵谷景区 → 流徽榭 → 孙中山纪念馆")
    with line_b, st.container(border=True):
        st.markdown("**B 线 · 4 个研究站点**")
        st.write("紫金·钟爱里 → 灵谷景区 → 流徽榭 → 孙中山纪念馆")

    with st.container(border=True):
        st.subheader("景区观光车线路总览")
        render_image("routes", caption="图片来源：钟山风景区/公开资料 · 保留完整图例与文字；仅供研究参考")
        original_map = asset_download("routes")
        if original_map is not None:
            st.download_button("下载线路原图，放大查看", data=original_map,
                               file_name="钟山风景区_观光车线路图.jpg", mime="image/jpeg",
                               key="user_route_map_download")
        st.caption("该图包含景区其他线路，不能视为本系统 A/B 研究线路的实时运营承诺。出行请以景区现行公告为准。")

    with st.expander("查看 A/B 研究站序拓扑与说明", expanded=False):
        dot = """
        digraph {
          rankdir=LR;
          nodesep=0.8;
          graph [bgcolor="transparent"];
          node [shape=box, style="rounded,filled", fillcolor="#E4F1E9", color="#B8D3C7", fontcolor="#1F2D3D", fontsize=12];
          edge [color="#1E6F5C", fontcolor="#1E6F5C"];
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
        st.subheader("选择起终点 · 比较直达线路")
        st.caption(f"比较时间：{format_t(t)}；数据来自运行 {run.run_id}。")
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

    st.subheader("沿线景点")
    st.caption("照片用于认识沿线景点，查询站点保持现有 A/B 模型范围。图片来源钟山风景区。")
    for column, key, title, note in zip(
        st.columns(4),
        ("sports", "linggu", "liuhuixie", "memorial"),
        ("钟山体育公园", "灵谷寺", "流徽榭", "孙中山纪念馆"),
        ("对应研究站点：体育公园", "灵谷景区内景点；查询选择灵谷景区", "A/B 研究线路共线站点", "A/B 研究线路共线站点"),
    ):
        with column, st.container(border=True):
            render_image(key)
            st.markdown(f"**{title}**")
            st.caption(note)

    with st.expander("景区其他游览参考", expanded=False):
        st.caption("美龄宫、紫金山天文台不在本系统 A/B 研究站序内；以下照片仅供认识景区，不构成直达线路推荐。")
        for column, key, title in zip(st.columns(2), ("meiling", "observatory"), ("美龄宫", "紫金山天文台")):
            with column, st.container(border=True):
                render_image(key, caption=f"{title} · 图片来源：钟山风景区")
                st.markdown(f"**{title}**")
                st.caption("其他游览参考 · 不在当前 A/B 可查询站序内")

with tab2:
    with st.container(border=True):
        st.subheader("这一刻的接驳仿真")
        st.caption(f"当前回放：{format_t(t)} · 运行编号：{run.run_id}")
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
        st.caption("总排队为站点快照合计；运行中仅统计 moving/running 状态；高载客车辆指载客量达到座位数的 90%。")

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
    st.subheader("本次仿真的排队变化")
    with st.container(border=True):
        st.subheader("各站点排队人数趋势")
        trends = station_state.pivot_table(index="time_min", columns=["route_id", "station_name"],
                                          values="waiting_total", aggfunc="sum", fill_value=0)
        trends.columns = [f"{r}线·{s}" for r, s in trends.columns]
        trend_data = trends.rename_axis("仿真时刻（分钟）").reset_index().melt(
            id_vars="仿真时刻（分钟）", var_name="线路与站点", value_name="排队人数")
        trend_figure = px.line(trend_data, x="仿真时刻（分钟）", y="排队人数", color="线路与站点")
        apply_plotly_theme(trend_figure)
        st.plotly_chart(trend_figure, use_container_width=True)
        st.caption(f"当前回放时间范围：{min(all_times):g}～{max(all_times):g}分钟；"
                   f"曲线来自当前运行 {run.run_id}，不同参数会产生不同结果。")

    st.subheader("Admin 已发布的三策略比较")
    st.caption("游客只读查看已完成并发布的比较组；后台参数设置和调度执行仍由管理员操作。")
    if published_comparison is None:
        if comparison_error:
            st.info("当前比较资料未通过校验，已保留上方单次仿真趋势。请等待管理员重新发布完整比较。")
        elif mode != "最新共享仿真":
            st.info("演示样例与上传的单次仿真 ZIP 不提供已发布比较。选择「最新共享仿真」后刷新，可读取管理员发布的三策略结果。")
        else:
            st.info("当前共享结果没有已发布的三策略比较。管理员完成同场景三策略比较并发布后，点击「刷新共享结果」即可查看。")
    else:
        comparison = published_comparison
        strategy_names = {"fixed": "固定调度", "dynamic": "动态阈值调度", "optimized": "滚动预测优化"}
        strategy_colors = {"固定调度": "#709B8D", "动态阈值调度": "#C6A15A", "滚动预测优化": "#1E6F5C"}
        st.success("已读取完整比较组，三策略使用一致的场景、客流与车队条件。")
        published_local = datetime.fromisoformat(comparison["published_at"]).astimezone(ZoneInfo("Asia/Shanghai"))
        st.caption(f"比较编号：{comparison['comparison_id']} · 发布时间：{published_local:%Y-%m-%d %H:%M:%S}（北京时间）")
        st.caption(f"关联单次回放：{comparison['selected_run_id']} · 随机种子：{comparison['seed']}")
        comparison_params = comparison["params"]
        fleet_text = "、".join(f"{route} 线 {count} 辆" for route, count in comparison_params["fleet"].items())
        with st.container(border=True):
            st.markdown("**这组比较使用的研究场景**")
            st.write(f"{comparison_params['scenario_type']} · 仿真 {comparison_params['duration_min']:g} 分钟 · "
                     f"A+B 两线基准到达率 {comparison_params['arrival_rate']:g} 人/小时")
            st.write(f"假设车队：{fleet_text}；假设车速：{comparison_params.get('speed_kmh', '未记录')} km/h。")
            st.caption(f"潮汐客流：{'开启' if comparison_params.get('tidal') else '关闭'}；"
                       f"突发情况：{comparison_params.get('disruption_type', '开启') if comparison_params.get('disruption') else '关闭'}。"
                       "这些是已完成运行的固定输入，后台尚未执行的参数修改不会改变这组结果。")
        comparison_rows, queue_rows = [], []
        for item in comparison["strategies"]:
            metrics = item["metrics"]
            name = strategy_names.get(item["strategy"], item["strategy"])
            comparison_rows.append({
                "策略": name, "运行编号": item["run_id"],
                "全体观测候车均值（分钟）": metrics["avg_observed_wait_all"],
                "已上车平均候车（分钟）": metrics["avg_wait"],
                "已上车 P95 候车（分钟）": metrics["p95_wait"],
                "上车服务率（%）": metrics["service_rate"] * 100,
                "期末未上车（人）": metrics["unserved"],
                "总到达（人）": metrics["total_arrivals"],
                "发车趟数": metrics["total_departures"],
            })
            queue_rows.extend({"仿真时刻（分钟）": point["time_min"], "总排队人数": point["waiting_total"],
                               "策略": name} for point in item["queue_series"])
        comparison_table = pd.DataFrame(comparison_rows)
        st.dataframe(comparison_table.round(2), hide_index=True, use_container_width=True)
        with st.expander("完整场景参数与校验记录（备查）", expanded=False):
            st.json({"comparison_id": comparison["comparison_id"],
                     "published_at": comparison["published_at"],
                     "selected_run_id": comparison["selected_run_id"],
                     "seed": comparison["seed"], "demand_signature": comparison["demand_signature"],
                     "params": comparison["params"],
                     "strategy_runs": [{"strategy": item["strategy"], "run_id": item["run_id"]}
                                       for item in comparison["strategies"]]})
        wait_col, service_col = st.columns(2)
        with wait_col, st.container(border=True):
            st.markdown("**全体到达游客的观测候车**")
            wait_figure = px.bar(comparison_table, x="策略", y="全体观测候车均值（分钟）", color="策略",
                                 color_discrete_map=strategy_colors)
            apply_plotly_theme(wait_figure)
            wait_figure.update_layout(showlegend=False)
            st.plotly_chart(wait_figure, use_container_width=True)
        with service_col, st.container(border=True):
            st.markdown("**截至仿真结束的上车服务率**")
            service_figure = px.bar(comparison_table, x="策略", y="上车服务率（%）", color="策略",
                                    color_discrete_map=strategy_colors)
            apply_plotly_theme(service_figure)
            service_figure.update_layout(showlegend=False)
            service_figure.update_yaxes(range=[0, 100])
            st.plotly_chart(service_figure, use_container_width=True)
        with st.container(border=True):
            st.markdown("**三策略总排队人数趋势**")
            queue_figure = px.line(pd.DataFrame(queue_rows), x="仿真时刻（分钟）", y="总排队人数", color="策略",
                                   color_discrete_map=strategy_colors)
            apply_plotly_theme(queue_figure)
            st.plotly_chart(queue_figure, use_container_width=True)
        st.caption("均值与 P95 的已上车口径只计算已上车游客；全体观测候车对未上车者仅计至仿真结束。"
                   "服务率与期末排队应结合发车趟数理解，不能仅凭一个指标宣称某策略最优。"
                   "表格与曲线均来自以上已发布比较组，不因当前回放时刻或后台未运行的输入修改而改变。")
