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
    st.title("🔐 Admin 管理员登录")
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

    with st.form("admin_login", clear_on_submit=True):
        username = st.text_input("账号")
        password = st.text_input("密码", type="password")
        submitted = st.form_submit_button("登录")
    if submitted:
        if login_admin(username, password):
            st.rerun()
        else:
            st.error("账号或密码错误。")


user_page = st.Page("views/user.py", title="游客出行与仿真回放", icon="📍", default=True)
pages = {"User 游客端": [user_page]}
if is_admin():
    pages["Admin 管理端"] = [
        st.Page("views/0_Admin_Home.py", title="入口说明", icon="🏠"),
        st.Page("views/1_Admin_Dashboard.py", title="调度控制台", icon="🎛️"),
        st.Page("views/2_Admin_Vehicle_Route.py", title="车辆与线路", icon="🚌"),
        st.Page("views/3_Admin_Demand_Scenario.py", title="客流场景", icon="👥"),
        st.Page("views/4_Admin_Smart_Dispatch.py", title="智能调度", icon="🧠"),
        st.Page("views/5_Admin_Simulation_Monitor.py", title="仿真监测", icon="📡"),
        st.Page("views/6_Admin_Experiment_Analysis.py", title="实验分析", icon="📊"),
    ]
pages["管理员账号"] = [st.Page(admin_account_page, title="管理员登录 / 退出", icon="🔐", url_path="admin-login")]

current_page = st.navigation(pages, position="top")
current_page.run()
