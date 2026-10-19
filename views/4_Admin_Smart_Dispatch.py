"""Admin：三策略真正调用同一仿真引擎，并自动生成User端联调CSV。"""
from datetime import datetime
import streamlit as st
import pandas as pd

from admin_auth import assert_admin, require_admin_page
from comparison_data import STRATEGY_LABELS, build_comparison
from core.simulation import run_simulation
from core.exporter import zip_content
from data.vehicles import DEFAULT_FLEET
from scenario_state import load_scenario, simulation_scenario_params
from shared_run_store import publish_result
from utils.style import page_header

require_admin_page()

page_header("智能调度控制", "在同一场景和车队下运行策略，检查结果并向游客发布科研仿真数据。", "ADMIN · DISPATCH")
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
        if not st.session_state.get("shared_publish_error"):
            st.success("本会话上次已成功发布本组三策略比较。游客读取服务器最新成功发布的结果；"
                       "其他管理员后续运行可能覆盖共享包，请以游客刷新后的比较编号为准。")
        rows = []
        for item in st.session_state["comparison"]:
            rows.append({"策略": STRATEGY_LABELS[item["strategy"]], "运行编号": item["run_id"], "总到达": item["total_arrivals"],
                         "已上车": item["served"], "未上车": item["unserved"],
                         "上车服务率(%)": round(item["service_rate"] * 100, 1),
                         "全体观测候车均值(min)": round(item["avg_observed_wait_all"], 2),
                         "已上车P95(min)": round(item["p95_wait"], 2),
                         "发车趟数": item["total_departures"],
                         "客流签名": item["demand_signature"]})
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
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
