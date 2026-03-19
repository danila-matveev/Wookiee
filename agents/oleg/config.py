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
# Marketplace API Keys (два кабинета: IP и OOO)
# ============================================================================
WB_API_KEY_IP: str = os.getenv("WB_API_KEY_IP", "")
WB_API_KEY_OOO: str = os.getenv("WB_API_KEY_OOO", "")

OZON_CLIENT_ID_IP: str = os.getenv("OZON_CLIENT_ID_IP", "")
OZON_API_KEY_IP: str = os.getenv("OZON_API_KEY_IP", "")
OZON_CLIENT_ID_OOO: str = os.getenv("OZON_CLIENT_ID_OOO", "")
OZON_API_KEY_OOO: str = os.getenv("OZON_API_KEY_OOO", "")


def get_wb_clients() -> dict:
    """Return dict {cabinet_name: WBClient} for all configured cabinets."""
    from shared.clients.wb_client import WBClient
    clients = {}
    if WB_API_KEY_IP:
        clients['IP'] = WBClient(api_key=WB_API_KEY_IP, cabinet_name='IP')
    if WB_API_KEY_OOO:
        clients['OOO'] = WBClient(api_key=WB_API_KEY_OOO, cabinet_name='OOO')
    return clients


def get_ozon_clients() -> dict:
    """Return dict {cabinet_name: OzonClient} for all configured cabinets."""
    from shared.clients.ozon_client import OzonClient
    clients = {}
    if OZON_CLIENT_ID_IP and OZON_API_KEY_IP:
        clients['IP'] = OzonClient(
            client_id=OZON_CLIENT_ID_IP, api_key=OZON_API_KEY_IP, cabinet_name='IP',
        )
    if OZON_CLIENT_ID_OOO and OZON_API_KEY_OOO:
        clients['OOO'] = OzonClient(
            client_id=OZON_CLIENT_ID_OOO, api_key=OZON_API_KEY_OOO, cabinet_name='OOO',
        )
    return clients


# ============================================================================
# Notion
# ============================================================================
NOTION_TOKEN: str = os.getenv("NOTION_TOKEN", "")
NOTION_DATABASE_ID: str = os.getenv("NOTION_DATABASE_ID", "")

# ============================================================================
# Paths
# ============================================================================
PLAYBOOK_PATH: str = str(Path(__file__).parent / "playbook.md")
MARKETING_PLAYBOOK_PATH: str = str(Path(__file__).parent / "marketing_playbook.md")
FUNNEL_PLAYBOOK_PATH: str = str(Path(__file__).parent / "funnel_playbook.md")
CHRISTINA_PLAYBOOK_PATH: str = str(Path(__file__).parent / "christina_playbook.md")

# ============================================================================
# Scheduler (MSK)
# ============================================================================
TIMEZONE: str = "Europe/Moscow"
DAILY_REPORT_TIME: str = os.getenv("DAILY_REPORT_TIME", "09:00")
WEEKLY_REPORT_TIME: str = os.getenv("WEEKLY_REPORT_TIME", "10:15")
MONTHLY_REPORT_TIME: str = os.getenv("MONTHLY_REPORT_TIME", "10:30")
MONTHLY_PRICE_ANALYSIS_TIME: str = os.getenv("MONTHLY_PRICE_ANALYSIS_TIME", "11:00")
MONTHLY_PRICE_ANALYSIS_DAY: int = int(os.getenv("MONTHLY_PRICE_ANALYSIS_DAY", "1"))
MARKETING_WEEKLY_REPORT_TIME: str = os.getenv("MARKETING_WEEKLY_REPORT_TIME", "11:15")
MARKETING_MONTHLY_REPORT_TIME: str = os.getenv("MARKETING_MONTHLY_REPORT_TIME", "11:30")
FUNNEL_WEEKLY_REPORT_TIME: str = os.getenv("FUNNEL_WEEKLY_REPORT_TIME", "12:00")
PROMOTION_SCAN_ENABLED: bool = os.getenv("PROMOTION_SCAN_ENABLED", "false").lower() in ("true", "1", "yes")

# Finolog (cash flow / ДДС)
FINOLOG_API_KEY: str = os.getenv("FINOLOG_API_KEY", "")
FINOLOG_BIZ_ID: int = int(os.getenv("FINOLOG_BIZ_ID", "48556"))
FINOLOG_WEEKLY_REPORT_TIME: str = os.getenv("FINOLOG_WEEKLY_REPORT_TIME", "18:00")
FINOLOG_CASH_GAP_THRESHOLD: float = float(os.getenv("FINOLOG_CASH_GAP_THRESHOLD", "1000000"))

# ============================================================================
# Executor
# ============================================================================
MAX_ITERATIONS: int = 15
MAX_TOOL_RESULT_LENGTH: int = 8500
TOOL_TIMEOUT_SEC: float = 30.0
TOTAL_TIMEOUT_SEC: float = 300.0
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
# Multi-Model Review
# ============================================================================
REVIEW_ENABLED: bool = os.getenv("OLEG_REVIEW_ENABLED", "true").lower() in ("true", "1", "yes")
REVIEW_MODE: str = os.getenv("OLEG_REVIEW_MODE", "dry_run")  # "dry_run" | "active"
REVIEW_MODEL: str = os.getenv("OLEG_REVIEW_MODEL", FALLBACK_MODEL)
REVIEW_TASK_TYPES: list = [
    t.strip()
    for t in os.getenv("OLEG_REVIEW_TASK_TYPES", "daily,weekly,monthly").split(",")
    if t.strip()
]
REVIEW_MAX_TOKENS: int = int(os.getenv("OLEG_REVIEW_MAX_TOKENS", "16000"))

# ============================================================================
# Anomaly Monitor
# ============================================================================
ANOMALY_MONITOR_ENABLED: bool = os.getenv("ANOMALY_MONITOR_ENABLED", "true").lower() in ("true", "1", "yes")
ANOMALY_MONITOR_INTERVAL_HOURS: int = int(os.getenv("ANOMALY_MONITOR_INTERVAL_HOURS", "4"))
ANOMALY_REVENUE_THRESHOLD: float = float(os.getenv("ANOMALY_REVENUE_THRESHOLD", "20.0"))
ANOMALY_MARGIN_PCT_THRESHOLD: float = float(os.getenv("ANOMALY_MARGIN_PCT_THRESHOLD", "10.0"))
ANOMALY_DRR_THRESHOLD_MONITOR: float = float(os.getenv("ANOMALY_DRR_THRESHOLD_MONITOR", "30.0"))
ANOMALY_ORDERS_THRESHOLD: float = float(os.getenv("ANOMALY_ORDERS_THRESHOLD", "25.0"))
ANOMALY_WEEKEND_MULTIPLIER: float = float(os.getenv("ANOMALY_WEEKEND_MULTIPLIER", "1.5"))

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
