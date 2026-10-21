"""Admin：三策略真正调用同一仿真引擎，并自动生成User端联调CSV。"""
from datetime import datetime
import streamlit as st
import pandas as pd
import plotly.express as px

from admin_auth import assert_admin, require_admin_page
from comparison_data import STRATEGY_LABELS, build_comparison
from core.simulation import run_simulation
from core.exporter import zip_content
from data.vehicles import DEFAULT_FLEET
from scenario_state import load_scenario, simulation_scenario_params
from shared_run_store import publish_result
from utils.style import admin_navigation, apply_plotly_theme, page_header, page_surface

require_admin_page()
page_surface("admin")
admin_navigation("智能调度")

page_header("智能调度", "本模块基于同一仿真模型，开展单策略运行及同场景三策略比较。", "ADMIN · DISPATCH")
st.caption("固定间隔 / 排队阈值 / 滚动预测优化：三策略均真实调用同一离散事件引擎")
st.warning("本项目仅为情景仿真：车队规模、双向原路折返、逐站客流均属假设，不代表景区运营事实。")

if "fleet" not in st.session_state:
    st.session_state.fleet = dict(DEFAULT_FLEET)
sc = load_scenario(st.session_state)

with st.container(border=True):
    st.subheader("① 车队配置")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.session_state.fleet["A"] = int(st.number_input(
            "A线车辆数", min_value=0, max_value=30,
            value=int(st.session_state.fleet["A"]), step=1))
    with col2:
        st.session_state.fleet["B"] = int(st.number_input(
            "B线车辆数", min_value=0, max_value=30,
            value=int(st.session_state.fleet["B"]), step=1))
    with col3:
        capacity = st.selectbox("假设单车座位数", [22, 36, 40], index=1)

with st.container(border=True):
    st.subheader("② 调度策略")
    display = st.radio("选择策略", ["固定调度", "动态阈值调度", "滚动预测优化"], horizontal=True)
    strategy = {"固定调度": "fixed", "动态阈值调度": "dynamic", "滚动预测优化": "optimized"}[display]
    c1, c2, c3 = st.columns(3)
    with c1:
        fixed_interval = st.slider("固定发车间隔（分钟）", 10, 30, 17)
    with c2:
        queue_threshold = st.slider("动态调度排队阈值（人）", 5, 100, 20, 5)
    with c3:
        speed = st.slider("假设行驶速度（km/h）", 5, 20, 15)
    with st.expander("⚙️ 滚动预测优化参数", expanded=(strategy == "optimized")):
        c1, c2, c3 = st.columns(3)
        with c1:
            step = st.slider("决策间隔（分钟）", 5, 30, 5, 5)
        with c2:
            horizon = st.slider("预测窗口（分钟）", 15, 120, 30, 15)
        with c3:
            beam = st.slider("束搜索宽度", 2, 15, 4)

params = None
seed = None
if sc is not None:
    params = {
        **simulation_scenario_params(sc),
        "fleet": dict(st.session_state.fleet),
        "vehicle_capacities": {rid: [capacity] * n for rid, n in st.session_state.fleet.items()},
        "speed_kmh": speed,
        "fixed_interval": fixed_interval,
        "queue_threshold": queue_threshold,
        "decision_interval_min": step,
        "prediction_horizon_min": horizon,
        "beam_width": beam,
        "snapshot_interval_min": 5,
    }
    seed = sc["seed"]
    st.success(f"已读取客流场景：{sc['type']}，基准到达率 {sc['arrival_rate']} 人/小时，"
               f"仿真时长 {sc['duration_min']} 分钟。")
else:
    st.warning("尚未保存有效客流场景。请先进入「客流场景」页面设置参数。")

st.caption("运行完成后自动发布所选策略的四份CSV；选择「同场景比较三策略」还会发布同组比较指标和排队曲线。"
           "再次运行单次策略将替换共享数据，并移除上一组比较，避免不同运行混用。")
left, right = st.columns(2)
with left:
    run_one = st.button("▶️ 运行所选策略", type="primary", use_container_width=True,
                        disabled=sc is None)
with right:
    run_compare = st.button("📊 同场景比较三策略", use_container_width=True,
                            disabled=sc is None)

if run_one or run_compare:
    try:
        assert_admin()
        if params is None or seed is None:
            raise ValueError("请先保存有效客流场景")
        with st.spinner("仿真计算中……"):
            if run_one:
                result = run_simulation(params, strategy=strategy, seed=seed)
                st.session_state["last_result"] = result
                st.session_state["result"] = result  # 兼容历史页面
                st.session_state.pop("comparison", None)
            else:
                results = [run_simulation(params, strategy=s, seed=seed)
                           for s in ("fixed", "dynamic", "optimized")]
                if len({r["demand_signature"] for r in results}) != 1:
                    raise RuntimeError("不同策略没有共享同一客流，比较中止")
                st.session_state["comparison"] = results
                selected = {r["strategy"]: r for r in results}[strategy]
                st.session_state["last_result"] = selected
                st.session_state["result"] = selected
            st.session_state["last_run_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            try:
                publish_result(st.session_state["last_result"],
                               comparison_results=st.session_state.get("comparison") if run_compare else None)
                st.session_state.pop("shared_publish_error", None)
            except (OSError, ValueError) as exc:
                st.session_state["shared_publish_error"] = str(exc)
    except (ValueError, RuntimeError) as e:
        st.error(f"仿真失败，未更新历史结果：{e}")

if st.session_state.get("shared_publish_error"):
    st.warning("本次仿真已在当前浏览器完成，但共享结果写入失败；其他设备仍可能看到旧结果。"
               f"错误：{st.session_state['shared_publish_error']}")

if "last_result" in st.session_state:
    r = st.session_state["last_result"]
    st.success(f"✅ 已完成仿真（当前查看 {r['strategy']}；运行编号：{r['run_id']}）")
    if st.session_state.get("last_run_time") and not st.session_state.get("shared_publish_error"):
        st.success("已成功共享结果。游客端可刷新最新共享仿真查看同一运行编号。")
    st.caption(f"结果对应运行参数：A线 {r['params']['fleet']['A']} 辆，B线 {r['params']['fleet']['B']} 辆，"
               f"总到达率基准 {r['params']['arrival_rate']} 人/小时；结果不会随输入修改自动更新，请重新运行。")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("已上车游客的平均候车", f"{r['avg_wait']:.1f} min")
    c2.metric("已上车游客P95候车", f"{r['p95_wait']:.1f} min")
    c3.metric("仿真末仍未上车", f"{r['unserved']} 人")
    c4.metric("上车服务率", f"{r['service_rate']*100:.1f}%")
    st.info(f"到达 {r['total_arrivals']} 人；已上车 {r['served']} 人（其中已下车 {r['completed']} 人、"
            f"仍在车上 {r['onboard_end']} 人）；发车 {r['total_departures']} 趟。"
            "均值/P95基于已上车游客，全体到达游客的观测候车均值为 "
            f"{r['avg_observed_wait_all']:.1f} 分钟（未上车者仅计至仿真结束）。")
    if "comparison" in st.session_state:
        st.subheader("同一客流/同一车队：三策略对比")
        comparison = build_comparison(st.session_state["comparison"], r)
        st.caption(f"比较编号：{comparison['comparison_id']} · 随机种子：{comparison['seed']} · "
                   f"客流签名：{comparison['demand_signature']}")
        compared_params = comparison["params"]
        fleet_description = "、".join(
            f"{route}线 {count} 辆" for route, count in compared_params["fleet"].items())
        st.info(
            f"比较条件一致：客流场景 {compared_params['scenario_type']}、随机种子 {comparison['seed']}、"
            f"车队 {fleet_description}、仿真时长 {compared_params['duration_min']:g} 分钟。"
            "固定调度、动态阈值调度和滚动预测优化均使用同一客流签名与同一组参数。"
        )
        if not st.session_state.get("shared_publish_error"):
            st.success("本会话上次已成功发布本组三策略比较。游客读取服务器最新成功发布的结果；"
                       "其他管理员后续运行可能覆盖共享包，请以游客刷新后的比较编号为准。")
        rows, queue_rows = [], []
        for item in comparison["strategies"]:
            metrics = item["metrics"]
            label = STRATEGY_LABELS[item["strategy"]]
            rows.append({
                "策略": label, "运行编号": item["run_id"],
                "总到达（人）": metrics["total_arrivals"], "已上车（人）": metrics["served"],
                "已上车平均候车（分钟）": round(metrics["avg_wait"], 2),
                "已上车 P95 候车（分钟）": round(metrics["p95_wait"], 2),
                "上车服务率（%）": round(metrics["service_rate"] * 100, 1),
                "期末未上车（人）": metrics["unserved"],
                "全体观测候车均值（分钟）": round(metrics["avg_observed_wait_all"], 2),
                "发车趟数": metrics["total_departures"],
            })
            queue_rows.extend({
                "仿真时刻（分钟）": point["time_min"],
                "总排队人数": point["waiting_total"], "策略": label,
            } for point in item["queue_series"])
        comparison_table = pd.DataFrame(rows)
        st.dataframe(comparison_table, hide_index=True, use_container_width=True)
        chart_left, chart_right = st.columns(2)
        with chart_left, st.container(border=True):
            st.markdown("**已上车游客的候车时间**")
            wait_chart = px.bar(comparison_table, x="策略",
                                y=["已上车平均候车（分钟）", "已上车 P95 候车（分钟）"],
                                barmode="group", labels={"value": "分钟", "variable": "指标"})
            st.plotly_chart(apply_plotly_theme(wait_chart), use_container_width=True)
        with chart_right, st.container(border=True):
            st.markdown("**上车服务率与期末未上车人数**")
            service_chart = px.bar(comparison_table, x="策略", y="上车服务率（%）",
                                   color="策略")
            service_chart.update_yaxes(range=[0, 100])
            st.plotly_chart(apply_plotly_theme(service_chart), use_container_width=True)
            st.caption("期末未上车人数及发车趟数见上方同组结果表。")
        with st.container(border=True):
            st.markdown("**三策略总排队人数趋势**")
            queue_chart = px.line(pd.DataFrame(queue_rows), x="仿真时刻（分钟）",
                                  y="总排队人数", color="策略")
            st.plotly_chart(apply_plotly_theme(queue_chart), use_container_width=True)
        top_service = max(rows, key=lambda item: item["上车服务率（%）"])
        if sum(item["上车服务率（%）"] == top_service["上车服务率（%）"] for item in rows) == 1:
            st.info(
                f"在本场景、当前参数下，{top_service['策略']}策略在上车服务率指标上表现较好"
                f"（{top_service['上车服务率（%）']:.1f}%）。"
                "请同时对照候车时间、期末未上车人数和发车趟数。"
            )
        else:
            st.info("在本场景、当前参数下，三策略的最高上车服务率出现并列；"
                    "请结合候车时间、期末未上车人数和发车趟数解读。")
        st.caption("已上车平均候车及 P95 仅统计已上车游客；全体观测候车对期末未上车者仅计至仿真结束。"
                   "图表与表格均来自本次已验证的三策略比较组，不与其他运行编号混用。")
        st.caption("优化器是束搜索近似MPC。发车趟数不同，效果比较需同时考虑运营成本，不能仅凭候车时间宣称最优。")

    st.subheader("📦 同次仿真结果导出")
    st.download_button("⬇️ 下载4份联调CSV（ZIP）", data=zip_content(r),
                       file_name=f"jingxing_user_data_{r['run_id']}.zip",
                       mime="application/zip", use_container_width=True)
    st.caption("ZIP包含 od_flow.csv、station_state.csv、vehicle_state.csv、passenger_results.csv；"
               "全部来自当前同一次仿真。请在接入既有User端前核对表头，不会覆盖昨天的样例文件。")
else:
    if sc is not None:
        st.info("客流场景已就绪；尚未运行仿真。")
