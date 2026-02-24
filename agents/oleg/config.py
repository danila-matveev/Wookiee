"""
Configuration for Oleg v2.

Inherits from shared/config.py, adds v2-specific settings.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(PROJECT_ROOT / '.env')


def _env_first(keys, default=""):
    """Return first non-empty env value from list of keys."""
    for k in keys:
        v = os.getenv(k)
        if v not in (None, ""):
            return v
    return default


# ============================================================================
# Telegram
# ============================================================================
TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")

# ============================================================================
# Authentication
# ============================================================================
AUTH_ENABLED: bool = os.getenv("AUTH_ENABLED", "true").lower() in ("true", "1", "yes")
HASHED_PASSWORD: str = os.getenv("BOT_PASSWORD_HASH", "").strip("'\"")

# ============================================================================
# AI Providers — all via OpenRouter
# ============================================================================
OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")

# Model tiers
CLASSIFY_MODEL: str = os.getenv("OLEG_CLASSIFY_MODEL", "z-ai/glm-4.7-flash")   # LIGHT
ANALYTICS_MODEL: str = os.getenv("OLEG_ANALYTICS_MODEL", "z-ai/glm-4.7")       # MAIN
FALLBACK_MODEL: str = os.getenv("OLEG_FALLBACK_MODEL", "google/gemini-3-flash-preview")  # HEAVY

AI_BASE_URL: str = os.getenv("AI_BASE_URL", "https://openrouter.ai/api/v1")
AI_API_KEY: str = OPENROUTER_API_KEY
AI_MODEL: str = ANALYTICS_MODEL

# Pricing per 1K tokens (USD)
PRICING: dict = {
    "z-ai/glm-4.7-flash": {"input": 0.00007, "output": 0.0003},
    "z-ai/glm-4.7": {"input": 0.00006, "output": 0.0004},
    "google/gemini-3-flash-preview": {"input": 0.0005, "output": 0.003},
    "openrouter/free": {"input": 0.0, "output": 0.0},
}

# ============================================================================
# Database (PostgreSQL)
# ============================================================================
DB_HOST: str = os.getenv("DB_HOST", "")
DB_PORT: int = int(os.getenv("DB_PORT", "6433"))
DB_USER: str = os.getenv("DB_USER", "")
DB_PASSWORD: str = os.getenv("DB_PASSWORD", "")
DB_NAME_WB: str = os.getenv("DB_NAME_WB", "pbi_wb_wookiee")
DB_NAME_OZON: str = os.getenv("DB_NAME_OZON", "pbi_ozon_wookiee")

DB_CONFIG: dict = {
    "host": DB_HOST,
    "port": DB_PORT,
    "user": DB_USER,
    "password": DB_PASSWORD,
}

# Supabase
SUPABASE_ENV_PATH: str = os.getenv(
    "SUPABASE_ENV_PATH",
    str(PROJECT_ROOT / "sku_database" / ".env"),
)

# SQLite (local state, reports, feedback)
SQLITE_DB_PATH: str = str(Path(__file__).parent / "data" / "oleg.db")

# ============================================================================
# Notion
# ============================================================================
NOTION_TOKEN: str = os.getenv("NOTION_TOKEN", "")
NOTION_DATABASE_ID: str = os.getenv("NOTION_DATABASE_ID", "")

# ============================================================================
# Paths
# ============================================================================
PLAYBOOK_PATH: str = str(Path(__file__).parent / "playbook.md")

# ============================================================================
# Scheduler (MSK)
# ============================================================================
TIMEZONE: str = "Europe/Moscow"
DAILY_REPORT_TIME: str = os.getenv("DAILY_REPORT_TIME", "09:00")
WEEKLY_REPORT_TIME: str = os.getenv("WEEKLY_REPORT_TIME", "10:15")

# ============================================================================
# Executor
# ============================================================================
MAX_ITERATIONS: int = 10
MAX_TOOL_RESULT_LENGTH: int = 8500
TOOL_TIMEOUT_SEC: float = 30.0
TOTAL_TIMEOUT_SEC: float = 120.0
CONTEXT_COMPRESSION_AFTER: int = 5

# ============================================================================
# Circuit Breaker
# ============================================================================
CB_FAILURE_THRESHOLD: int = 3
CB_COOLDOWN_SEC: float = 300.0  # 5 minutes

# ============================================================================
# Orchestrator
# ============================================================================
MAX_CHAIN_STEPS: int = 5
ANOMALY_MARGIN_THRESHOLD: float = 10.0   # margin change > 10% triggers escalation
ANOMALY_DRR_THRESHOLD: float = 30.0      # DRR change > 30% triggers escalation

# ============================================================================
# Watchdog
# ============================================================================
WATCHDOG_HEARTBEAT_INTERVAL_HOURS: int = 6
ADMIN_CHAT_ID: int = int(os.getenv("ADMIN_CHAT_ID", "0"))

# ============================================================================
# Logging
# ============================================================================
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE: str = str(Path(__file__).parent / "logs" / "oleg.log")

# ============================================================================
# Auth persistence
# ============================================================================
USERS_FILE_PATH: str = str(Path(__file__).parent / "data" / "authenticated_users.json")
