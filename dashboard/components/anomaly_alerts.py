"""
Anomaly Alerts Component
==========================
Displays detected anomalies as colored alert boxes.
"""

import streamlit as st
import pandas as pd


SEVERITY_CONFIG = {
    "critical": {"emoji": "🔴", "color": "#FF4B4B", "bg": "#3D1F1F"},
    "high": {"emoji": "🟠", "color": "#F39C12", "bg": "#3D2E1F"},
    "medium": {"emoji": "🟡", "color": "#F1C40F", "bg": "#3D3A1F"},
    "low": {"emoji": "⚪", "color": "#95A5A6", "bg": "#2D2D2D"},
}


def render_anomaly_alerts(df_anomalies: pd.DataFrame, max_display: int = 10):
    """
    Render anomaly alerts as styled boxes.
    
    Args:
        df_anomalies: DataFrame with anomaly data
        max_display: Maximum number of anomalies to show
    """
    st.markdown("### 🚨 Anomaly Alerts")

    if len(df_anomalies) == 0:
        st.info("No anomalies detected in the selected period.")
        return

    # Sort by severity
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    df_sorted = df_anomalies.copy()
    df_sorted["severity_rank"] = df_sorted["severity"].map(severity_order).fillna(99)
    df_sorted = df_sorted.sort_values("severity_rank").head(max_display)

    for _, row in df_sorted.iterrows():
        severity = row.get("severity", "low")
        config = SEVERITY_CONFIG.get(severity, SEVERITY_CONFIG["low"])

        date_str = ""
        if pd.notna(row.get("date")):
            try:
                date_str = pd.to_datetime(row["date"]).strftime("%b %d, %Y")
            except Exception:
                date_str = str(row["date"])

        description = row.get("description", "No description available")
        method = row.get("detection_method", "")
        direction = row.get("direction", "")

        st.markdown(f"""
        <div style="
            background: {config['bg']};
            border-left: 4px solid {config['color']};
            border-radius: 5px;
            padding: 10px 15px;
            margin-bottom: 8px;
        ">
            <span style="color: {config['color']}; font-weight: bold;">
                {config['emoji']} {severity.upper()}
            </span>
            <span style="color: #888; font-size: 12px; margin-left: 10px;">
                {date_str} | {method} | {direction}
            </span>
            <p style="color: #DDD; margin: 5px 0 0 0; font-size: 14px;">
                {description}
            </p>
        </div>
        """, unsafe_allow_html=True)

    # Show total count if there are more
    total = len(df_anomalies)
    if total > max_display:
        st.caption(f"Showing {max_display} of {total} anomalies. Filter by severity to see more.")
        
        