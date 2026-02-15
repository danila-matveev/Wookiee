"""
Configuration for Oleg Analytics Telegram Bot.
Merged from bot/config.py + scripts/config.py.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / '.env')

# ============================================================================
# Telegram
# ============================================================================
TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")

# ============================================================================
# Authentication
# ============================================================================
HASHED_PASSWORD: str = os.getenv(
    "BOT_PASSWORD_HASH",
    "$2b$12$LQ3fPZJ5ZqX5ZqX5ZqX5ZeX5ZqX5ZqX5ZqX5ZqX5ZqX5ZqX5ZqX5Zq"  # PLACEHOLDER
)

# ============================================================================
# AI (z.ai — единственный провайдер)
# ============================================================================
ZAI_API_KEY: str = os.getenv("ZAI_API_KEY", "")
ZAI_MODEL: str = "glm-4.5-flash"       # Для classify/clarify задач
OLEG_MODEL: str = "glm-4-plus"          # Для аналитики (tool-use)

# Pricing per 1K tokens (USD)
PRICING: dict = {
    "claude-opus-4-6": {"input": 0.015, "output": 0.075},
    "claude-sonnet-4-5-20250929": {"input": 0.003, "output": 0.015},
    "glm-4-plus": {"input": 0.007, "output": 0.007},
    "glm-4.5-flash": {"input": 0.0001, "output": 0.0002},
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
DAILY_REPORT_TIME: str = os.getenv("DAILY_REPORT_TIME", "10:05")
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
