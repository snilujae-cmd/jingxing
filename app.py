"""景行智调 · 单网站双入口（Admin / User）统一启动文件。"""
import streamlit as st
from admin_auth import admin_configured, is_admin, login_admin, logout_admin
from utils.style import load_css

st.set_page_config(
    page_title="景行智调 · 景区接驳车仿真",
    page_icon="🚌",
    layout="wide",
    initial_sidebar_state="expanded",
)
load_css()

def admin_account_page() -> None:
    page_header("管理员账号", "管理研究场景、运行调度仿真，并向游客发布已完成的结果。", "景行智调 · ADMIN")
    if is_admin():
        st.success("管理员已登录。")
        st.page_link("views/0_Admin_Home.py", label="进入管理端", icon="🏠")
        if st.button("退出管理员登录"):
            logout_admin()
            st.switch_page("views/user.py")
        return

    if not admin_configured():
        st.error("管理员账号尚未配置；管理端已关闭。请由部署者配置凭据。")
        return

    left, right = st.columns([1, 1.2], gap="large")
    with left:
        with st.form("admin_login", clear_on_submit=True):
            st.subheader("登录调度工作台")
            username = st.text_input("账号")
            password = st.text_input("密码", type="password")
            submitted = st.form_submit_button("登录", type="primary", use_container_width=True)
    with right:
        with st.container(border=True):
            st.subheader("研究仿真工作流程")
            st.write("设置客流场景 → 运行调度策略 → 检查结果 → 发布游客可读结果")
            st.caption("游客可直接使用线路查询与已发布结果，无需管理员账号。")
            st.info("系统未接入景区真实实时运营数据；车辆、排队和调度结果均为科研情景仿真。")
    if submitted:
        if login_admin(username, password):
            st.rerun()
        else:
            st.error("账号或密码错误。")


user_page = st.Page("views/user.py", title="游客出行与仿真回放", icon="📍", default=True)
admin_visibility = "visible" if is_admin() else "hidden"
pages = {"User 游客端": [user_page]}
pages["Admin 管理端"] = [
    st.Page("views/0_Admin_Home.py", title="入口说明", icon="🏠", visibility=admin_visibility),
    st.Page("views/1_Admin_Dashboard.py", title="调度控制台", icon="🎛️", visibility=admin_visibility),
    st.Page("views/2_Admin_Vehicle_Route.py", title="车辆与线路", icon="🚌", visibility=admin_visibility),
    st.Page("views/3_Admin_Demand_Scenario.py", title="客流场景", icon="👥", visibility=admin_visibility),
    st.Page("views/4_Admin_Smart_Dispatch.py", title="智能调度", icon="🧠", visibility=admin_visibility),
    st.Page("views/5_Admin_Simulation_Monitor.py", title="仿真监测", icon="📡", visibility=admin_visibility),
    st.Page("views/6_Admin_Experiment_Analysis.py", title="实验分析", icon="📊", visibility=admin_visibility),
]
pages["管理员账号"] = [st.Page(admin_account_page, title="管理员登录 / 退出", icon="🔐", url_path="admin-login")]

current_page = st.navigation(pages, position="top")
current_page.run()

def page_header(title, subtitle="", eyebrow=None):
    st.title(title)
    if subtitle:
        st.caption(subtitle)
