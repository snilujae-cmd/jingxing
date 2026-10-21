import streamlit as st
import numpy as np
import plotly.graph_objects as go
from admin_auth import require_admin_page
from core.demand import demand_multiplier, outbound_fraction
from scenario_state import (default_scenario, load_scenario, save_scenario,
                            simulation_scenario_params)
from utils.style import admin_navigation, apply_plotly_theme, page_header, page_surface, section_header

require_admin_page()
page_surface("admin")
admin_navigation("客流场景")

page_header("客流场景", "设置同一组研究参数，用于单次仿真与三策略公平比较。参数自动保存到当前会话。", "ADMIN · SCENARIO")
st.info("基准到达率指 A+B 两线合计每小时待乘车游客数（非每站、非景区总游客数）；所有客流均为仿真假设。")
section_header("场景参数", "先设置基础客流，再按需要启用潮汐与突发情况。")

# 编辑副本；所有控件更新完毕后再一次性保存有效场景。
sc = load_scenario(st.session_state) or default_scenario()

# ============ 场景基础参数 ============
with st.container(border=True):
    st.subheader("① 基础场景")
    sc["type"] = st.radio(
        "客流模式",
        ["平峰", "上午高峰", "下午高峰"],
        horizontal=True,
        index=["平峰", "上午高峰", "下午高峰"].index(sc["type"]),
    )

    col1, col2 = st.columns(2)
    with col1:
        sc["arrival_rate"] = st.slider("基准到达率（人/小时）", 30, 600, sc["arrival_rate"], 10)
    with col2:
        sc["duration_min"] = st.number_input("仿真时长（分钟）", 60, 720, sc["duration_min"], 30)

# ============ 潮汐客流开关 ============
with st.container(border=True):
    st.subheader("② 节假日潮汐客流")
    st.caption("开启后，客流呈现明显的方向切换：上午上山为主，下午下山为主")
    sc["tidal"] = st.checkbox("启用潮汐客流（节假日典型模式）", value=sc["tidal"])

# ============ 突发情况 ============
with st.container(border=True):
    st.subheader("③ 突发情况模拟")
    st.caption("模拟客流突增、骤降等异常事件；‘骤降’的2倍影响表示客流降为原来的1/2")
    sc["disruption"] = st.checkbox("启用突发情况", value=sc["disruption"])

    if sc["disruption"]:
        sc["disruption_type"] = st.selectbox(
            "突发类型",
            ["客流突增", "客流骤降", "双向高峰"],
            index=["客流突增", "客流骤降", "双向高峰"].index(sc["disruption_type"]),
        )
        col1, col2, col3 = st.columns(3)
        with col1:
            sc["disruption_center"] = st.number_input(
                "触发时刻（分钟）", 0, sc["duration_min"], min(sc["disruption_center"], sc["duration_min"]), 15)
        with col2:
            sc["disruption_sigma"] = st.number_input(
                "持续宽度（分钟）", 5, 180, sc["disruption_sigma"], 5)
        with col3:
            is_drop = sc["disruption_type"] == "客流骤降"
            intensity_label = "骤降强度（2 表示降到原来的 1/2）" if is_drop else "影响强度（倍）"
            # 脉冲过中心时: 突增/双向为倍率x，骤降为原来的1/x；避免“骤降”反而增长。
            intensity_now = max(1.0, min(5.0, float(sc["disruption_intensity"])))
            sc["disruption_intensity"] = st.slider(
                intensity_label, 1.0, 5.0, intensity_now, 0.1)

sc["seed"] = st.number_input("随机种子", 0, 9999, sc["seed"])
sc["disruption_center"] = min(sc["disruption_center"], sc["duration_min"])
sc = save_scenario(st.session_state, sc)


# ================================================================
# 核心：生成客流曲线（基础 + 潮汐 + 突发）
# ================================================================
def generate_curve(sc):
    """与core/simulation.py一致的15分钟期望客流曲线；真实生成还会泊松抽样。"""
    t = np.arange(0, sc["duration_min"], 15)
    params = simulation_scenario_params(sc)
    y_up, y_down = [], []
    for minute in t:
        moment = minute + 7.5
        expected_total = params["arrival_rate"] / 4 * demand_multiplier(moment, params)
        outbound = outbound_fraction(moment, params)
        y_up.append(expected_total * outbound)
        y_down.append(expected_total * (1 - outbound))
    return t, np.array(y_up), np.array(y_down)


# ================================================================
# 绘图
# ================================================================
t, y_up, y_down = generate_curve(sc)

with st.container(border=True):
    st.subheader("📈 客流曲线预览")
    st.caption("按 15 分钟计算的模型期望人数；实际仿真使用相同强度模型作泊松抽样，结果可能波动")

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=t, y=y_up, mode="lines+markers",
        name="上行（上山 / 进景区）",
        line=dict(color="#1E6F5C", width=3),
        marker=dict(size=5),
    ))
    fig.add_trace(go.Scatter(
        x=t, y=y_down, mode="lines+markers",
        name="下行（下山 / 出景区）",
        line=dict(color="#C6A15A", width=3),
        marker=dict(size=5),
    ))

    fig.update_layout(
        height=400,
        xaxis_title="时间（分钟）",
        yaxis_title="到达人数 / 15min",
        margin=dict(l=20, r=20, t=30, b=20),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    st.plotly_chart(apply_plotly_theme(fig), use_container_width=True)

    # 峰值信息
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("基准到达率", f"{sc['arrival_rate']} 人/h")
    c2.metric("上行峰值", f"{y_up.max()*4:.0f} 人/h")
    c3.metric("下行峰值", f"{y_down.max()*4:.0f} 人/h")
    c4.metric("期望总到达量", f"{(y_up.sum() + y_down.sum()):.0f} 人")

st.success("✅ 场景已保存，可进入「智能调度控制」页运行仿真")
