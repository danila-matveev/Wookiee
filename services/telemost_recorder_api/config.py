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

# Bitrix calendar scheduler — auto-queues a recording when a Telemost meeting
# is about to start.
#
#   TELEMOST_SCHEDULER_ENABLED        — master on/off switch (default false).
#                                       Set to "true" on prod when ready to activate.
#   TELEMOST_SCHEDULER_BITRIX_USER_ID — legacy single-user mode: poll only this
#                                       Bitrix user. Leave empty to use multi-user
#                                       mode (iterates telemost.users WHERE is_active).
#   TELEMOST_SCHEDULER_TELEGRAM_ID    — legacy single-user mode: triggered_by value.
SCHEDULER_ENABLED: bool = os.getenv("TELEMOST_SCHEDULER_ENABLED", "false").lower() == "true"
SCHEDULER_BITRIX_USER_ID: str = os.getenv("TELEMOST_SCHEDULER_BITRIX_USER_ID", "").strip()
_raw_scheduler_tg = os.getenv("TELEMOST_SCHEDULER_TELEGRAM_ID", "").strip()
SCHEDULER_TELEGRAM_ID: int | None = int(_raw_scheduler_tg) if _raw_scheduler_tg else None
SCHEDULER_TICK_SECONDS: int = int(os.getenv("TELEMOST_SCHEDULER_TICK_SECONDS", "60"))
# How early before DATE_FROM we queue the recording. Default 90s — enough for
# the recorder container to spawn (~30s) and join before participants do.
SCHEDULER_LEAD_SECONDS: int = int(os.getenv("TELEMOST_SCHEDULER_LEAD_SECONDS", "90"))
# Grace period: catch a meeting we missed (e.g. worker crashed). Don't queue
# anything that started more than this many seconds ago.
SCHEDULER_GRACE_SECONDS: int = int(os.getenv("TELEMOST_SCHEDULER_GRACE_SECONDS", "300"))

# Morning digest — daily DM to each active user with today's meetings.
#
#   MORNING_DIGEST_ENABLED   — master on/off switch (default false).
#                              Set to "true" on prod when ready to activate.
#   MORNING_DIGEST_HOUR_MSK  — hour in Europe/Moscow when digest is sent
#                              (default 9 = 09:00 МСК).
MORNING_DIGEST_ENABLED: bool = (
    os.getenv("MORNING_DIGEST_ENABLED", "false").lower() == "true"
)
MORNING_DIGEST_HOUR_MSK: int = int(os.getenv("MORNING_DIGEST_HOUR_MSK", "9"))

# Voice-triggers pipeline (Phase 1 — detection only, no Bitrix writes).
#
#   VOICE_TRIGGERS_ENABLED  — master on/off switch (default false).
#                             Set to "true" on prod when ready to evaluate
#                             precision/recall on real meetings.
VOICE_TRIGGERS_ENABLED: bool = (
    os.getenv("VOICE_TRIGGERS_ENABLED", "false").lower() == "true"
)

# OpenRouter model tiers used by voice_triggers pipeline.
# LIGHT  — Stage 1: candidate detection (cheap, fast).
# HEAVY  — Stage 2: slot-filling per intent (accurate, $3/$15 per M tokens).
MODEL_LIGHT: str = os.getenv("VOICE_TRIGGERS_MODEL_LIGHT", "google/gemini-3-flash-preview")
MODEL_HEAVY: str = os.getenv("VOICE_TRIGGERS_MODEL_HEAVY", "anthropic/claude-sonnet-4-6")

# Paths
DATA_DIR: Path = _PROJECT_ROOT / "data" / "telemost"
# When the API runs inside a container that talks to the host docker.sock,
# spawned recorder containers must mount the *host* path, not the API
# container's internal /app/data/telemost. Defaults to DATA_DIR so local
# dev / tests work without extra config; production docker-compose sets
# TELEMOST_HOST_DATA_DIR=/home/danila/projects/wookiee/data/telemost.
HOST_DATA_DIR: Path = Path(os.getenv("TELEMOST_HOST_DATA_DIR", str(DATA_DIR)))
ASSETS_DIR: Path = Path(__file__).resolve().parent / "assets"

# Playwright storage_state JSON for a pre-authenticated Yandex 360 Business
# user (e.g. recorder@wookiee.shop). When set, the API mounts this file
# read-only into each spawned recorder container so the bot joins Telemost
# as that authenticated participant — bypassing the guest anti-bot kick.
# Empty/unset = legacy guest mode. Path is a *host* path (must be readable
# by the host docker daemon when bind-mounting into recorder containers).
# Generate via scripts/telemost_export_cookies.py, then copy to the server.
TELEMOST_STORAGE_STATE_PATH: str = os.getenv("TELEMOST_STORAGE_STATE_PATH", "").strip()
