"""
Trend Charts Component
=======================
Line charts showing KPI trends over time.
"""

import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import streamlit as st


# Color palette for channels
CHANNEL_COLORS = {
    "google_ads": "#4285F4",   # Google blue
    "meta_ads": "#1877F2",     # Meta blue
    "organic": "#34A853",      # Green
    "direct": "#9B59B6",       # Purple
    "email": "#F39C12",        # Orange
    "referral": "#E74C3C",     # Red
    "total": "#FFFFFF",        # White
}


def create_revenue_spend_chart(df_daily: pd.DataFrame) -> go.Figure:
    """
    Dual-axis chart: Revenue (bars) and Spend (line) over time.
    Shows the total across all channels.
    """
    # Filter to total only
    df_total = df_daily[df_daily["channel"] == "total"].sort_values("date")

    fig = go.Figure()

    # Revenue bars
    fig.add_trace(go.Bar(
        x=df_total["date"],
        y=df_total["revenue"],
        name="Revenue",
        marker_color="#00D4AA",
        opacity=0.7,
    ))

    # Spend line on secondary axis
    fig.add_trace(go.Scatter(
        x=df_total["date"],
        y=df_total["cost"],
        name="Spend",
        line=dict(color="#FF4B4B", width=2),
        yaxis="y2",
    ))

    fig.update_layout(
        title="Revenue & Spend Over Time",
        template="plotly_dark",
        paper_bgcolor="#0E1117",
        plot_bgcolor="#0E1117",
        yaxis=dict(title="Revenue ($)", side="left", gridcolor="#333"),
        yaxis2=dict(title="Spend ($)", side="right", overlaying="y", gridcolor="#333"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        height=350,
        margin=dict(l=50, r=50, t=50, b=30),
    )

    return fig


def create_roas_by_channel_chart(df_daily: pd.DataFrame) -> go.Figure:
    """
    Multi-line chart showing ROAS trend for each paid channel.
    """
    # Only paid channels
    paid_channels = ["google_ads", "meta_ads"]
    df_paid = df_daily[df_daily["channel"].isin(paid_channels)].sort_values("date")

    fig = go.Figure()

    for channel in paid_channels:
        df_ch = df_paid[df_paid["channel"] == channel]
        color = CHANNEL_COLORS.get(channel, "#FFFFFF")

        fig.add_trace(go.Scatter(
            x=df_ch["date"],
            y=df_ch["roas"],
            name=channel.replace("_", " ").title(),
            line=dict(color=color, width=2),
            mode="lines",
        ))

    fig.update_layout(
        title="ROAS by Channel (Daily)",
        template="plotly_dark",
        paper_bgcolor="#0E1117",
        plot_bgcolor="#0E1117",
        yaxis=dict(title="ROAS (x)", gridcolor="#333"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        height=350,
        margin=dict(l=50, r=50, t=50, b=30),
    )

    return fig


def create_conversions_chart(df_daily: pd.DataFrame) -> go.Figure:
    """
    Stacked area chart showing conversions by channel over time.
    """
    channels = ["google_ads", "meta_ads", "organic", "direct", "email", "referral"]
    df_channels = df_daily[df_daily["channel"].isin(channels)].sort_values("date")

    fig = go.Figure()

    for channel in channels:
        df_ch = df_channels[df_channels["channel"] == channel]
        color = CHANNEL_COLORS.get(channel, "#FFFFFF")

        fig.add_trace(go.Scatter(
            x=df_ch["date"],
            y=df_ch["conversions"],
            name=channel.replace("_", " ").title(),
            stackgroup="one",
            line=dict(color=color, width=0.5),
        ))

    fig.update_layout(
        title="Conversions by Channel (Stacked)",
        template="plotly_dark",
        paper_bgcolor="#0E1117",
        plot_bgcolor="#0E1117",
        yaxis=dict(title="Conversions", gridcolor="#333"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        height=350,
        margin=dict(l=50, r=50, t=50, b=30),
    )

    return fig


def render_trend_charts(df_daily: pd.DataFrame):
    """Render all trend charts in the dashboard."""
    col1, col2 = st.columns(2)

    with col1:
        fig_rev = create_revenue_spend_chart(df_daily)
        st.plotly_chart(fig_rev, use_container_width=True)

    with col2:
        fig_roas = create_roas_by_channel_chart(df_daily)
        st.plotly_chart(fig_roas, use_container_width=True)

    # Full width conversions chart
    fig_conv = create_conversions_chart(df_daily)
    st.plotly_chart(fig_conv, use_container_width=True)
    