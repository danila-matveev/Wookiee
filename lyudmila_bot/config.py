"""
Configuration for Lyudmila Bot — IEE-агент, бизнес-ассистент Wookiee
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from root .env file
env_path = Path(__file__).resolve().parent.parent / '.env'
load_dotenv(env_path)

# ============================================================================
# Telegram Bot Configuration
# ============================================================================
LYUDMILA_BOT_TOKEN: str = os.getenv("LYUDMILA_BOT_TOKEN", "")

# ============================================================================
# Bitrix24 Configuration
# ============================================================================
BITRIX_WEBHOOK_URL: str = os.getenv("Bitrix_rest_api", "")

# ============================================================================
# AI Configuration — ZAI (primary) + Claude (fallback)
# ============================================================================
ZAI_API_KEY: str = os.getenv("ZAI_API_KEY", "")
ZAI_MODEL: str = "glm-4.5-flash"

CLAUDE_API_KEY: str = os.getenv("CLAUDE_API_KEY", "")
CLAUDE_MODEL: str = "claude-sonnet-4-5-20250929"

# ============================================================================
# Database Configuration
# ============================================================================
SQLITE_DB_PATH: str = str(Path(__file__).resolve().parent / "data" / "lyudmila.db")

# ============================================================================
# Supabase (PostgreSQL) — память Людмилы
# ============================================================================
SUPABASE_HOST: str = os.getenv("SUPABASE_HOST", "")
SUPABASE_PORT: int = int(os.getenv("SUPABASE_PORT", "5432"))
SUPABASE_DB: str = os.getenv("SUPABASE_DB", "postgres")
SUPABASE_USER: str = os.getenv("SUPABASE_USER", "")
SUPABASE_PASSWORD: str = os.getenv("SUPABASE_PASSWORD", "")

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
