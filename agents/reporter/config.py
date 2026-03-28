# agents/reporter/config.py
"""Reporter V4 configuration — all settings from environment."""
import os
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# ── OpenRouter LLM ────────────────────────────────────────────────────────────
OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
MODEL_PRIMARY: str = os.getenv("REPORTER_MODEL_PRIMARY", "google/gemini-2.5-flash")
MODEL_FALLBACK: str = os.getenv("REPORTER_MODEL_FALLBACK", "google/gemini-2.5-pro-preview-03-25")
MODEL_FREE: str = "openrouter/free"

# ── Telegram ──────────────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN: str = os.getenv("REPORTER_V4_BOT_TOKEN", "")
ADMIN_CHAT_ID: int = int(os.getenv("ADMIN_CHAT_ID", "0"))

# ── Notion ────────────────────────────────────────────────────────────────────
NOTION_TOKEN: str = os.getenv("NOTION_TOKEN", "")
NOTION_DATABASE_ID: str = os.getenv("NOTION_DATABASE_ID", "")

# ── Supabase ──────────────────────────────────────────────────────────────────
SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY: str = os.getenv("SUPABASE_SERVICE_KEY", "")

# ── Database (read-only analytics) ────────────────────────────────────────────
DB_HOST: str = os.getenv("DB_HOST", "")
DB_PORT: int = int(os.getenv("DB_PORT", "6433"))

# ── Timezone & Schedule ───────────────────────────────────────────────────────
TIMEZONE: str = "Europe/Moscow"
DATA_READY_CHECK_HOURS: list[int] = [6, 7, 8, 9, 10, 11, 12]
DEADLINE_HOUR: int = 13
HEARTBEAT_INTERVAL_HOURS: int = 6

# ── Circuit Breaker ───────────────────────────────────────────────────────────
CB_FAILURE_THRESHOLD: int = 3
CB_COOLDOWN_SEC: float = 3600.0

# ── Validator ─────────────────────────────────────────────────────────────────
MIN_TOGGLE_SECTIONS: int = 6
MIN_REPORT_LENGTH: int = 500
MIN_CONFIDENCE: float = 0.3
MAX_PLACEHOLDERS: int = 5

# ── Pipeline ──────────────────────────────────────────────────────────────────
MAX_ATTEMPTS: int = 3
LLM_TIMEOUT: float = 120.0
LLM_MAX_TOKENS: int = 16000

# ── Logging ───────────────────────────────────────────────────────────────────
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

# ── Paths ─────────────────────────────────────────────────────────────────────
PROMPTS_DIR: Path = Path(__file__).parent / "analyst" / "prompts"
TEMPLATES_DIR: Path = Path(__file__).parent / "formatter" / "templates"
