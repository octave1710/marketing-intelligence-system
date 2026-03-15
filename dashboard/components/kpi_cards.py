"""
KPI Cards Component
====================
Displays the top-row KPI cards in the dashboard.
Each card shows: metric name, current value, and period-over-period change.
"""

import streamlit as st
from typing import Optional


def format_value(value, format_type: str) -> str:
    """Format a KPI value for display."""
    if value is None:
        return "N/A"
    
    if format_type == "currency":
        if abs(value) >= 1_000_000:
            return f"${value / 1_000_000:,.1f}M"
        elif abs(value) >= 1_000:
            return f"${value / 1_000:,.1f}K"
        else:
            return f"${value:,.2f}"
    elif format_type == "percentage":
        return f"{value:.2%}"
    elif format_type == "multiplier":
        return f"{value:.2f}x"
    elif format_type == "number":
        if abs(value) >= 1_000_000:
            return f"{value / 1_000_000:,.1f}M"
        elif abs(value) >= 1_000:
            return f"{value / 1_000:,.1f}K"
        else:
            return f"{value:,.0f}"
    else:
        return f"{value:,.2f}"


def format_change(change: Optional[float], good_direction: str = "up") -> str:
    """
    Format a percentage change with color indicator.
    
    Args:
        change: The percentage change as a decimal (0.12 = +12%)
        good_direction: "up" means positive change is good, "down" means negative is good
    """
    if change is None:
        return "N/A"
    
    arrow = "▲" if change > 0 else "▼" if change < 0 else "—"
    pct = f"{abs(change):.1%}"
    
    return f"{arrow} {pct}"


def get_change_color(change: Optional[float], good_direction: str = "up") -> str:
    """Return color based on whether the change is good or bad."""
    if change is None:
        return "gray"
    
    if good_direction == "up":
        return "#00D4AA" if change > 0 else "#FF4B4B" if change < 0 else "gray"
    else:  # down is good (like CPA, CPC)
        return "#00D4AA" if change < 0 else "#FF4B4B" if change > 0 else "gray"


def render_kpi_cards(kpi_data: dict, changes: dict):
    """
    Render a row of KPI cards at the top of the dashboard.
    
    Args:
        kpi_data: Dict with current KPI values
        changes: Dict with period-over-period changes
    """
    cards = [
        {
            "label": "Total Spend",
            "value": kpi_data.get("spend"),
            "format": "currency",
            "change": changes.get("spend_change"),
            "good_direction": "neutral",  # Spend isn't inherently good or bad
        },
        {
            "label": "Revenue",
            "value": kpi_data.get("revenue"),
            "format": "currency",
            "change": changes.get("revenue_change"),
            "good_direction": "up",
        },
        {
            "label": "ROAS",
            "value": kpi_data.get("roas"),
            "format": "multiplier",
            "change": changes.get("roas_change"),
            "good_direction": "up",
        },
        {
            "label": "CPA",
            "value": kpi_data.get("cpa"),
            "format": "currency",
            "change": changes.get("cpa_change"),
            "good_direction": "down",  # Lower CPA is better
        },
        {
            "label": "Conversions",
            "value": kpi_data.get("conversions"),
            "format": "number",
            "change": changes.get("conversions_change"),
            "good_direction": "up",
        },
        {
            "label": "CVR",
            "value": kpi_data.get("cvr"),
            "format": "percentage",
            "change": changes.get("cvr_change"),
            "good_direction": "up",
        },
    ]

    cols = st.columns(len(cards))

    for col, card in zip(cols, cards):
        with col:
            value_str = format_value(card["value"], card["format"])
            change_str = format_change(card["change"], card["good_direction"])
            color = get_change_color(card["change"], card["good_direction"])

            st.markdown(f"""
            <div style="
                background: #1E1E1E;
                border-radius: 10px;
                padding: 15px;
                text-align: center;
                border: 1px solid #333;
            ">
                <p style="color: #888; font-size: 12px; margin: 0;">{card['label']}</p>
                <p style="color: white; font-size: 24px; font-weight: bold; margin: 5px 0;">{value_str}</p>
                <p style="color: {color}; font-size: 14px; margin: 0;">{change_str}</p>
            </div>
            """, unsafe_allow_html=True)
            