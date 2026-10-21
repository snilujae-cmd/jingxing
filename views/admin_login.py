"""方案 B 管理端登录页；认证委托原有 admin_auth。"""

import streamlit as st

from admin_auth import admin_configured, is_admin, login_admin, logout_admin
from utils.style import page_surface


page_surface("login")
if st.button("← 返回平台首页"):
    st.switch_page("views/portal.py")
st.markdown("""
<div class="jx-login-intro">
  <div>景行智调 · 智能调度管理平台</div>
  <h1>客流情景建模、运力配置、<br>调度仿真与可视化决策</h1>
</div>
""", unsafe_allow_html=True)

left, right = st.columns([1, 1.2], gap="large")
with left:
    with st.container(border=True):
        st.markdown('<div class="jx-login-card"><h2>管理员登录</h2>'
                    '<p>请使用已配置的管理账号进入工作台。</p></div>',
                    unsafe_allow_html=True)
        if is_admin():
            st.success("管理员已登录。")
            if st.button("进入管理工作台 →", type="primary", use_container_width=True):
                st.switch_page("views/0_Admin_Home.py")
            if st.button("退出管理员登录", use_container_width=True):
                logout_admin()
                st.switch_page("views/portal.py")
        elif not admin_configured():
            st.error("管理员账号尚未配置；管理端已关闭。请由部署者配置凭据。")
        else:
            with st.form("admin_login", clear_on_submit=True):
                username = st.text_input("管理员账号")
                password = st.text_input("登录密码", type="password")
                submitted = st.form_submit_button("登录管理工作台 →", type="primary",
                                                  use_container_width=True)
            if submitted:
                if login_admin(username, password):
                    st.switch_page("views/0_Admin_Home.py")
                else:
                    st.error("账号或密码不正确，请重新输入。")
with right:
    st.markdown("""
    <div class="jx-login-intro">
      <p>管理端仅用于科研情景仿真、结果分析和共享发布，不代表真实景区运营控制台。</p>
      <small>背景：林荫道路 · 原图水印署名「钟山风景名胜区」；素材由用户提供。</small>
    </div>""", unsafe_allow_html=True)
