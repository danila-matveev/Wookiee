"""Wookiee v3 agent system configuration."""
import os
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# ── OpenRouter ────────────────────────────────────────────────────────────────
OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"

# ── Model tiers ───────────────────────────────────────────────────────────────
MODEL_HEAVY: str = os.getenv("MODEL_HEAVY", "google/gemini-3-flash-preview")
MODEL_MAIN: str = os.getenv("MODEL_MAIN", "z-ai/glm-4.7")
MODEL_LIGHT: str = os.getenv("MODEL_LIGHT", "z-ai/glm-4.7-flash")

# Pricing per 1K tokens (USD)
PRICING: dict = {
    "z-ai/glm-4.7-flash": {"input": 0.00007, "output": 0.0003},
    "z-ai/glm-4.7": {"input": 0.00006, "output": 0.0004},
    "google/gemini-3-flash-preview": {"input": 0.0005, "output": 0.003},
}

# ── Agent MD files directory ──────────────────────────────────────────────────
AGENTS_DIR: Path = PROJECT_ROOT / "agents" / "v3" / "agents"

# ── Timeouts (seconds) ────────────────────────────────────────────────────────
AGENT_TIMEOUT: int = int(os.getenv("AGENT_TIMEOUT", "120"))
ORCHESTRATOR_TIMEOUT: int = int(os.getenv("ORCHESTRATOR_TIMEOUT", "600"))

# ── Telegram ──────────────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
ADMIN_CHAT_ID: int = int(os.getenv("ADMIN_CHAT_ID", "0"))

# ── Notion ────────────────────────────────────────────────────────────────────
NOTION_TOKEN: str = os.getenv("NOTION_TOKEN", "")
NOTION_DATABASE_ID: str = os.getenv("NOTION_DATABASE_ID", "")

# ── Timezone & Scheduler ──────────────────────────────────────────────────────
TIMEZONE: str = "Europe/Moscow"
DAILY_REPORT_TIME: str = os.getenv("DAILY_REPORT_TIME", "09:00")
WEEKLY_REPORT_TIME: str = os.getenv("WEEKLY_REPORT_TIME", "10:15")
MONTHLY_REPORT_TIME: str = os.getenv("MONTHLY_REPORT_TIME", "10:30")
MONTHLY_PRICE_ANALYSIS_TIME: str = os.getenv("MONTHLY_PRICE_ANALYSIS_TIME", "11:00")
MONTHLY_PRICE_ANALYSIS_DAY: int = int(os.getenv("MONTHLY_PRICE_ANALYSIS_DAY", "1"))
MARKETING_WEEKLY_REPORT_TIME: str = os.getenv("MARKETING_WEEKLY_REPORT_TIME", "11:15")
MARKETING_MONTHLY_REPORT_TIME: str = os.getenv("MARKETING_MONTHLY_REPORT_TIME", "11:30")
FUNNEL_WEEKLY_REPORT_TIME: str = os.getenv("FUNNEL_WEEKLY_REPORT_TIME", "12:00")
FINOLOG_WEEKLY_REPORT_TIME: str = os.getenv("FINOLOG_WEEKLY_REPORT_TIME", "18:00")

# ── Finolog (cash flow / ДДС) ─────────────────────────────────────────────────
FINOLOG_API_KEY: str = os.getenv("FINOLOG_API_KEY", "")
FINOLOG_BIZ_ID: int = int(os.getenv("FINOLOG_BIZ_ID", "48556"))
FINOLOG_CASH_GAP_THRESHOLD: float = float(os.getenv("FINOLOG_CASH_GAP_THRESHOLD", "1000000"))

# ── Anomaly thresholds ────────────────────────────────────────────────────────
ANOMALY_MARGIN_THRESHOLD: float = float(os.getenv("ANOMALY_MARGIN_THRESHOLD", "10.0"))
ANOMALY_DRR_THRESHOLD: float = float(os.getenv("ANOMALY_DRR_THRESHOLD", "30.0"))
ANOMALY_REVENUE_THRESHOLD: float = float(os.getenv("ANOMALY_REVENUE_THRESHOLD", "20.0"))
ANOMALY_MARGIN_PCT_THRESHOLD: float = float(os.getenv("ANOMALY_MARGIN_PCT_THRESHOLD", "10.0"))
ANOMALY_DRR_THRESHOLD_MONITOR: float = float(os.getenv("ANOMALY_DRR_THRESHOLD_MONITOR", "30.0"))
ANOMALY_ORDERS_THRESHOLD: float = float(os.getenv("ANOMALY_ORDERS_THRESHOLD", "25.0"))
ANOMALY_WEEKEND_MULTIPLIER: float = float(os.getenv("ANOMALY_WEEKEND_MULTIPLIER", "1.5"))

# ── Monitor & Watchdog intervals ──────────────────────────────────────────────
ANOMALY_MONITOR_INTERVAL_HOURS: int = int(os.getenv("ANOMALY_MONITOR_INTERVAL_HOURS", "4"))
WATCHDOG_HEARTBEAT_INTERVAL_HOURS: int = int(os.getenv("WATCHDOG_HEARTBEAT_INTERVAL_HOURS", "6"))

# ── Circuit Breaker ───────────────────────────────────────────────────────────
CB_FAILURE_THRESHOLD: int = int(os.getenv("CB_FAILURE_THRESHOLD", "3"))
CB_COOLDOWN_SEC: float = float(os.getenv("CB_COOLDOWN_SEC", "300.0"))

# ── Database (PostgreSQL, read-only analytics DB) ─────────────────────────────
DB_HOST: str = os.getenv("DB_HOST", "")
DB_PORT: int = int(os.getenv("DB_PORT", "6433"))
DB_USER: str = os.getenv("DB_USER", "")
DB_PASSWORD: str = os.getenv("DB_PASSWORD", "")
DB_NAME_WB: str = os.getenv("DB_NAME_WB", "pbi_wb_wookiee")
DB_NAME_OZON: str = os.getenv("DB_NAME_OZON", "pbi_ozon_wookiee")

# ── SQLite state store ────────────────────────────────────────────────────────
STATE_DB_PATH: str = os.getenv(
    "V3_STATE_DB_PATH",
    str(PROJECT_ROOT / "agents" / "v3" / "data" / "v3_state.db"),
)

# ── Logging ───────────────────────────────────────────────────────────────────
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

# ── Feature flags ─────────────────────────────────────────────────────────────
PROMOTION_SCAN_ENABLED: bool = os.getenv("PROMOTION_SCAN_ENABLED", "false").lower() in (
    "true", "1", "yes",
)
