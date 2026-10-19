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
    @media (max-width:760px) {
        .block-container { padding:1.1rem 1rem 2rem; }
        h1, .jx-page-header h1 { font-size:1.55rem !important; }
        [data-testid="stMetric"] { padding:.8rem .9rem; }
        [data-testid="stMetricValue"] { font-size:1.4rem; }
        [data-baseweb="tab-list"] { gap:.75rem; }
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
