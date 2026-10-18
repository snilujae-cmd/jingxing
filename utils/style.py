import streamlit as st

def load_css():
    st.markdown("""
    <style>
    .main-title { font-size: 2.2rem; font-weight: 700; color: #1E6F5C; }
    .sub-title  { font-size: 1rem; color: #5A6B63; margin-bottom: 1rem; }
    div[data-testid="stMetric"] {
        background-color: #FFFFFF;
        border: 1px solid #E0E6E4;
        border-radius: 10px;
        padding: 15px 20px;
    }
    div[data-testid="stMetricValue"] {
        font-size: 1.8rem;
        color: #1E6F5C;
        font-weight: 700;
    }
    .stButton > button {
        border-radius: 8px;
        font-weight: 600;
    }
    .footer-text {
        color: #8C9E97;
        font-size: 0.85rem;
        text-align: center;
        margin-top: 30px;
        border-top: 1px solid #E0E6E4;
        padding-top: 15px;
    }
    </style>
    """, unsafe_allow_html=True)