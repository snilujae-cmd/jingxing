import streamlit as st

def check_p0(mode="sim"):
    missing = ["A/B线实际车辆数", "逐站客流", "端点折返时间"]

    if mode == "real":
        st.error("❌ 真实模式阻断：以下 P0 数据未核实")
        for m in missing:
            st.write(f"- {m}")
        st.stop()
    else:
        st.warning(f"⚠️ 仿真模式：以下数据为仿真设定 → {', '.join(missing)}")