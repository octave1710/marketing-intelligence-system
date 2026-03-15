"""
Generate Synthetic Marketing Data
==================================
Creates realistic fake data for Google Ads, Meta Ads, and GA4.

Output: 3 CSV files in data/raw/
- sample_google_ads.csv  (~2,200 rows)
- sample_meta_ads.csv    (~1,100 rows)
- sample_ga4.csv         (~1,650 rows)

The data covers 92 days (2024-07-01 to 2024-09-30) and includes:
- Realistic daily patterns (less activity on weekends)
- Gradual growth trend over the period
- Random noise for day-to-day variability
- 4 intentionally injected anomalies for the anomaly detector to find later
"""

# ================================================================
# IMPORTS
# ================================================================
# Standard library (built into Python)
from pathlib import Path
import sys

# Third-party (installed via pip)
import pandas as pd
import numpy as np

# Local project imports
# We need to tell Python where our project root is so it can find config/
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from config.settings import (
    SIMULATION_START_DATE,
    SIMULATION_END_DATE,
    RAW_DATA_DIR,
)

# Fix the random seed so the data is identical every time we run the script.
# Why? Reproducibility. Anyone who clones the repo and runs this script
# gets the exact same data, which makes testing and debugging predictable.
np.random.seed(42)


# ================================================================
# SECTION 1: CAMPAIGN DEFINITIONS
# ================================================================
# Each campaign is a dictionary with its "base" characteristics.
# The generator will add noise, trends, and anomalies on top.
#
# How to read these:
#   daily_budget = how much this campaign spends per day on average
#   avg_cpc = average cost per click (Google Ads charges per click)
#   avg_ctr = what % of people who SEE the ad actually CLICK it
#   avg_cvr = what % of people who CLICK actually BUY something
#   avg_aov = average value of one purchase

GOOGLE_ADS_CAMPAIGNS = [
    {
        "campaign_id": "gads_search_brand_us_001",
        "campaign_name": "US - Search - Brand - Core",
        "campaign_type": "Search",
        "market": "US",
        "daily_budget": 375.0,
        "avg_cpc": 1.20,
        "avg_ctr": 0.08,       # 8% CTR — high because it's brand search
        "avg_cvr": 0.06,       # 6% CVR — people searching your brand name convert well
        "avg_aov": 145.0,
    },
    {
        "campaign_id": "gads_search_nonbrand_us_002",
        "campaign_name": "US - Search - Non-Brand - Generic",
        "campaign_type": "Search",
        "market": "US",
        "daily_budget": 300.0,
        "avg_cpc": 2.80,       # More expensive — competing on generic keywords
        "avg_ctr": 0.035,      # 3.5% CTR — lower because it's generic
        "avg_cvr": 0.025,      # 2.5% CVR — less intent than brand
        "avg_aov": 120.0,
    },
    {
        "campaign_id": "gads_shopping_us_003",
        "campaign_name": "US - Shopping - Smart",
        "campaign_type": "Shopping",
        "market": "US",
        "daily_budget": 225.0,
        "avg_cpc": 0.85,       # Cheap clicks — Shopping ads show product images
        "avg_ctr": 0.012,      # 1.2% CTR — lower but lots of impressions
        "avg_cvr": 0.032,      # 3.2% CVR — product-level intent
        "avg_aov": 135.0,
    },
    {
        "campaign_id": "gads_search_brand_uk_004",
        "campaign_name": "UK - Search - Brand",
        "campaign_type": "Search",
        "market": "UK",
        "daily_budget": 180.0,
        "avg_cpc": 0.95,
        "avg_ctr": 0.075,
        "avg_cvr": 0.055,
        "avg_aov": 130.0,
    },
    {
        "campaign_id": "gads_search_brand_fr_005",
        "campaign_name": "FR - Search - Brand",
        "campaign_type": "Search",
        "market": "FR",
        "daily_budget": 120.0,
        "avg_cpc": 0.70,
        "avg_ctr": 0.07,
        "avg_cvr": 0.045,
        "avg_aov": 115.0,
    },
    {
        "campaign_id": "gads_search_generic_de_006",
        "campaign_name": "DE - Search - Generic",
        "campaign_type": "Search",
        "market": "DE",
        "daily_budget": 120.0,
        "avg_cpc": 1.50,
        "avg_ctr": 0.04,
        "avg_cvr": 0.03,
        "avg_aov": 125.0,
    },
    {
        "campaign_id": "gads_pmax_us_007",
        "campaign_name": "US - PMax - All Products",
        "campaign_type": "PMax",
        "market": "US",
        "daily_budget": 120.0,
        "avg_cpc": 1.10,
        "avg_ctr": 0.02,
        "avg_cvr": 0.028,
        "avg_aov": 140.0,
    },
    {
        "campaign_id": "gads_display_retargeting_uk_008",
        "campaign_name": "UK - Display - Retargeting",
        "campaign_type": "Display",
        "market": "UK",
        "daily_budget": 60.0,
        "avg_cpc": 0.45,
        "avg_ctr": 0.005,      # 0.5% CTR — Display ads have low CTR, that's normal
        "avg_cvr": 0.018,
        "avg_aov": 110.0,
    },
]
# Total Google Ads daily budget: 375+300+225+180+120+120+120+60 = $1,500/day

META_ADS_CAMPAIGNS = [
    {
        "campaign_id": "meta_conv_prospecting_us_001",
        "campaign_name": "US - Conversions - Prospecting - LAL",
        "objective": "Conversions",
        "placement": "Feed",
        "market": "US",
        "daily_budget": 360.0,
        "avg_cpm": 12.50,      # Meta charges per 1000 impressions (CPM), not per click
        "avg_ctr": 0.015,      # 1.5% CTR
        "avg_cvr": 0.022,      # 2.2% CVR on link clicks
        "avg_aov": 130.0,
        "avg_frequency": 1.8,  # Each person sees the ad 1.8 times on average
    },
    {
        "campaign_id": "meta_conv_retargeting_us_002",
        "campaign_name": "US - Conversions - Retargeting - DPA",
        "objective": "Conversions",
        "placement": "Feed",
        "market": "US",
        "daily_budget": 300.0,
        "avg_cpm": 18.00,      # Retargeting is more expensive (smaller audience)
        "avg_ctr": 0.025,      # Higher CTR — people already know the brand
        "avg_cvr": 0.045,      # Much higher CVR — these are warm leads
        "avg_aov": 150.0,
        "avg_frequency": 2.5,  # Higher frequency — retargeting shows ads more often
    },
    {
        "campaign_id": "meta_conv_prospecting_uk_003",
        "campaign_name": "UK - Conversions - Prospecting",
        "objective": "Conversions",
        "placement": "Feed",
        "market": "UK",
        "daily_budget": 180.0,
        "avg_cpm": 9.50,
        "avg_ctr": 0.013,
        "avg_cvr": 0.018,
        "avg_aov": 120.0,
        "avg_frequency": 1.6,
    },
    {
        "campaign_id": "meta_traffic_awareness_fr_004",
        "campaign_name": "FR - Traffic - Awareness",
        "objective": "Traffic",
        "placement": "Stories",
        "market": "FR",
        "daily_budget": 120.0,
        "avg_cpm": 6.00,       # Awareness = cheap impressions
        "avg_ctr": 0.02,
        "avg_cvr": 0.008,      # Very low CVR — awareness campaigns don't optimize for sales
        "avg_aov": 100.0,
        "avg_frequency": 1.3,
    },
    {
        "campaign_id": "meta_reels_conv_us_005",
        "campaign_name": "US - Reels - Conversions",
        "objective": "Conversions",
        "placement": "Reels",
        "market": "US",
        "daily_budget": 144.0,
        "avg_cpm": 14.00,
        "avg_ctr": 0.018,
        "avg_cvr": 0.028,
        "avg_aov": 125.0,
        "avg_frequency": 1.5,
    },
    {
        "campaign_id": "meta_conv_prospecting_de_006",
        "campaign_name": "DE - Conversions - Prospecting",
        "objective": "Conversions",
        "placement": "Feed",
        "market": "DE",
        "daily_budget": 96.0,
        "avg_cpm": 8.00,
        "avg_ctr": 0.011,
        "avg_cvr": 0.015,
        "avg_aov": 115.0,
        "avg_frequency": 1.4,
    },
]
# Total Meta Ads daily budget: 360+300+180+120+144+96 = $1,200/day

GA4_CHANNELS = [
    {
        "source": "google",
        "medium": "organic",
        "market": "US",
        "avg_daily_sessions": 5000,
        "avg_engagement_rate": 0.65,   # 65% of sessions are "engaged" (not bounce)
        "avg_cvr": 0.035,              # 3.5% of sessions lead to a purchase
        "avg_aov": 140.0,
    },
    {
        "source": "direct",
        "medium": "(none)",            # GA4 marks direct traffic with medium "(none)"
        "market": "US",
        "avg_daily_sessions": 3500,
        "avg_engagement_rate": 0.72,   # Direct visitors are loyal → higher engagement
        "avg_cvr": 0.042,
        "avg_aov": 155.0,
    },
    {
        "source": "newsletter",
        "medium": "email",
        "market": "US",
        "avg_daily_sessions": 1200,
        "avg_engagement_rate": 0.58,
        "avg_cvr": 0.048,             # Email subscribers convert well
        "avg_aov": 160.0,
    },
    {
        "source": "google",
        "medium": "organic",
        "market": "UK",
        "avg_daily_sessions": 2800,
        "avg_engagement_rate": 0.62,
        "avg_cvr": 0.030,
        "avg_aov": 130.0,
    },
    {
        "source": "referral",
        "medium": "referral",
        "market": "FR",
        "avg_daily_sessions": 800,
        "avg_engagement_rate": 0.55,
        "avg_cvr": 0.020,
        "avg_aov": 110.0,
    },
    {
        "source": "direct",
        "medium": "(none)",
        "market": "DE",
        "avg_daily_sessions": 600,
        "avg_engagement_rate": 0.60,
        "avg_cvr": 0.025,
        "avg_aov": 120.0,
    },
]


# ================================================================
# SECTION 2: ANOMALY DEFINITIONS
# ================================================================
# These are "problems" or "events" we intentionally inject into the data.
# Later, our anomaly detector module should find them automatically.
# Think of it as hiding Easter eggs that our system needs to discover.

ANOMALIES = [
    {
        # Scenario: A competitor started bidding aggressively on our keywords
        # Impact: CPC (cost per click) jumps 45% for ALL Google Ads campaigns
        "start": "2024-08-12",
        "end": "2024-08-14",          # 3 days
        "channel": "google_ads",
        "campaign_type": None,         # None = affects ALL Google Ads campaigns
        "source": None,
        "medium": None,
        "metric": "cpc",
        "multiplier": 1.45,           # ×1.45 = +45% increase
    },
    {
        # Scenario: A bug was deployed on the checkout page
        # Impact: Conversion rate drops 28% for ALL Meta Ads campaigns
        "start": "2024-09-03",
        "end": "2024-09-07",          # 5 days
        "channel": "meta_ads",
        "campaign_type": None,
        "source": None,
        "medium": None,
        "metric": "cvr",
        "multiplier": 0.72,           # ×0.72 = -28% decrease
    },
    {
        # Scenario: An article about us went viral on Reddit
        # Impact: Organic traffic from Google spikes 67%
        "start": "2024-08-25",
        "end": "2024-08-26",          # 2 days
        "channel": "ga4",
        "campaign_type": None,
        "source": "google",            # Only affects google/organic
        "medium": "organic",
        "metric": "sessions",
        "multiplier": 1.67,           # ×1.67 = +67% increase
    },
    {
        # Scenario: We restructured our Shopping campaigns with better product groups
        # Impact: Shopping campaign CVR improves 35% (good anomaly!)
        "start": "2024-09-15",
        "end": "2024-09-21",          # 7 days
        "channel": "google_ads",
        "campaign_type": "Shopping",   # Only affects Shopping campaigns
        "source": None,
        "medium": None,
        "metric": "cvr",
        "multiplier": 1.35,           # ×1.35 = +35% improvement
    },
]


# ================================================================
# SECTION 3: DEVICE WEIGHTS
# ================================================================
# How traffic is split across devices. These are realistic proportions.

GOOGLE_DEVICE_WEIGHTS = {"desktop": 0.35, "mobile": 0.55, "tablet": 0.10}
META_DEVICE_WEIGHTS = {"desktop": 0.25, "mobile": 0.75}  # Meta is mobile-heavy
GA4_DEVICE_WEIGHTS = {"desktop": 0.35, "mobile": 0.55, "tablet": 0.10}


# ================================================================
# SECTION 4: HELPER FUNCTIONS
# ================================================================

def get_day_multiplier(date) -> float:
    """
    Returns a multiplier based on day of week.
    
    In real marketing, performance dips on weekends because fewer people
    shop online on Saturday/Sunday. This simulates that pattern.
    
    Monday-Friday → 1.0 (normal)
    Saturday → 0.75 (25% less activity)
    Sunday → 0.65 (35% less activity)
    """
    day_of_week = date.weekday()  # Monday=0, Tuesday=1, ..., Sunday=6
    if day_of_week == 5:    # Saturday
        return 0.75
    elif day_of_week == 6:  # Sunday
        return 0.65
    else:                   # Monday to Friday
        return 1.0


def get_growth_multiplier(date, start_date) -> float:
    """
    Returns a multiplier that increases slightly over time.
    
    Simulates organic growth: +0.5% per week.
    Over 13 weeks (92 days), that's about +6.5% total growth.
    
    Example:
      Week 1 → 1.000
      Week 5 → 1.025
      Week 13 → 1.065
    """
    days_elapsed = (date - start_date).days
    weeks_elapsed = days_elapsed / 7
    return 1.0 + (weeks_elapsed * 0.005)


def add_noise(value: float, noise_level: float = 0.15) -> float:
    """
    Adds random variation to a value.
    
    In real life, marketing metrics fluctuate day to day even without
    any real change. This function simulates that natural variability.
    
    Args:
        value: the base value (e.g., 100)
        noise_level: how much it can vary (0.15 = ±15%)
    
    Returns:
        A value randomly adjusted. Never returns negative.
        
    Example:
        add_noise(100, 0.15) might return 87, 104, 112, 95, etc.
    """
    noisy = value * (1 + np.random.normal(0, noise_level))
    return max(0, noisy)  # Safety: never return a negative number


def get_anomaly_multiplier(
    date,
    channel: str,
    metric: str,
    campaign_type: str = None,
    source: str = None,
    medium: str = None,
) -> float:
    """
    Checks if this specific date/channel/metric has an injected anomaly.
    
    Returns:
        The anomaly multiplier if there's an anomaly (e.g., 1.45 for +45%)
        1.0 if there's no anomaly (= no change)
    """
    date_str = date.strftime("%Y-%m-%d")

    for anomaly in ANOMALIES:
        # Check 1: Is today within the anomaly's date range?
        if not (anomaly["start"] <= date_str <= anomaly["end"]):
            continue  # Not in range → skip to next anomaly

        # Check 2: Does this anomaly apply to this channel?
        if anomaly["channel"] != channel:
            continue

        # Check 3: Does this anomaly apply to this metric?
        if anomaly["metric"] != metric:
            continue

        # Check 4: Campaign type filter (None = applies to all campaigns)
        if anomaly["campaign_type"] is not None:
            if anomaly["campaign_type"] != campaign_type:
                continue

        # Check 5: Source/medium filter for GA4 (None = applies to all)
        if anomaly["source"] is not None:
            if anomaly["source"] != source:
                continue
        if anomaly["medium"] is not None:
            if anomaly["medium"] != medium:
                continue

        # All checks passed → this anomaly applies!
        return anomaly["multiplier"]

    # No anomaly found for this combination
    return 1.0


# ================================================================
# SECTION 5: DATA GENERATORS
# ================================================================

def generate_google_ads(start_date: str, end_date: str) -> pd.DataFrame:
    """
    Generate realistic Google Ads data.
    
    Google Ads uses a CPC (cost-per-click) model: you pay each time
    someone clicks your ad. The logic chain is:
    
    Budget → Cost (what you spend)
    Cost ÷ CPC → Clicks (how many clicks you got)
    Clicks ÷ CTR → Impressions (how many times the ad was shown)
    Clicks × CVR → Conversions (how many people bought)
    Conversions × AOV → Revenue (how much money you made)
    
    Each row = one day × one campaign × one device type
    """
    dates = pd.date_range(start=start_date, end=end_date)
    rows = []

    for date in dates:
        day_mult = get_day_multiplier(date)
        growth_mult = get_growth_multiplier(date, dates[0])

        for campaign in GOOGLE_ADS_CAMPAIGNS:
            for device, dev_weight in GOOGLE_DEVICE_WEIGHTS.items():

                # --- STEP 1: COST ---
                # Start with daily budget, adjust for device share, day pattern, growth
                base_cost = campaign["daily_budget"] * dev_weight * day_mult * growth_mult
                cost = round(add_noise(base_cost, 0.12), 2)

                # --- STEP 2: CPC (with anomaly check) ---
                cpc_anomaly = get_anomaly_multiplier(
                    date, "google_ads", "cpc", campaign["campaign_type"]
                )
                cpc = add_noise(campaign["avg_cpc"] * cpc_anomaly, 0.10)
                cpc = max(0.10, cpc)  # CPC minimum $0.10

                # --- STEP 3: CLICKS (derived from cost and cpc) ---
                clicks = max(1, int(cost / cpc))

                # --- STEP 4: IMPRESSIONS (derived from clicks and ctr) ---
                ctr = add_noise(campaign["avg_ctr"], 0.10)
                ctr = max(0.001, min(ctr, 0.30))  # Keep CTR between 0.1% and 30%
                impressions = max(clicks, int(clicks / ctr))  # impressions >= clicks always

                # --- STEP 5: CONVERSIONS (with anomaly check for Shopping ROAS improvement) ---
                cvr_anomaly = get_anomaly_multiplier(
                    date, "google_ads", "cvr", campaign["campaign_type"]
                )
                cvr = add_noise(campaign["avg_cvr"] * cvr_anomaly, 0.12)
                cvr = max(0, min(cvr, 0.50))  # Cap at 50%
                conversions = round(clicks * cvr, 1)

                # --- STEP 6: REVENUE ---
                aov = add_noise(campaign["avg_aov"], 0.08)
                conversion_value = round(conversions * aov, 2)

                # --- SEARCH IMPRESSION SHARE (only for Search campaigns) ---
                if campaign["campaign_type"] == "Search":
                    sis = round(add_noise(0.72, 0.08), 2)
                    sis = max(0.20, min(sis, 0.98))
                else:
                    sis = None

                rows.append({
                    "date": date.strftime("%Y-%m-%d"),
                    "campaign_id": campaign["campaign_id"],
                    "campaign_name": campaign["campaign_name"],
                    "campaign_type": campaign["campaign_type"],
                    "market": campaign["market"],
                    "device": device,
                    "impressions": impressions,
                    "clicks": clicks,
                    "cost": cost,
                    "conversions": conversions,
                    "conversion_value": conversion_value,
                    "search_impression_share": sis,
                })

    return pd.DataFrame(rows)


def generate_meta_ads(start_date: str, end_date: str) -> pd.DataFrame:
    """
    Generate realistic Meta Ads (Facebook/Instagram) data.
    
    Meta uses a CPM (cost-per-mille) model: you pay per 1000 impressions.
    The logic chain is different from Google:
    
    Budget → Cost
    Cost ÷ CPM × 1000 → Impressions
    Impressions ÷ Frequency → Reach (unique people)
    Impressions × CTR → Link Clicks
    Link Clicks × CVR → Purchases
    Purchases × AOV → Revenue
    
    Meta also tracks funnel metrics like add-to-cart and landing page views.
    """
    dates = pd.date_range(start=start_date, end=end_date)
    rows = []

    for date in dates:
        day_mult = get_day_multiplier(date)
        growth_mult = get_growth_multiplier(date, dates[0])

        for campaign in META_ADS_CAMPAIGNS:
            for device, dev_weight in META_DEVICE_WEIGHTS.items():

                # --- COST ---
                base_cost = campaign["daily_budget"] * dev_weight * day_mult * growth_mult
                cost = round(add_noise(base_cost, 0.12), 2)

                # --- CPM → IMPRESSIONS ---
                cpm = add_noise(campaign["avg_cpm"], 0.10)
                cpm = max(1.0, cpm)
                impressions = max(100, int((cost / cpm) * 1000))

                # --- FREQUENCY → REACH ---
                frequency = add_noise(campaign["avg_frequency"], 0.08)
                frequency = max(1.0, frequency)
                reach = max(1, int(impressions / frequency))

                # --- CTR → LINK CLICKS ---
                ctr = add_noise(campaign["avg_ctr"], 0.10)
                ctr = max(0.002, min(ctr, 0.15))
                link_clicks = max(1, int(impressions * ctr))

                # --- TOTAL CLICKS (link clicks + likes, comments, shares, etc.) ---
                clicks = max(link_clicks, int(link_clicks * add_noise(1.5, 0.10)))

                # --- CVR → PURCHASES (with anomaly check) ---
                cvr_anomaly = get_anomaly_multiplier(date, "meta_ads", "cvr")
                cvr = add_noise(campaign["avg_cvr"] * cvr_anomaly, 0.12)
                cvr = max(0, min(cvr, 0.30))
                purchases = round(link_clicks * cvr, 1)

                # --- AOV → REVENUE ---
                aov = add_noise(campaign["avg_aov"], 0.08)
                purchase_value = round(purchases * aov, 2)

                # --- FUNNEL METRICS ---
                # Add to cart: typically 3-4x more people add to cart than actually buy
                add_to_cart = max(0, int(purchases * add_noise(3.5, 0.15)))
                # Landing page views: ~85% of link clickers actually load the page
                landing_page_views = max(1, int(link_clicks * add_noise(0.85, 0.05)))

                rows.append({
                    "date": date.strftime("%Y-%m-%d"),
                    "campaign_id": campaign["campaign_id"],
                    "campaign_name": campaign["campaign_name"],
                    "objective": campaign["objective"],
                    "placement": campaign["placement"],
                    "market": campaign["market"],
                    "device": device,
                    "impressions": impressions,
                    "reach": reach,
                    "clicks": clicks,
                    "link_clicks": link_clicks,
                    "cost": cost,
                    "purchases": purchases,
                    "purchase_value": purchase_value,
                    "add_to_cart": add_to_cart,
                    "landing_page_views": landing_page_views,
                    "frequency": round(frequency, 2),
                })

    return pd.DataFrame(rows)


def generate_ga4(start_date: str, end_date: str) -> pd.DataFrame:
    """
    Generate realistic GA4 (Google Analytics 4) data.
    
    GA4 tracks ALL traffic to your website, not just paid ads.
    Organic search, direct visits, email clicks, referral links — all free.
    So there's no "cost" column here.
    
    The logic chain:
    Base sessions (adjusted for day/growth/noise/anomaly)
    Sessions × 0.8 → Users (some people visit multiple times)
    Sessions × engagement_rate → Engaged Sessions
    Sessions × CVR → Conversions
    Conversions × AOV → Revenue
    """
    dates = pd.date_range(start=start_date, end=end_date)
    rows = []

    for date in dates:
        day_mult = get_day_multiplier(date)
        growth_mult = get_growth_multiplier(date, dates[0])

        for channel in GA4_CHANNELS:
            for device, dev_weight in GA4_DEVICE_WEIGHTS.items():

                # --- SESSIONS (with anomaly check for traffic spike) ---
                session_anomaly = get_anomaly_multiplier(
                    date, "ga4", "sessions",
                    source=channel["source"],
                    medium=channel["medium"],
                )
                base_sessions = (
                    channel["avg_daily_sessions"]
                    * dev_weight
                    * day_mult
                    * growth_mult
                    * session_anomaly
                )
                sessions = max(1, int(add_noise(base_sessions, 0.12)))

                # --- USERS & NEW USERS ---
                users = max(1, int(sessions * add_noise(0.80, 0.05)))
                new_users = max(0, int(users * add_noise(0.66, 0.08)))

                # --- ENGAGEMENT ---
                engagement_rate = add_noise(channel["avg_engagement_rate"], 0.05)
                engagement_rate = max(0.20, min(engagement_rate, 0.95))
                engaged_sessions = max(1, int(sessions * engagement_rate))

                avg_session_duration = max(10, add_noise(180, 0.15))
                events = max(sessions, int(sessions * add_noise(3.7, 0.10)))

                # --- CONVERSIONS & REVENUE ---
                cvr = add_noise(channel["avg_cvr"], 0.10)
                cvr = max(0, min(cvr, 0.20))
                conversions = max(0, int(sessions * cvr))

                aov = add_noise(channel["avg_aov"], 0.08)
                total_revenue = round(conversions * aov, 2)

                # --- BOUNCE RATE (roughly the inverse of engagement rate) ---
                bounce_rate = add_noise(1 - engagement_rate, 0.08)
                bounce_rate = max(0.05, min(bounce_rate, 0.85))

                rows.append({
                    "date": date.strftime("%Y-%m-%d"),
                    "source": channel["source"],
                    "medium": channel["medium"],
                    "market": channel["market"],
                    "device_category": device,
                    "sessions": sessions,
                    "users": users,
                    "new_users": new_users,
                    "engaged_sessions": engaged_sessions,
                    "engagement_rate": round(engagement_rate, 3),
                    "avg_session_duration": round(avg_session_duration, 1),
                    "events": events,
                    "conversions": conversions,
                    "total_revenue": total_revenue,
                    "bounce_rate": round(bounce_rate, 3),
                })

    return pd.DataFrame(rows)


# ================================================================
# SECTION 6: MAIN EXECUTION
# ================================================================
# This block only runs when you execute the script directly:
#   python scripts/generate_sample_data.py
# It does NOT run when another file imports functions from this file.

if __name__ == "__main__":
    print("=" * 60)
    print("  GENERATING SYNTHETIC MARKETING DATA")
    print("=" * 60)

    # Create the output directory if it doesn't exist
    RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)

    start = SIMULATION_START_DATE
    end = SIMULATION_END_DATE

    # --- Google Ads ---
    print(f"\n📊 Generating Google Ads data...")
    df_google = generate_google_ads(start, end)
    google_path = RAW_DATA_DIR / "sample_google_ads.csv"
    df_google.to_csv(google_path, index=False)
    print(f"   ✅ {len(df_google):,} rows saved to {google_path.name}")
    print(f"   📅 {df_google['date'].min()} → {df_google['date'].max()}")
    print(f"   🏷️  Campaigns: {df_google['campaign_name'].nunique()}")
    print(f"   💰 Total spend: ${df_google['cost'].sum():,.2f}")
    print(f"   💵 Total revenue: ${df_google['conversion_value'].sum():,.2f}")

    # --- Meta Ads ---
    print(f"\n📱 Generating Meta Ads data...")
    df_meta = generate_meta_ads(start, end)
    meta_path = RAW_DATA_DIR / "sample_meta_ads.csv"
    df_meta.to_csv(meta_path, index=False)
    print(f"   ✅ {len(df_meta):,} rows saved to {meta_path.name}")
    print(f"   📅 {df_meta['date'].min()} → {df_meta['date'].max()}")
    print(f"   🏷️  Campaigns: {df_meta['campaign_name'].nunique()}")
    print(f"   💰 Total spend: ${df_meta['cost'].sum():,.2f}")
    print(f"   💵 Total revenue: ${df_meta['purchase_value'].sum():,.2f}")

    # --- GA4 ---
    print(f"\n🌐 Generating GA4 data...")
    df_ga4 = generate_ga4(start, end)
    ga4_path = RAW_DATA_DIR / "sample_ga4.csv"
    df_ga4.to_csv(ga4_path, index=False)
    print(f"   ✅ {len(df_ga4):,} rows saved to {ga4_path.name}")
    print(f"   📅 {df_ga4['date'].min()} → {df_ga4['date'].max()}")
    print(f"   📊 Channels: {df_ga4.groupby(['source', 'medium']).ngroups}")
    print(f"   👥 Total sessions: {df_ga4['sessions'].sum():,}")
    print(f"   💵 Total revenue: ${df_ga4['total_revenue'].sum():,.2f}")

    # --- Summary ---
    total_rows = len(df_google) + len(df_meta) + len(df_ga4)
    total_spend = df_google['cost'].sum() + df_meta['cost'].sum()
    total_revenue = (
        df_google['conversion_value'].sum()
        + df_meta['purchase_value'].sum()
        + df_ga4['total_revenue'].sum()
    )

    print(f"\n{'=' * 60}")
    print(f"  ✅ DATA GENERATION COMPLETE")
    print(f"{'=' * 60}")
    print(f"  📁 Files saved to: {RAW_DATA_DIR}")
    print(f"  📊 Total rows generated: {total_rows:,}")
    print(f"  💰 Total ad spend: ${total_spend:,.2f}")
    print(f"  💵 Total revenue (all channels): ${total_revenue:,.2f}")
    print(f"  📈 Blended ROAS (paid only): {total_revenue / total_spend:.2f}x")
    print(f"\n  🔍 Injected anomalies to detect later:")
    print(f"     🔴 Aug 12-14: Google Ads CPC spike +45% (competitor)")
    print(f"     🔴 Sep 03-07: Meta Ads CVR drop -28% (checkout bug)")
    print(f"     🟢 Aug 25-26: GA4 organic traffic spike +67% (viral)")
    print(f"     🟢 Sep 15-21: Google Shopping CVR improvement +35%")
    print(f"{'=' * 60}")