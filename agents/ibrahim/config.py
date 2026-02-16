"""Configuration for Ibrahim Agent — autonomous data engineer."""

import os
from pathlib import Path

from shared.config import (
    MARKETPLACE_DB_CONFIG,
    DB_CONFIG, DB_WB, DB_OZON,
    OPENROUTER_API_KEY,
    IBRAHIM_LLM_MODEL,
    SYNC_SCHEDULE,
    TIMEZONE,
)

# ============================================================================
# Agent paths
# ============================================================================
AGENT_DIR = Path(__file__).resolve().parent
DATA_DIR = AGENT_DIR / "data"
LOGS_DIR = AGENT_DIR / "logs"
SQLITE_DB = DATA_DIR / "ibrahim.db"
API_DOCS_CACHE_DIR = DATA_DIR / "api_docs_cache"
SCHEMA_PROPOSALS_DIR = DATA_DIR / "schema_proposals"

# ============================================================================
# LLM
# ============================================================================
LLM_API_KEY = OPENROUTER_API_KEY
LLM_MODEL = IBRAHIM_LLM_MODEL

# ============================================================================
# Schedule (reuse from shared config)
# ============================================================================
# Daily ETL sync hour:minute
_parts = SYNC_SCHEDULE.split(":")
SYNC_HOUR = int(_parts[0]) if len(_parts) >= 2 else 5
SYNC_MINUTE = int(_parts[1]) if len(_parts) >= 2 else 0

# Weekly analysis: Sunday 03:00
WEEKLY_DAY = os.getenv("IBRAHIM_WEEKLY_DAY", "sun")
WEEKLY_HOUR = int(os.getenv("IBRAHIM_WEEKLY_HOUR", "3"))
WEEKLY_MINUTE = int(os.getenv("IBRAHIM_WEEKLY_MINUTE", "0"))

# ============================================================================
# Reconciliation
# ============================================================================
RECONCILIATION_THRESHOLD_PCT = 1.0

# ============================================================================
# Logging
# ============================================================================
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = str(LOGS_DIR / "ibrahim.log")
