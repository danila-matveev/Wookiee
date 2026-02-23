"""
Configuration for Lyudmila Bot — IEE-агент, бизнес-ассистент Wookiee
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from root .env file
env_path = Path(__file__).resolve().parent.parent / '.env'
load_dotenv(env_path)


def _env_first(keys, default=""):
    for k in keys:
        v = os.getenv(k)
        if v not in (None, ""):
            return v
    return default

# ============================================================================
# Telegram Bot Configuration
# ============================================================================
LYUDMILA_BOT_TOKEN: str = os.getenv("LYUDMILA_BOT_TOKEN", "")

# ============================================================================
# Bitrix24 Configuration
# ============================================================================
BITRIX_WEBHOOK_URL: str = os.getenv("Bitrix_rest_api", "")

# ============================================================================
# AI Configuration — OpenRouter (единый провайдер)
# ============================================================================
OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
LIGHT_MODEL: str = os.getenv("LYUDMILA_LIGHT_MODEL", "z-ai/glm-4.7-flash")
MAIN_MODEL: str = os.getenv("LYUDMILA_MAIN_MODEL", "z-ai/glm-4.7")

# ============================================================================
# Database Configuration
# ============================================================================
SQLITE_DB_PATH: str = str(Path(__file__).resolve().parent / "data" / "lyudmila.db")

# ============================================================================
# Supabase (PostgreSQL) — память Людмилы
# ============================================================================
SUPABASE_HOST: str = _env_first(["POSTGRES_HOST", "SUPABASE_HOST"], "")
SUPABASE_PORT: int = int(_env_first(["POSTGRES_PORT", "SUPABASE_PORT"], "5432"))
SUPABASE_DB: str = _env_first(["POSTGRES_DB", "SUPABASE_DB"], "postgres")
SUPABASE_USER: str = _env_first(["POSTGRES_USER", "SUPABASE_USER"], "")
SUPABASE_PASSWORD: str = _env_first(["POSTGRES_PASSWORD", "SUPABASE_PASSWORD"], "")

# ============================================================================
# Scheduler Configuration
# ============================================================================
DEFAULT_DIGEST_TIME: str = "09:00"
DEFAULT_TIMEZONE: str = "Europe/Moscow"

# ============================================================================
# User Cache
# ============================================================================
USER_CACHE_REFRESH_MINUTES: int = 30
FUZZY_MATCH_THRESHOLD: int = 60

# ============================================================================
# Logging
# ============================================================================
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE: str = str(Path(__file__).resolve().parent / "logs" / "lyudmila.log")
