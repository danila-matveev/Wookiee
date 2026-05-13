"""Phase 0 config. All required env vars validated at import time."""
from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import quote_plus

from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Tests can opt out of .env loading by setting TELEMOST_DISABLE_DOTENV=1
# before patching the environment. In production this stays unset so .env
# is loaded normally.
if os.getenv("TELEMOST_DISABLE_DOTENV") != "1":
    load_dotenv(_PROJECT_ROOT / ".env")


def _required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Required env var {name} is missing")
    return value


# Telegram bot
TELEMOST_BOT_TOKEN: str = _required("TELEMOST_BOT_TOKEN")
TELEMOST_BOT_ID: int = int(_required("TELEMOST_BOT_ID"))
TELEMOST_BOT_USERNAME: str = _required("TELEMOST_BOT_USERNAME")
TELEMOST_WEBHOOK_SECRET: str = _required("TELEMOST_WEBHOOK_SECRET")
# Public URL of the API used by Telegram to deliver webhook updates. If unset
# (e.g. local dev / tests), startup skips automatic webhook registration and
# the operator is expected to set it manually via Bot API.
TELEMOST_PUBLIC_URL: str = os.getenv("TELEMOST_PUBLIC_URL", "").rstrip("/")

# Supabase
SUPABASE_URL: str = _required("SUPABASE_URL")
SUPABASE_SERVICE_KEY: str = _required("SUPABASE_SERVICE_KEY")

# Database (built from project-convention vars used by shared/data_layer/_connection.py)
_DB_HOST: str = _required("SUPABASE_HOST")
_DB_PORT: str = os.getenv("SUPABASE_PORT", "5432")
_DB_NAME: str = os.getenv("SUPABASE_DB", "postgres")
_DB_USER: str = _required("SUPABASE_USER")
_DB_PASSWORD: str = _required("SUPABASE_PASSWORD")
DATABASE_URL: str = (
    f"postgresql://{_DB_USER}:{quote_plus(_DB_PASSWORD)}"
    f"@{_DB_HOST}:{_DB_PORT}/{_DB_NAME}?sslmode=require"
)

# External APIs
SPEECHKIT_API_KEY: str = _required("SPEECHKIT_API_KEY")
YANDEX_FOLDER_ID: str = _required("YANDEX_FOLDER_ID")
OPENROUTER_API_KEY: str = _required("OPENROUTER_API_KEY")
BITRIX24_WEBHOOK_URL: str = _required("BITRIX24_WEBHOOK_URL")

# Tunables
MAX_PARALLEL_RECORDINGS: int = int(os.getenv("MAX_PARALLEL_RECORDINGS", "1"))
AUDIO_RETENTION_DAYS: int = int(os.getenv("AUDIO_RETENTION_DAYS", "30"))
RECORDING_HARD_LIMIT_HOURS: int = int(os.getenv("RECORDING_HARD_LIMIT_HOURS", "4"))
LLM_POSTPROCESS_MODEL: str = os.getenv("LLM_POSTPROCESS_MODEL", "google/gemini-2.5-flash")
LLM_POSTPROCESS_TIMEOUT_SECONDS: int = int(os.getenv("LLM_POSTPROCESS_TIMEOUT_SECONDS", "120"))
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

# HTTP timeouts for external services. Defaults are tuned per-API:
# - Telegram: 60s — sendDocument с длинным transcript-файлом (до нескольких MB)
#   и sendMessage с большой клавиатурой может занимать заметное время на стороне
#   Bot API.
# - Notion: 30s — обычный REST с пагинацией, иногда блочные PATCH-и медленные.
# - Bitrix: 15s — calendar.event.get на коротком окне ±2ч, отвечает быстро,
#   но REST вебхук Bitrix24 нестабилен под нагрузкой.
# - Supabase Storage: 120s — заливка opus-аудио до сотен MB по медленному
#   серверному каналу; 5s (httpx default) обрывал заливки длинных встреч.
TELEGRAM_TIMEOUT_SECONDS: float = float(os.getenv("TELEGRAM_TIMEOUT_SECONDS", "60"))
NOTION_TIMEOUT_SECONDS: float = float(os.getenv("NOTION_TIMEOUT_SECONDS", "30"))
BITRIX_TIMEOUT_SECONDS: float = float(os.getenv("BITRIX_TIMEOUT_SECONDS", "15"))
SUPABASE_STORAGE_TIMEOUT_SECONDS: float = float(
    os.getenv("SUPABASE_STORAGE_TIMEOUT_SECONDS", "120")
)

# Paths
DATA_DIR: Path = _PROJECT_ROOT / "data" / "telemost"
# When the API runs inside a container that talks to the host docker.sock,
# spawned recorder containers must mount the *host* path, not the API
# container's internal /app/data/telemost. Defaults to DATA_DIR so local
# dev / tests work without extra config; production docker-compose sets
# TELEMOST_HOST_DATA_DIR=/home/danila/projects/wookiee/data/telemost.
HOST_DATA_DIR: Path = Path(os.getenv("TELEMOST_HOST_DATA_DIR", str(DATA_DIR)))
ASSETS_DIR: Path = Path(__file__).resolve().parent / "assets"
