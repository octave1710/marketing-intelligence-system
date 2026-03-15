"""
Configuration globale du projet Marketing Intelligence System.
Centralise tous les paramètres. Modifier ici = modifier partout.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ============================================================
# CHEMINS
# ============================================================
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
DATABASE_DIR = DATA_DIR / "database"
DATABASE_PATH = DATABASE_DIR / "marketing_data.db"

# ============================================================
# API
# ============================================================
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.3"))
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "4000"))

# ============================================================
# DONNÉES
# ============================================================
DATE_FORMAT = "%Y-%m-%d"
SIMULATION_START_DATE = "2024-07-01"
SIMULATION_END_DATE = "2024-09-30"

MARKETS = ["US", "UK", "FR", "DE"]
DEVICES = ["desktop", "mobile", "tablet"]

MARKET_WEIGHTS = {"US": 0.45, "UK": 0.25, "FR": 0.18, "DE": 0.12}
DEVICE_WEIGHTS = {"desktop": 0.35, "mobile": 0.55, "tablet": 0.10}

# ============================================================
# ANOMALIES
# ============================================================
ZSCORE_THRESHOLD = 2.5
PCT_CHANGE_THRESHOLD = 0.30
IQR_MULTIPLIER = 1.5
MIN_IMPRESSIONS_FILTER = 100

# ============================================================
# BUSINESS
# ============================================================
TARGET_ROAS = 4.0
TARGET_CPA = 35.0
MAX_FREQUENCY = 3.0