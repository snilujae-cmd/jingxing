"""方案 B 独立双入口门户。"""

import streamlit as st

from utils.style import page_surface


page_surface("portal")

st.markdown("""
<div class="jx-portal-intro">
  <div class="jx-kicker">景行智调</div>
  <h1>智慧接驳 · 畅游钟山</h1>
  <div class="jx-subtitle">面向景区高峰客流的接驳车智能调度与可视化决策系统</div>
  <p>以南京钟山风景区为研究案例，融合线路查询、客流仿真、智能调度与可视化决策分析。</p>
</div>
""", unsafe_allow_html=True)

visitor, manager = st.columns(2, gap="large")
with visitor:
    with st.container(border=True):
        st.markdown("""
        <div class="jx-entry-card">
          <div class="jx-number">01 / VISITOR</div>
          <h2>游客出行服务</h2>
          <p>看清接驳线路，选择出发地与目的地，查看仿真情景下的路线推荐和候车参考。</p>
        </div>""", unsafe_allow_html=True)
        if st.button("进入游客端 →", type="primary", use_container_width=True):
            st.switch_page("views/user.py")
with manager:
    with st.container(border=True):
        st.markdown("""
        <div class="jx-entry-card">
          <div class="jx-number">02 / ADMIN</div>
          <h2>智能调度管理</h2>
          <p>设置客流与车辆参数，运行调度仿真，比较策略表现并查看共享结果。</p>
        </div>""", unsafe_allow_html=True)
        if st.button("进入管理端 →", type="primary", use_container_width=True):
            st.switch_page("views/admin_login.py")

st.markdown("""
<div class="jx-portal-note">本系统为科研情景仿真与出行辅助演示，不提供景区实时车辆定位或官方调度信息。<br>
背景：流徽榭 · 图片来源：钟山风景名胜区</div>
""", unsafe_allow_html=True)
