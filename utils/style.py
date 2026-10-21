"""Shared visual helpers. These helpers never read or change simulation state."""

from html import escape

import streamlit as st


COLORS = ["#1E6F5C", "#C6A15A", "#5B8497", "#8B75A5", "#D38365", "#719F8D"]
FONT_FAMILY = '"PingFang SC", "Microsoft YaHei", "Noto Sans CJK SC", sans-serif'


def load_css():
    st.markdown("""
    <style>
    :root { --jx-green:#1E6F5C; --jx-ink:#1F2D3D; --jx-muted:#62756C;
            --jx-line:#DEE7E2; --jx-soft:#E4F1E9; }
    html, body, [data-testid="stApp"] {
        font-family:"PingFang SC","Microsoft YaHei","Noto Sans CJK SC",sans-serif;
    }
    [data-testid="stAppViewContainer"] { background-color:#F7F9F8; }
    .block-container { max-width:1440px; padding-top:2rem; padding-bottom:3rem; }
    h1, h2, h3 { letter-spacing:-0.025em; color:#173F35; }
    h1 { font-size:2rem !important; line-height:1.35 !important; }
    h2 { font-size:1.5rem !important; }
    h3 { font-size:1.15rem !important; }
    .jx-page-header { margin:0.25rem 0 1.6rem; padding-bottom:1.35rem;
                      border-bottom:1px solid var(--jx-line); }
    .jx-eyebrow { color:var(--jx-green); font-size:.76rem; font-weight:700;
                  letter-spacing:.12em; margin-bottom:.55rem; }
    .jx-page-header h1 { margin:0 0 .5rem !important; padding:0 !important; }
    .jx-page-header p { color:var(--jx-muted); margin:0; line-height:1.8; max-width:960px; }
    .jx-section-header { margin:1.15rem 0 .8rem; }
    .jx-section-header h2 { font-size:1.15rem !important; margin:0 0 .25rem; padding:0; }
    .jx-section-header p { color:var(--jx-muted); margin:0; font-size:.9rem; line-height:1.7; }
    .main-title { font-size:2.2rem; font-weight:700; color:var(--jx-green); }
    .sub-title { font-size:1rem; color:var(--jx-muted); margin-bottom:1rem; }
    [data-testid="stVerticalBlockBorderWrapper"] > div,
    [data-testid="stLayoutWrapper"] > [data-testid="stVerticalBlock"],
    [data-testid="stMetric"] {
        border-color:var(--jx-line) !important; border-radius:14px !important;
        background-color:#FFFFFF;
    }
    [data-testid="stMetric"] { border:1px solid var(--jx-line); padding:1.05rem 1.15rem; }
    [data-testid="stMetricLabel"] { color:var(--jx-muted); font-size:.88rem; }
    [data-testid="stMetricValue"] { font-size:1.7rem; color:var(--jx-green); font-weight:700; }
    [data-testid="stMetricDelta"] { font-size:.8rem; }
    [data-testid="stButton"] > button, [data-testid="stDownloadButton"] > button,
    [data-testid="stFormSubmitButton"] > button { border-radius:9px; font-weight:600; min-height:2.65rem; }
    [data-testid="stButton"] > button:focus-visible,
    [data-testid="stDownloadButton"] > button:focus-visible { outline:3px solid #A4CFBA; outline-offset:2px; }
    [data-baseweb="tab-list"] { gap:1rem; border-bottom:1px solid var(--jx-line); }
    [data-baseweb="tab"] { padding-left:.2rem; padding-right:.2rem; font-weight:600; }
    [data-testid="stAlert"] { border-radius:10px; }
    [data-testid="stAlertContainer"]:has([data-testid="stAlertContentInfo"]) {
        background-color:#E4F1E9; color:#173F35;
    }
    [data-testid="stDataFrame"] { border-radius:10px; }
    [data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p {
        color:var(--jx-muted); line-height:1.65;
    }
    .footer-text { color:var(--jx-muted); font-size:.82rem; text-align:center;
                   margin-top:2rem; border-top:1px solid var(--jx-line); padding-top:1rem; }
    .jx-portal-intro { max-width:870px; margin:6vh auto 2.2rem; text-align:center;
                       color:#fff; text-shadow:0 2px 18px rgba(0,0,0,.32); }
    .jx-portal-intro .jx-kicker { font-size:.9rem; letter-spacing:.28em; font-weight:700; }
    .jx-portal-intro h1 { color:#fff !important; font-size:clamp(2.5rem,5vw,4.6rem) !important;
                          letter-spacing:.06em; margin:.5rem 0 .9rem; }
    .jx-portal-intro .jx-subtitle { font-size:clamp(1.1rem,2vw,1.4rem); font-weight:600; }
    .jx-portal-intro p { line-height:1.8; }
    .jx-entry-card h2, .jx-admin-card h3 { color:#123d32 !important; margin:.25rem 0 .8rem; }
    .jx-entry-card p, .jx-admin-card p { color:#43594e; line-height:1.8; min-height:4.4rem; }
    .jx-entry-card .jx-number, .jx-admin-card .jx-number { color:#1e6f5c; font-size:.8rem;
        letter-spacing:.14em; font-weight:800; }
    [data-testid="stVerticalBlockBorderWrapper"]:has(.jx-entry-card) {
        background:rgba(252,253,249,.88) !important; border:1px solid rgba(255,255,255,.88) !important;
        box-shadow:0 18px 46px rgba(7,30,24,.22); padding:1.5rem !important;
        min-height:270px; backdrop-filter:blur(16px); -webkit-backdrop-filter:blur(16px);
        transition:transform .22s ease,box-shadow .22s ease;
    }
    [data-testid="stVerticalBlockBorderWrapper"]:has(.jx-admin-card) {
        background:rgba(255,255,252,.92) !important; border:1px solid rgba(215,229,218,.95) !important;
        box-shadow:0 10px 28px rgba(19,62,49,.1); min-height:205px;
        transition:transform .22s ease,box-shadow .22s ease;
    }
    [data-testid="stVerticalBlockBorderWrapper"]:has(.jx-entry-card):hover,
    [data-testid="stVerticalBlockBorderWrapper"]:has(.jx-admin-card):hover {
        transform:translateY(-4px); box-shadow:0 23px 52px rgba(7,30,24,.27);
    }
    .jx-portal-note { color:#f7f9f6; text-align:center; margin:1.8rem auto 0;
                      font-size:.84rem; text-shadow:0 2px 10px rgba(0,0,0,.7); }
    .jx-login-intro { color:#fff; text-shadow:0 2px 16px rgba(0,0,0,.4); padding:5vh 0 1.5rem; }
    .jx-login-intro h1 { color:#fff !important; font-size:clamp(1.85rem,3.5vw,3.3rem) !important;
                         max-width:100%; overflow-wrap:anywhere; line-height:1.35 !important; }
    .jx-login-intro p { font-size:1.12rem; }
    [data-testid="stVerticalBlockBorderWrapper"]:has(.jx-login-card) {
        background:rgba(255,255,252,.94) !important; border:1px solid rgba(255,255,255,.8) !important;
        box-shadow:0 16px 42px rgba(9,38,29,.22); backdrop-filter:blur(14px);
    }
    .jx-section-lead { padding:.7rem 0 .3rem; }
    .jx-section-lead h2 { margin:.2rem 0 .35rem; }
    .jx-admin-nav { font-size:.78rem; letter-spacing:.06em; color:#1e6f5c; font-weight:800; }
    [data-testid="stVerticalBlockBorderWrapper"]:has(.jx-admin-nav) {
        background:rgba(255,255,252,.96) !important; box-shadow:0 5px 25px rgba(20,65,51,.08);
    }
    [data-testid="stButton"] > button[kind="primary"],
    [data-testid="stFormSubmitButton"] > button[kind="primary"] {
        background:#1b6b55; border-color:#1b6b55; color:#fff; min-height:3rem;
        box-shadow:0 5px 14px rgba(21,94,71,.18); transition:transform .2s,box-shadow .2s,background .2s;
    }
    [data-testid="stButton"] > button:hover,
    [data-testid="stFormSubmitButton"] > button:hover {
        transform:translateY(-2px); box-shadow:0 10px 20px rgba(21,94,71,.2);
    }
    [data-testid="stButton"] > button:active,
    [data-testid="stFormSubmitButton"] > button:active { transform:translateY(0) scale(.99); }
    [data-testid="stButton"] > button:focus-visible,
    [data-testid="stFormSubmitButton"] > button:focus-visible,
    [data-testid="stLinkButton"] a:focus-visible { outline:3px solid #f0c966 !important; outline-offset:3px; }
    [data-testid="stButton"]:has(button[key="user_module_active"]) > button { border-color:#1e6f5c; }
    .jx-module-copy { font-size:.88rem; color:#4a6255; min-height:2.7rem; line-height:1.55; }
    [data-testid="stVerticalBlockBorderWrapper"]:has(.jx-module-active) {
        border:2px solid #1e6f5c !important; background:rgba(230,242,232,.96) !important;
    }
    [data-testid="stAppViewContainer"] [data-testid="stVerticalBlockBorderWrapper"] {
        backdrop-filter:blur(3px);
    }
    @media (prefers-reduced-motion:reduce) {
        *,*::before,*::after { animation-duration:.01ms !important; transition-duration:.01ms !important; }
    }
    @media (max-width:760px) {
        .block-container { padding:1.1rem 1rem 2rem; }
        h1, .jx-page-header h1 { font-size:1.55rem !important; }
        [data-testid="stMetric"] { padding:.8rem .9rem; }
        [data-testid="stMetricValue"] { font-size:1.4rem; }
        [data-baseweb="tab-list"] { gap:.75rem; }
        .jx-portal-intro { margin:2.2rem auto 1.25rem; }
        .jx-portal-intro h1 { font-size:2.15rem !important; }
        .jx-entry-card p { min-height:0; }
        [data-testid="stVerticalBlockBorderWrapper"]:has(.jx-entry-card) { min-height:0; padding:.8rem !important; }
        [data-testid="stVerticalBlockBorderWrapper"]:has(.jx-admin-card) { min-height:0; }
        .jx-login-intro { padding:1.5rem 0 .5rem; }
    }
    </style>
    """, unsafe_allow_html=True)


def page_header(title, subtitle, eyebrow=None):
    """Render a consistent page heading; all dynamic text is escaped."""
    label = f'<div class="jx-eyebrow">{escape(str(eyebrow))}</div>' if eyebrow else ""
    st.markdown(
        f'<div class="jx-page-header">{label}<h1>{escape(str(title))}</h1>'
        f'<p>{escape(str(subtitle))}</p></div>', unsafe_allow_html=True,
    )


def section_header(title, description=None):
    detail = f'<p>{escape(str(description))}</p>' if description else ""
    st.markdown(f'<div class="jx-section-header"><h2>{escape(str(title))}</h2>{detail}</div>',
                unsafe_allow_html=True)


def page_surface(kind: str) -> None:
    """Set a local scenic background for this page only."""
    from utils.media import asset_data_uri

    photo_key = "admin_login" if kind == "login" else "portal"
    photo = asset_data_uri(photo_key)
    if kind in {"portal", "login"}:
        shade = ("linear-gradient(105deg,rgba(8,39,31,.77),rgba(8,47,35,.43) 55%,"
                 "rgba(5,30,25,.62))")
        background = f'{shade},url("{photo}")' if photo else shade
        st.markdown(f"""<style>
        [data-testid="stAppViewContainer"] {{background-image:{background} !important;
            background-size:cover !important; background-position:center center !important;
            background-attachment:fixed !important; min-height:100vh;}}
        [data-testid="stHeader"] {{background:transparent !important;}}
        </style>""", unsafe_allow_html=True)
    else:
        shade = "linear-gradient(180deg,rgba(245,250,245,.83),#f7f9f6 38rem)"
        background = f'{shade},url("{photo}")' if photo else shade
        st.markdown(f"""<style>
        [data-testid="stAppViewContainer"] {{background-image:{background} !important;
            background-size:cover !important; background-position:center top !important;
            background-attachment:fixed !important;}}
        [data-testid="stHeader"] {{background:rgba(248,250,247,.88) !important;}}
        </style>""", unsafe_allow_html=True)


def admin_navigation(active: str) -> None:
    """Visible links on every protected page; access checks remain in each view."""
    links = [
        ("工作台", "views/0_Admin_Home.py"),
        ("调度控制台", "views/1_Admin_Dashboard.py"),
        ("车辆与线路", "views/2_Admin_Vehicle_Route.py"),
        ("客流场景", "views/3_Admin_Demand_Scenario.py"),
        ("智能调度", "views/4_Admin_Smart_Dispatch.py"),
        ("仿真监测", "views/5_Admin_Simulation_Monitor.py"),
        ("实验分析", "views/6_Admin_Experiment_Analysis.py"),
    ]
    with st.container(border=True):
        st.markdown(f'<div class="jx-admin-nav">管理中心 · 当前：{escape(active)}</div>',
                    unsafe_allow_html=True)
        for row in (links[:4], links[4:]):
            for column, (label, path) in zip(st.columns(len(row)), row):
                with column:
                    st.page_link(path, label=(f"● {label}" if label == active else label),
                                 use_container_width=True)
        home, visitor, account = st.columns(3)
        with home:
            st.page_link("views/portal.py", label="返回平台首页", use_container_width=True)
        with visitor:
            st.page_link("views/user.py", label="查看游客端", use_container_width=True)
        with account:
            st.page_link("views/admin_login.py", label="管理账号", use_container_width=True)


def apply_plotly_theme(fig):
    """Apply a readable chart style without changing traces or calculations."""
    fig.update_layout(
        font=dict(family=FONT_FAMILY, size=13, color="#1F2D3D"),
        colorway=COLORS,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=18, r=24, t=46, b=36),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        hoverlabel=dict(bgcolor="#FFFFFF", font_size=13, font_family=FONT_FAMILY),
    )
    fig.update_xaxes(showgrid=False, linecolor="#DEE7E2", tickfont=dict(size=12),
                     title_font=dict(size=13), automargin=True)
    fig.update_yaxes(gridcolor="#E8EEEA", zerolinecolor="#DEE7E2", tickfont=dict(size=12),
                     title_font=dict(size=13), automargin=True)
    return fig
