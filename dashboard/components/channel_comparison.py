"""
Channel Comparison Component
==============================
Side-by-side comparison charts for channels.
"""

import plotly.graph_objects as go
import pandas as pd
import streamlit as st

from dashboard.components.trend_charts import CHANNEL_COLORS


def create_spend_vs_revenue_chart(channel_data: list) -> go.Figure:
    """Grouped bar chart: Spend vs Revenue by channel."""
    channels = [ch["channel"] for ch in channel_data]
    spend = [ch["spend"] for ch in channel_data]
    revenue = [ch["revenue"] for ch in channel_data]
    colors = [CHANNEL_COLORS.get(ch, "#FFFFFF") for ch in channels]

    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=channels,
        y=spend,
        name="Spend",
        marker_color="#FF4B4B",
        opacity=0.8,
    ))

    fig.add_trace(go.Bar(
        x=channels,
        y=revenue,
        name="Revenue",
        marker_color="#00D4AA",
        opacity=0.8,
    ))

    fig.update_layout(
        title="Spend vs Revenue by Channel",
        template="plotly_dark",
        paper_bgcolor="#0E1117",
        plot_bgcolor="#0E1117",
        barmode="group",
        yaxis=dict(title="USD ($)", gridcolor="#333"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        height=350,
        margin=dict(l=50, r=50, t=50, b=30),
    )

    return fig


def create_efficiency_chart(channel_data: list) -> go.Figure:
    """Horizontal bar chart showing efficiency index per channel."""
    # Only paid channels
    paid = [ch for ch in channel_data if ch.get("spend", 0) > 0]

    if not paid:
        fig = go.Figure()
        fig.update_layout(title="No paid channel data", template="plotly_dark")
        return fig

    channels = [ch["channel"] for ch in paid]
    roas = [ch.get("roas", 0) or 0 for ch in paid]

    # Color based on ROAS performance
    colors = ["#00D4AA" if r >= 4 else "#F39C12" if r >= 2 else "#FF4B4B" for r in roas]

    fig = go.Figure()

    fig.add_trace(go.Bar(
        y=channels,
        x=roas,
        orientation="h",
        marker_color=colors,
        text=[f"{r:.1f}x" for r in roas],
        textposition="outside",
    ))

    # Add target line
    fig.add_vline(x=4.0, line_dash="dash", line_color="white", opacity=0.5,
                  annotation_text="Target 4x", annotation_position="top right")

    fig.update_layout(
        title="ROAS by Channel",
        template="plotly_dark",
        paper_bgcolor="#0E1117",
        plot_bgcolor="#0E1117",
        xaxis=dict(title="ROAS (x)", gridcolor="#333"),
        height=300,
        margin=dict(l=100, r=50, t=50, b=30),
    )

    return fig


def create_campaign_performance_table(top_campaigns: dict):
    """Display top and bottom campaigns as a formatted table."""
    
    st.markdown("#### 🏆 Top Campaigns by ROAS")
    if top_campaigns.get("top"):
        top_df = pd.DataFrame(top_campaigns["top"])
        top_df = top_df[["campaign_name", "channel", "cost", "revenue", "roas"]].copy()
        top_df.columns = ["Campaign", "Channel", "Spend", "Revenue", "ROAS"]
        top_df["Spend"] = top_df["Spend"].apply(lambda x: f"${x:,.0f}")
        top_df["Revenue"] = top_df["Revenue"].apply(lambda x: f"${x:,.0f}")
        top_df["ROAS"] = top_df["ROAS"].apply(lambda x: f"{x:.2f}x")
        st.dataframe(top_df, use_container_width=True, hide_index=True)
    
    st.markdown("#### 📉 Bottom Campaigns by ROAS")
    if top_campaigns.get("bottom"):
        bottom_df = pd.DataFrame(top_campaigns["bottom"])
        bottom_df = bottom_df[["campaign_name", "channel", "cost", "revenue", "roas"]].copy()
        bottom_df.columns = ["Campaign", "Channel", "Spend", "Revenue", "ROAS"]
        bottom_df["Spend"] = bottom_df["Spend"].apply(lambda x: f"${x:,.0f}")
        bottom_df["Revenue"] = bottom_df["Revenue"].apply(lambda x: f"${x:,.0f}")
        bottom_df["ROAS"] = bottom_df["ROAS"].apply(lambda x: f"{x:.2f}x")
        st.dataframe(bottom_df, use_container_width=True, hide_index=True)


def render_channel_comparison(channel_data: list, top_campaigns: dict):
    """Render all channel comparison components."""
    col1, col2 = st.columns(2)

    with col1:
        fig_bar = create_spend_vs_revenue_chart(channel_data)
        st.plotly_chart(fig_bar, use_container_width=True)

    with col2:
        fig_eff = create_efficiency_chart(channel_data)
        st.plotly_chart(fig_eff, use_container_width=True)

    create_campaign_performance_table(top_campaigns)
    