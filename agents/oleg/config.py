"""
Configuration for Oleg Analytics Telegram Bot.
Merged from bot/config.py + scripts/config.py.
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
HASHED_PASSWORD: str = os.getenv(
    "BOT_PASSWORD_HASH",
    "$2b$12$LQ3fPZJ5ZqX5ZqX5ZqX5ZeX5ZqX5ZqX5ZqX5ZqX5ZqX5ZqX5ZqX5Zq"  # PLACEHOLDER
).strip("'\"")

# ============================================================================
# AI Providers — всё через OpenRouter
# ============================================================================
OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")

# Model tiers
CLASSIFY_MODEL: str = os.getenv("OLEG_CLASSIFY_MODEL", "z-ai/glm-4.7-flash")   # LIGHT
ANALYTICS_MODEL: str = os.getenv("OLEG_ANALYTICS_MODEL", "z-ai/glm-4.7")       # MAIN
FALLBACK_MODEL: str = os.getenv("OLEG_FALLBACK_MODEL", "google/gemini-3-flash-preview")  # HEAVY

# ============================================================================
# AI API (OpenRouter — primary provider)
# ============================================================================
AI_BASE_URL: str = os.getenv("AI_BASE_URL", "https://openrouter.ai/api/v1")
AI_API_KEY: str = OPENROUTER_API_KEY
AI_MODEL: str = ANALYTICS_MODEL  # "z-ai/glm-4.7" (for tool-use / analytics)
AI_CLASSIFY_MODEL: str = CLASSIFY_MODEL  # "z-ai/glm-4.7-flash" (for classification)

# Backward-compatible aliases
ZAI_API_KEY: str = AI_API_KEY
ZAI_MODEL: str = AI_CLASSIFY_MODEL
OLEG_MODEL: str = AI_MODEL

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

# Optional: SKU database (Supabase pooler) — used when SKU access required
SKU_DB_HOST: str = _env_first(["POSTGRES_HOST", "SUPABASE_HOST"], "")
SKU_DB_PORT: int = int(_env_first(["POSTGRES_PORT", "SUPABASE_PORT"], "5432"))
SKU_DB_NAME: str = _env_first(["POSTGRES_DB", "SUPABASE_DB"], "postgres")
SKU_DB_USER: str = _env_first(["POSTGRES_USER", "SUPABASE_USER"], "")
SKU_DB_PASSWORD: str = _env_first(["POSTGRES_PASSWORD", "SUPABASE_PASSWORD"], "")

DB_CONFIG: dict = {
    "host": DB_HOST,
    "port": DB_PORT,
    "user": DB_USER,
    "password": DB_PASSWORD,
}

# Supabase (товарная матрица)
SUPABASE_ENV_PATH: str = os.getenv(
    "SUPABASE_ENV_PATH",
    str(PROJECT_ROOT / "sku_database" / ".env"),
)

# SQLite (local report history)
SQLITE_DB_PATH: str = str(Path(__file__).parent / "data" / "reports.db")

# ============================================================================
# Notion
# ============================================================================
NOTION_TOKEN: str = os.getenv("NOTION_TOKEN", "")
NOTION_DATABASE_ID: str = os.getenv("NOTION_DATABASE_ID", "")

# ============================================================================
# Paths
# ============================================================================
PLAYBOOK_PATH: str = str(Path(__file__).parent / "playbook.md")
FEEDBACK_LOG_PATH: str = str(Path(__file__).parent / "feedback_log.md")

# ============================================================================
# Scheduler (MSK)
# ============================================================================
TIMEZONE: str = "Europe/Moscow"
DAILY_REPORT_TIME: str = os.getenv("DAILY_REPORT_TIME", "09:00")
WEEKLY_REPORT_TIME: str = os.getenv("WEEKLY_REPORT_TIME", "10:15")
MONTHLY_REPORT_TIME: str = os.getenv("MONTHLY_REPORT_TIME", "10:30")

# ============================================================================
# Reports
# ============================================================================
REPORT_RETENTION_DAYS: int = 90

# ============================================================================
# Logging
# ============================================================================
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE: str = str(Path(__file__).parent / "logs" / "bot.log")

# ============================================================================
# Auth persistence
# ============================================================================
USERS_FILE_PATH: str = str(Path(__file__).parent / "data" / "authenticated_users.json")
ADMIN_CHAT_ID: int = int(os.getenv("ADMIN_CHAT_ID", "0"))
