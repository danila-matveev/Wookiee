# Telemost Recorder Phase 0 — Telegram-only MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Пользователь пишет `/record <url>` в `@wookiee_recorder_bot` → через ~50 минут получает в DM structured summary + полный transcript как `.txt` attachment.

**Architecture:** Один долгоживущий FastAPI-сервис `telemost_recorder_api` (порт 8006) принимает Telegram webhook, кладёт задачу в Postgres-очередь (`telemost.meetings`). Asyncio worker-loop забирает задачу через `FOR UPDATE SKIP LOCKED`, спавнит разовый Docker-контейнер существующего `telemost_recorder` через mounted Docker socket, после exit читает `audio.opus` + `raw_segments.json` из shared volume. Postprocess-worker делает single-call Gemini Flash → structured JSON → апдейтит meeting. Notifier шлёт DM триггерщику с idempotent-защитой.

**Tech Stack:** Python 3.11, FastAPI + uvicorn, asyncpg (Supabase pool), docker SDK (Python), httpx (Telegram API + OpenRouter), pyyaml, существующий recorder-контейнер `telemost_recorder:latest`.

**Spec:** [docs/superpowers/specs/2026-05-07-telemost-recorder-production-design.md](../specs/2026-05-07-telemost-recorder-production-design.md), Section 11 «Phase 0».

**Branch:** `telemost-recorder-phase-0` (создаётся отдельно от `catalog-rework-2026-05-07`, чтобы автопул main не подхватил незавершённую работу).

---

## File Structure

**Создаём:**
```
services/telemost_recorder_api/
├── __init__.py
├── app.py                              # FastAPI factory create_app()
├── config.py                           # env vars
├── db.py                               # asyncpg pool (lifespan-managed)
├── url_canon.py                        # canonicalize_telemost_url
├── telegram_client.py                  # tg_call() httpx wrapper
├── auth.py                             # bitrix_user_sync, get_user_by_tg_id
├── docker_client.py                    # spawn_recorder, monitor_container
├── llm_postprocess.py                  # postprocess_meeting (single LLM call)
├── notifier.py                         # send_meeting_result (idempotent + chunked)
├── audio_uploader.py                   # upload_to_supabase_storage
├── routes/
│   ├── __init__.py
│   ├── telegram.py                     # POST /telegram/webhook
│   └── health.py                       # GET /health
├── workers/
│   ├── __init__.py
│   ├── recorder_worker.py              # picks queued, spawns container
│   └── postprocess_worker.py           # picks recorded, calls LLM, notifies
├── assets/
│   └── avatar.png                      # 512×512 bot avatar (commit binary)
└── migrations/
    ├── 001_schema_users_meetings.sql
    └── 002_processed_calendar_events.sql

scripts/
├── telemost_setup_webhook.py           # one-shot setWebhook + setMyCommands
└── telemost_audio_cleanup.py           # daily cron (Phase 0: skeleton, Phase 1: cron)

deploy/
├── Dockerfile.telemost_recorder_api    # python:3.11-slim, без playwright
└── docker-compose.yml                  # MODIFY: добавить service telemost-recorder-api

tests/services/telemost_recorder_api/
├── __init__.py
├── conftest.py                         # mock_docker, mock_tg, db_pool
├── test_url_canon.py
├── test_auth.py
├── test_telegram_routes.py
├── test_recorder_worker.py
├── test_postprocess.py
├── test_notifier.py
└── test_health.py
```

**Модифицируем:**
- `.env` (локально + на сервере) — уже добавлены `TELEMOST_BOT_TOKEN`, `TELEMOST_BOT_USERNAME`, `TELEMOST_BOT_ID`. Добавить `TELEMOST_WEBHOOK_SECRET`.
- `deploy/docker-compose.yml` — service `telemost-recorder-api`.
- `deploy/Caddyfile` — `recorder.os.wookiee.shop` → `telemost_recorder_api:8006`.

**НЕ трогаем:**
- `services/telemost_recorder/` — существующий recorder-контейнер. API передаёт ему параметры через CLI args, контейнер пишет artefacts в shared volume `data/telemost/{meeting_id}/`.

---

## Task 1: Capacity Check + Branch Setup

**Files:**
- Read-only: server `/home`, `free -h`, `df -h`
- Modify (locally): nothing — это pre-flight check

- [ ] **Step 1: Проверить capacity на сервере**

```bash
ssh timeweb "free -h && df -h /home && docker ps | wc -l && docker images | grep telemost_recorder"
```

Expected: free RAM ≥ 4GB, free disk на `/home` ≥ 10GB, образ `telemost_recorder:latest` существует.

- [ ] **Step 2: Установить `MAX_PARALLEL_RECORDINGS` по результату**

Записать в head плана решение:
- ≥ 8GB free → `MAX_PARALLEL_RECORDINGS=5` (но Phase 0 всё равно использует 1)
- 4–8GB → `MAX_PARALLEL_RECORDINGS=3`
- < 4GB → `MAX_PARALLEL_RECORDINGS=2` + alert владельцу через `TELEGRAM_ALERTS_BOT`

Phase 0 hardcoded `MAX_PARALLEL_RECORDINGS=1` независимо от capacity (упрощение). Реальный лимит включаем в Phase 1.

- [ ] **Step 3: Создать ветку**

```bash
git checkout main
git pull
git checkout -b telemost-recorder-phase-0
```

- [ ] **Step 4: Commit пустого scaffolding**

```bash
mkdir -p services/telemost_recorder_api/routes services/telemost_recorder_api/workers \
         services/telemost_recorder_api/migrations services/telemost_recorder_api/assets \
         tests/services/telemost_recorder_api
touch services/telemost_recorder_api/__init__.py \
      services/telemost_recorder_api/routes/__init__.py \
      services/telemost_recorder_api/workers/__init__.py \
      tests/services/telemost_recorder_api/__init__.py
git add services/telemost_recorder_api tests/services/telemost_recorder_api
git commit -m "feat(telemost-api): scaffolding for Phase 0"
```

---

## Task 2: DB Migrations — schema + 3 tables

**Files:**
- Create: `services/telemost_recorder_api/migrations/001_schema_users_meetings.sql`
- Create: `services/telemost_recorder_api/migrations/002_processed_calendar_events.sql`
- Test (manual): apply via Supabase MCP `apply_migration`

- [ ] **Step 1: Написать миграцию 001**

Создать `services/telemost_recorder_api/migrations/001_schema_users_meetings.sql`:

```sql
-- 001_schema_users_meetings.sql
CREATE SCHEMA IF NOT EXISTS telemost;
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "moddatetime";

CREATE TABLE telemost.users (
    telegram_id   bigint PRIMARY KEY,
    bitrix_id     text NOT NULL UNIQUE,
    name          text NOT NULL,
    short_name    text,
    is_active     boolean NOT NULL DEFAULT true,
    synced_at     timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE telemost.users ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON telemost.users FROM anon;

CREATE TABLE telemost.meetings (
    id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source               text NOT NULL CHECK (source IN ('telegram','calendar')),
    source_event_id      text,
    triggered_by         bigint REFERENCES telemost.users(telegram_id),
    meeting_url          text NOT NULL,
    title                text,
    organizer_id         bigint REFERENCES telemost.users(telegram_id),
    invitees             jsonb NOT NULL DEFAULT '[]',
    scheduled_at         timestamptz,
    started_at           timestamptz,
    ended_at             timestamptz,
    duration_seconds     integer,
    status               text NOT NULL DEFAULT 'queued'
                          CHECK (status IN ('queued','recording','postprocessing','done','failed')),
    error                text,
    audio_path           text,
    audio_expires_at     timestamptz,
    raw_segments         jsonb,
    processed_paragraphs jsonb,
    speakers_map         jsonb,
    summary              jsonb,
    tags                 text[],
    notified_at          timestamptz,
    created_at           timestamptz NOT NULL DEFAULT now(),
    updated_at           timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_meetings_status ON telemost.meetings(status);
CREATE INDEX idx_meetings_scheduled ON telemost.meetings(scheduled_at);
CREATE INDEX idx_meetings_source_event ON telemost.meetings(source_event_id)
    WHERE source_event_id IS NOT NULL;
CREATE INDEX idx_meetings_audio_expires ON telemost.meetings(audio_expires_at)
    WHERE audio_path IS NOT NULL;
CREATE UNIQUE INDEX idx_meetings_active_unique
    ON telemost.meetings (meeting_url)
    WHERE status IN ('queued','recording','postprocessing');

ALTER TABLE telemost.meetings ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON telemost.meetings FROM anon;

CREATE TRIGGER meetings_updated_at BEFORE UPDATE ON telemost.meetings
    FOR EACH ROW EXECUTE FUNCTION moddatetime(updated_at);
```

- [ ] **Step 2: Написать миграцию 002**

Создать `services/telemost_recorder_api/migrations/002_processed_calendar_events.sql`:

```sql
-- 002_processed_calendar_events.sql (Phase 0 готовит таблицу, Phase 1 будет писать в неё)
CREATE TABLE telemost.processed_calendar_events (
    bitrix_event_id  text PRIMARY KEY,
    meeting_id       uuid REFERENCES telemost.meetings(id) ON DELETE CASCADE,
    processed_at     timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE telemost.processed_calendar_events ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON telemost.processed_calendar_events FROM anon;
```

- [ ] **Step 3: Применить миграции через Supabase MCP**

Выполнить через Supabase MCP `apply_migration`:
- name: `001_schema_users_meetings`, query: содержимое 001
- name: `002_processed_calendar_events`, query: содержимое 002

Verify: `SELECT table_name FROM information_schema.tables WHERE table_schema = 'telemost'` должен вернуть 3 строки (`users`, `meetings`, `processed_calendar_events`).

- [ ] **Step 4: Создать Storage bucket**

Через Supabase Dashboard или MCP создать bucket `telemost-audio` (private, RLS ON, доступ только service-role).

Если MCP не умеет — выполнить SQL:
```sql
INSERT INTO storage.buckets (id, name, public)
VALUES ('telemost-audio', 'telemost-audio', false)
ON CONFLICT DO NOTHING;
```

- [ ] **Step 5: Commit**

```bash
git add services/telemost_recorder_api/migrations/
git commit -m "feat(telemost-api): DB migrations for telemost schema (users, meetings, processed_calendar_events)"
```

---

## Task 3: Config Module

**Files:**
- Create: `services/telemost_recorder_api/config.py`
- Modify: `.env` — добавить `TELEMOST_WEBHOOK_SECRET`
- Test: `tests/services/telemost_recorder_api/test_config.py`

- [ ] **Step 1: Сгенерировать webhook secret и добавить в .env**

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

Скопировать значение, добавить строку в `.env` (локально):
```
TELEMOST_WEBHOOK_SECRET=<generated>
```

И на сервере: `ssh timeweb "echo 'TELEMOST_WEBHOOK_SECRET=<generated>' >> /home/danila/projects/wookiee/.env"`.

- [ ] **Step 2: Написать failing test**

Создать `tests/services/telemost_recorder_api/test_config.py`:

```python
import os
from unittest.mock import patch


def test_config_reads_required_env_vars():
    with patch.dict(os.environ, {
        "TELEMOST_BOT_TOKEN": "bot:token",
        "TELEMOST_BOT_ID": "12345",
        "TELEMOST_BOT_USERNAME": "wookiee_recorder_bot",
        "TELEMOST_WEBHOOK_SECRET": "secret_xyz",
        "DATABASE_URL": "postgres://x",
        "SPEECHKIT_API_KEY": "sk_key",
        "YANDEX_FOLDER_ID": "folder",
        "OPENROUTER_API_KEY": "or_key",
        "BITRIX24_WEBHOOK_URL": "https://b.example.com/rest/1/abc/",
        "SUPABASE_URL": "https://x.supabase.co",
        "SUPABASE_SERVICE_ROLE_KEY": "srk",
    }, clear=False):
        # Re-import to pick up patched env
        import importlib
        from services.telemost_recorder_api import config
        importlib.reload(config)
        assert config.TELEMOST_BOT_TOKEN == "bot:token"
        assert config.TELEMOST_BOT_ID == 12345
        assert config.TELEMOST_BOT_USERNAME == "wookiee_recorder_bot"
        assert config.TELEMOST_WEBHOOK_SECRET == "secret_xyz"
        assert config.MAX_PARALLEL_RECORDINGS == 1
        assert config.AUDIO_RETENTION_DAYS == 30


def test_config_fails_loudly_on_missing_required():
    with patch.dict(os.environ, {}, clear=True):
        import importlib
        from services.telemost_recorder_api import config
        try:
            importlib.reload(config)
        except RuntimeError as e:
            assert "TELEMOST_BOT_TOKEN" in str(e)
        else:
            raise AssertionError("expected RuntimeError")
```

- [ ] **Step 3: Run test — должен упасть**

```bash
pytest tests/services/telemost_recorder_api/test_config.py -v
```

Expected: FAIL — module не существует.

- [ ] **Step 4: Реализовать config.py**

Создать `services/telemost_recorder_api/config.py`:

```python
"""Phase 0 config. All required env vars validated at import time."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
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

# Supabase
SUPABASE_URL: str = _required("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY: str = _required("SUPABASE_SERVICE_ROLE_KEY")
DATABASE_URL: str = _required("DATABASE_URL")

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

# Paths
DATA_DIR: Path = _PROJECT_ROOT / "data" / "telemost"
ASSETS_DIR: Path = Path(__file__).resolve().parent / "assets"
```

- [ ] **Step 5: Run test — passing**

```bash
pytest tests/services/telemost_recorder_api/test_config.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add services/telemost_recorder_api/config.py tests/services/telemost_recorder_api/test_config.py
git commit -m "feat(telemost-api): config module with required-env validation"
```

---

## Task 4: Asyncpg DB Pool

**Files:**
- Create: `services/telemost_recorder_api/db.py`
- Create: `services/telemost_recorder_api/requirements.txt`
- Test: `tests/services/telemost_recorder_api/test_db.py`

- [ ] **Step 1: Создать requirements.txt**

`services/telemost_recorder_api/requirements.txt`:

```
fastapi>=0.110
uvicorn[standard]>=0.29
asyncpg>=0.29
docker>=7.0
httpx>=0.27
pyyaml>=6.0
python-dotenv>=1.0
python-multipart>=0.0.9
```

- [ ] **Step 2: Установить локально**

```bash
pip install -r services/telemost_recorder_api/requirements.txt
```

- [ ] **Step 3: Написать failing test**

`tests/services/telemost_recorder_api/test_db.py`:

```python
import pytest
import asyncpg

from services.telemost_recorder_api.db import get_pool, close_pool


@pytest.mark.asyncio
async def test_pool_singleton():
    pool1 = await get_pool()
    pool2 = await get_pool()
    assert pool1 is pool2
    await close_pool()


@pytest.mark.asyncio
async def test_pool_can_query():
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.fetchval("SELECT 1")
        assert result == 1
    await close_pool()
```

- [ ] **Step 4: Run test — должен упасть**

```bash
pytest tests/services/telemost_recorder_api/test_db.py -v
```

Expected: FAIL — module не существует.

- [ ] **Step 5: Реализовать db.py**

`services/telemost_recorder_api/db.py`:

```python
"""Asyncpg pool management for the API. Singleton pattern, lifespan-managed."""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

import asyncpg

from services.telemost_recorder_api.config import DATABASE_URL

logger = logging.getLogger(__name__)

_pool: Optional[asyncpg.Pool] = None
_lock = asyncio.Lock()


async def get_pool() -> asyncpg.Pool:
    global _pool
    async with _lock:
        if _pool is None or _pool._closed:
            logger.info("Creating asyncpg pool")
            _pool = await asyncpg.create_pool(
                dsn=DATABASE_URL,
                min_size=2,
                max_size=10,
                command_timeout=30,
            )
        return _pool


async def close_pool() -> None:
    global _pool
    async with _lock:
        if _pool is not None and not _pool._closed:
            await _pool.close()
            _pool = None
```

- [ ] **Step 6: Run test — passing**

```bash
pytest tests/services/telemost_recorder_api/test_db.py -v
```

Expected: PASS (тест действительно ходит в Supabase, поэтому `.env` должен быть доступен).

- [ ] **Step 7: Commit**

```bash
git add services/telemost_recorder_api/db.py services/telemost_recorder_api/requirements.txt tests/services/telemost_recorder_api/test_db.py
git commit -m "feat(telemost-api): asyncpg pool with singleton + lifespan management"
```

---

## Task 5: URL Canonicalizer

**Files:**
- Create: `services/telemost_recorder_api/url_canon.py`
- Test: `tests/services/telemost_recorder_api/test_url_canon.py`

- [ ] **Step 1: Написать failing test**

`tests/services/telemost_recorder_api/test_url_canon.py`:

```python
import pytest

from services.telemost_recorder_api.url_canon import (
    canonicalize_telemost_url,
    is_valid_telemost_url,
)


@pytest.mark.parametrize("url,expected", [
    ("https://telemost.360.yandex.ru/j/12345", "https://telemost.yandex.ru/j/12345"),
    ("https://telemost.yandex.ru/j/12345", "https://telemost.yandex.ru/j/12345"),
    ("https://telemost.yandex.ru/j/12345/", "https://telemost.yandex.ru/j/12345"),
    ("https://TELEMOST.yandex.ru/J/AbCdEf", "https://telemost.yandex.ru/j/abcdef"),
    ("https://telemost.yandex.ru/j/12345?utm=x", "https://telemost.yandex.ru/j/12345"),
])
def test_canonicalize(url, expected):
    assert canonicalize_telemost_url(url) == expected


@pytest.mark.parametrize("url,valid", [
    ("https://telemost.yandex.ru/j/12345", True),
    ("https://telemost.360.yandex.ru/j/12345", True),
    ("http://telemost.yandex.ru/j/12345", False),  # http запрещён
    ("https://telemost.yandex.ru/", False),
    ("https://example.com/j/12345", False),
    ("not a url", False),
    ("", False),
])
def test_is_valid_telemost_url(url, valid):
    assert is_valid_telemost_url(url) is valid
```

- [ ] **Step 2: Run test — должен упасть**

```bash
pytest tests/services/telemost_recorder_api/test_url_canon.py -v
```

Expected: FAIL.

- [ ] **Step 3: Реализовать url_canon.py**

`services/telemost_recorder_api/url_canon.py`:

```python
"""Canonicalize Telemost URLs for dedup and storage."""
from __future__ import annotations

import re
from urllib.parse import urlparse

_TELEMOST_HOSTS = ("telemost.yandex.ru", "telemost.360.yandex.ru")
_PATH_RE = re.compile(r"^/j/[A-Za-z0-9_-]+/?$")


def canonicalize_telemost_url(url: str) -> str:
    """Normalize a Telemost meeting URL.

    Rules:
    - Lowercase host and path.
    - Map telemost.360.yandex.ru → telemost.yandex.ru.
    - Strip trailing slash + query + fragment.
    - Force https.
    """
    parsed = urlparse(url.strip())
    host = parsed.netloc.lower().replace(
        "telemost.360.yandex.ru", "telemost.yandex.ru"
    )
    path = parsed.path.lower().rstrip("/")
    return f"https://{host}{path}"


def is_valid_telemost_url(url: str) -> bool:
    """True iff url is https + telemost host + /j/<id> path."""
    if not url or not isinstance(url, str):
        return False
    parsed = urlparse(url.strip())
    if parsed.scheme != "https":
        return False
    if parsed.netloc.lower() not in _TELEMOST_HOSTS:
        return False
    return bool(_PATH_RE.match(parsed.path))
```

- [ ] **Step 4: Run test — passing**

```bash
pytest tests/services/telemost_recorder_api/test_url_canon.py -v
```

Expected: PASS (8 cases).

- [ ] **Step 5: Commit**

```bash
git add services/telemost_recorder_api/url_canon.py tests/services/telemost_recorder_api/test_url_canon.py
git commit -m "feat(telemost-api): URL canonicalizer + validator"
```

---

## Task 6: Telegram API Client

**Files:**
- Create: `services/telemost_recorder_api/telegram_client.py`
- Test: `tests/services/telemost_recorder_api/test_telegram_client.py`

- [ ] **Step 1: Написать failing test**

`tests/services/telemost_recorder_api/test_telegram_client.py`:

```python
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from services.telemost_recorder_api.telegram_client import (
    TelegramAPIError,
    tg_call,
    tg_send_message,
    tg_send_document,
)


@pytest.mark.asyncio
async def test_tg_call_returns_result():
    mock_resp = httpx.Response(200, json={"ok": True, "result": {"message_id": 42}})
    with patch("httpx.AsyncClient.post", AsyncMock(return_value=mock_resp)):
        result = await tg_call("sendMessage", chat_id=123, text="hi")
    assert result == {"message_id": 42}


@pytest.mark.asyncio
async def test_tg_call_raises_on_error():
    mock_resp = httpx.Response(400, json={"ok": False, "description": "bad request"})
    with patch("httpx.AsyncClient.post", AsyncMock(return_value=mock_resp)):
        with pytest.raises(TelegramAPIError) as exc:
            await tg_call("sendMessage", chat_id=123, text="hi")
        assert "bad request" in str(exc.value)


@pytest.mark.asyncio
async def test_tg_send_message_chunks_long_text():
    sent = []

    async def fake_call(method, **payload):
        sent.append(payload)
        return {"message_id": len(sent)}

    with patch("services.telemost_recorder_api.telegram_client.tg_call", AsyncMock(side_effect=fake_call)):
        long_text = "x" * 5000
        await tg_send_message(chat_id=999, text=long_text)

    # 5000 chars, chunk size = 4000 → 2 messages
    assert len(sent) == 2
    assert sent[0]["text"].startswith("(1/2) ")
    assert sent[1]["text"].startswith("(2/2) ")


@pytest.mark.asyncio
async def test_tg_send_document_uses_multipart():
    captured = {}

    async def fake_post(url, files=None, data=None, **kwargs):
        captured["url"] = url
        captured["files"] = files
        captured["data"] = data
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 7}})

    with patch("httpx.AsyncClient.post", AsyncMock(side_effect=fake_post)):
        await tg_send_document(chat_id=1, file_bytes=b"hello", filename="t.txt", caption="cap")

    assert "sendDocument" in captured["url"]
    assert "document" in captured["files"]
    assert captured["data"]["chat_id"] == 1
    assert captured["data"]["caption"] == "cap"
```

- [ ] **Step 2: Run test — должен упасть**

```bash
pytest tests/services/telemost_recorder_api/test_telegram_client.py -v
```

Expected: FAIL.

- [ ] **Step 3: Реализовать telegram_client.py**

`services/telemost_recorder_api/telegram_client.py`:

```python
"""Thin httpx wrapper around Telegram Bot API. Raises on non-ok responses.

Handles message chunking (4096 char limit → 4000 to leave room for prefix)
and multipart document upload.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

import httpx

from services.telemost_recorder_api.config import TELEMOST_BOT_TOKEN

logger = logging.getLogger(__name__)

_BASE_URL = f"https://api.telegram.org/bot{TELEMOST_BOT_TOKEN}"
_CHUNK_SIZE = 4000  # 4096 - prefix headroom


class TelegramAPIError(RuntimeError):
    pass


async def tg_call(method: str, **payload: Any) -> dict:
    url = f"{_BASE_URL}/{method}"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(url, json=payload)
    body = resp.json()
    if not body.get("ok"):
        raise TelegramAPIError(f"{method} failed: {body.get('description')}")
    return body["result"]


async def tg_send_message(
    chat_id: int,
    text: str,
    parse_mode: Optional[str] = "Markdown",
    disable_web_page_preview: bool = True,
) -> None:
    if len(text) <= _CHUNK_SIZE:
        await tg_call(
            "sendMessage",
            chat_id=chat_id,
            text=text,
            parse_mode=parse_mode,
            disable_web_page_preview=disable_web_page_preview,
        )
        return

    chunks = [text[i:i + _CHUNK_SIZE] for i in range(0, len(text), _CHUNK_SIZE)]
    total = len(chunks)
    for idx, chunk in enumerate(chunks, start=1):
        prefixed = f"({idx}/{total}) {chunk}"
        await tg_call(
            "sendMessage",
            chat_id=chat_id,
            text=prefixed,
            parse_mode=parse_mode,
            disable_web_page_preview=disable_web_page_preview,
        )


async def tg_send_document(
    chat_id: int,
    file_bytes: bytes,
    filename: str,
    caption: Optional[str] = None,
) -> None:
    url = f"{_BASE_URL}/sendDocument"
    files = {"document": (filename, file_bytes, "text/plain; charset=utf-8")}
    data: dict[str, Any] = {"chat_id": chat_id}
    if caption:
        data["caption"] = caption
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(url, files=files, data=data)
    body = resp.json()
    if not body.get("ok"):
        raise TelegramAPIError(f"sendDocument failed: {body.get('description')}")
```

- [ ] **Step 4: Run test — passing**

```bash
pytest tests/services/telemost_recorder_api/test_telegram_client.py -v
```

Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add services/telemost_recorder_api/telegram_client.py tests/services/telemost_recorder_api/test_telegram_client.py
git commit -m "feat(telemost-api): Telegram API client with chunking + document upload"
```

---

## Task 7: Bitrix User Sync + Auth

**Files:**
- Create: `services/telemost_recorder_api/auth.py`
- Test: `tests/services/telemost_recorder_api/test_auth.py`

- [ ] **Step 1: Написать failing test**

`tests/services/telemost_recorder_api/test_auth.py`:

```python
from unittest.mock import AsyncMock, patch

import pytest

from services.telemost_recorder_api.auth import (
    sync_users_from_bitrix,
    get_user_by_telegram_id,
)


@pytest.mark.asyncio
async def test_sync_inserts_active_users_with_telegram_id():
    bitrix_response = {
        "result": [
            {"ID": "1", "NAME": "Полина", "LAST_NAME": "Ермилова",
             "UF_USR_TELEGRAM": "123456", "ACTIVE": True},
            {"ID": "2", "NAME": "Иван", "LAST_NAME": "Петров",
             "UF_USR_TELEGRAM": "@petrov", "ACTIVE": True},
            {"ID": "3", "NAME": "Без", "LAST_NAME": "Телеграма",
             "UF_USR_TELEGRAM": "", "ACTIVE": True},
        ]
    }
    captured_rows = []

    class FakeConn:
        async def execute(self, query, *args):
            captured_rows.append((query, args))

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

    class FakePool:
        def acquire(self):
            return FakeConn()

    with patch(
        "services.telemost_recorder_api.auth._fetch_bitrix_users",
        AsyncMock(return_value=bitrix_response["result"]),
    ), patch(
        "services.telemost_recorder_api.auth.get_pool",
        AsyncMock(return_value=FakePool()),
    ), patch(
        "services.telemost_recorder_api.auth._resolve_telegram_id",
        AsyncMock(side_effect=[123456, 999111, None]),
    ):
        count = await sync_users_from_bitrix()

    assert count == 2
    assert len(captured_rows) == 2


@pytest.mark.asyncio
async def test_get_user_by_telegram_id_returns_active():
    class FakeConn:
        async def fetchrow(self, query, *args):
            if args[0] == 123:
                return {
                    "telegram_id": 123, "bitrix_id": "1",
                    "name": "Полина", "is_active": True,
                }
            return None

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

    class FakePool:
        def acquire(self):
            return FakeConn()

    with patch("services.telemost_recorder_api.auth.get_pool", AsyncMock(return_value=FakePool())):
        user = await get_user_by_telegram_id(123)
        none_user = await get_user_by_telegram_id(456)

    assert user["name"] == "Полина"
    assert none_user is None
```

- [ ] **Step 2: Run test — должен упасть**

```bash
pytest tests/services/telemost_recorder_api/test_auth.py -v
```

Expected: FAIL.

- [ ] **Step 3: Реализовать auth.py**

`services/telemost_recorder_api/auth.py`:

```python
"""Bitrix24 user sync + auth lookup by telegram_id.

Bitrix custom field UF_USR_TELEGRAM может содержать:
- numeric Telegram user_id
- @username (нужно резолвить в numeric через getChat)
- ссылку https://t.me/...
- быть пустым

В Phase 0 сохраняем только numeric (либо разрезолвленный из username).
"""
from __future__ import annotations

import logging
import re
from typing import Optional

import httpx

from services.telemost_recorder_api.config import BITRIX24_WEBHOOK_URL
from services.telemost_recorder_api.db import get_pool
from services.telemost_recorder_api.telegram_client import tg_call, TelegramAPIError

logger = logging.getLogger(__name__)

_TELEGRAM_FIELD_KEYS = ("UF_USR_TELEGRAM", "UF_USR_TG", "UF_TELEGRAM")


async def _fetch_bitrix_users() -> list[dict]:
    url = BITRIX24_WEBHOOK_URL.rstrip("/") + "/user.get.json"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url, params={"ACTIVE": "Y"})
    resp.raise_for_status()
    return resp.json().get("result", [])


def _extract_telegram_raw(user_record: dict) -> Optional[str]:
    for key in _TELEGRAM_FIELD_KEYS:
        value = user_record.get(key)
        if value:
            return str(value).strip()
    return None


async def _resolve_telegram_id(raw: str) -> Optional[int]:
    """Resolve raw Bitrix telegram field into numeric telegram_id.

    Returns numeric id if user has interacted with the bot, else None.
    """
    raw = raw.strip()
    # Pure number
    if re.fullmatch(r"\d+", raw):
        return int(raw)
    # https://t.me/<name> или @<name>
    m = re.search(r"(?:t\.me/|@)([A-Za-z0-9_]{3,32})", raw)
    if not m:
        return None
    username = m.group(1)
    try:
        chat = await tg_call("getChat", chat_id=f"@{username}")
        return int(chat["id"])
    except TelegramAPIError as e:
        logger.warning("Could not resolve @%s to telegram_id: %s", username, e)
        return None


async def sync_users_from_bitrix() -> int:
    """Pull users from Bitrix, upsert into telemost.users. Returns count of synced users."""
    raw_users = await _fetch_bitrix_users()
    pool = await get_pool()
    synced = 0
    async with pool.acquire() as conn:
        for u in raw_users:
            tg_raw = _extract_telegram_raw(u)
            if not tg_raw:
                continue
            tg_id = await _resolve_telegram_id(tg_raw)
            if not tg_id:
                continue
            full_name = " ".join(filter(None, [u.get("NAME"), u.get("LAST_NAME")])) or "—"
            short_name = u.get("NAME") or full_name
            is_active = bool(u.get("ACTIVE", True))
            await conn.execute(
                """
                INSERT INTO telemost.users (telegram_id, bitrix_id, name, short_name, is_active, synced_at)
                VALUES ($1, $2, $3, $4, $5, now())
                ON CONFLICT (telegram_id) DO UPDATE SET
                    bitrix_id = EXCLUDED.bitrix_id,
                    name = EXCLUDED.name,
                    short_name = EXCLUDED.short_name,
                    is_active = EXCLUDED.is_active,
                    synced_at = now()
                """,
                tg_id, str(u["ID"]), full_name, short_name, is_active,
            )
            synced += 1
    logger.info("Synced %d users from Bitrix", synced)
    return synced


async def get_user_by_telegram_id(telegram_id: int) -> Optional[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT telegram_id, bitrix_id, name, short_name, is_active "
            "FROM telemost.users WHERE telegram_id = $1 AND is_active = true",
            telegram_id,
        )
    return dict(row) if row else None
```

- [ ] **Step 4: Run test — passing**

```bash
pytest tests/services/telemost_recorder_api/test_auth.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add services/telemost_recorder_api/auth.py tests/services/telemost_recorder_api/test_auth.py
git commit -m "feat(telemost-api): Bitrix user sync + telegram_id auth"
```

---

## Task 8: FastAPI Skeleton + /health

**Files:**
- Create: `services/telemost_recorder_api/app.py`
- Create: `services/telemost_recorder_api/routes/health.py`
- Test: `tests/services/telemost_recorder_api/test_health.py`

- [ ] **Step 1: Написать failing test**

`tests/services/telemost_recorder_api/test_health.py`:

```python
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from services.telemost_recorder_api.app import create_app


def test_health_returns_ok_when_db_reachable():
    class FakeConn:
        async def fetchval(self, q):
            return 1

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

    class FakePool:
        def acquire(self):
            return FakeConn()

    with patch(
        "services.telemost_recorder_api.routes.health.get_pool",
        AsyncMock(return_value=FakePool()),
    ):
        app = create_app()
        client = TestClient(app)
        resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] in ("ok", "degraded")
    assert "checks" in body
    assert body["checks"]["db_ping_ms"] >= 0


def test_health_returns_down_when_db_fails():
    async def boom(*a, **kw):
        raise RuntimeError("db unreachable")

    with patch(
        "services.telemost_recorder_api.routes.health.get_pool",
        AsyncMock(side_effect=boom),
    ):
        app = create_app()
        client = TestClient(app)
        resp = client.get("/health")
    assert resp.status_code == 503
    assert resp.json()["status"] == "down"
```

- [ ] **Step 2: Run — failing**

```bash
pytest tests/services/telemost_recorder_api/test_health.py -v
```

Expected: FAIL.

- [ ] **Step 3: Реализовать routes/health.py**

`services/telemost_recorder_api/routes/health.py`:

```python
"""GET /health — DB ping + queue snapshot."""
from __future__ import annotations

import time

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from services.telemost_recorder_api.db import get_pool

router = APIRouter()


@router.get("/health")
async def health() -> JSONResponse:
    started = time.perf_counter()
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
            queue_size = await conn.fetchval(
                "SELECT count(*) FROM telemost.meetings WHERE status = 'queued'"
            ) or 0
            recording_count = await conn.fetchval(
                "SELECT count(*) FROM telemost.meetings WHERE status = 'recording'"
            ) or 0
    except Exception as e:
        return JSONResponse(
            {"status": "down", "error": str(e)},
            status_code=503,
        )
    db_ping_ms = int((time.perf_counter() - started) * 1000)
    status = "ok"
    if db_ping_ms > 1000:
        status = "degraded"
    return JSONResponse({
        "status": status,
        "checks": {
            "db_ping_ms": db_ping_ms,
            "queue_size": queue_size,
            "recording_count": recording_count,
        },
    })
```

- [ ] **Step 4: Реализовать app.py**

`services/telemost_recorder_api/app.py`:

```python
"""FastAPI factory for telemost_recorder_api.

Lifespan:
- Startup: open DB pool, run user-sync once, set bot avatar (idempotent).
- Shutdown: close DB pool.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from services.telemost_recorder_api.config import LOG_LEVEL
from services.telemost_recorder_api.db import close_pool, get_pool
from services.telemost_recorder_api.routes import health

logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def _lifespan(app: FastAPI):
    logger.info("telemost-recorder-api starting up")
    await get_pool()
    yield
    logger.info("telemost-recorder-api shutting down")
    await close_pool()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Telemost Recorder API",
        version="0.1.0",
        lifespan=_lifespan,
    )
    app.include_router(health.router)
    return app
```

- [ ] **Step 5: Run — passing**

```bash
pytest tests/services/telemost_recorder_api/test_health.py -v
```

Expected: PASS (2 tests).

- [ ] **Step 6: Smoke-test локально**

```bash
uvicorn services.telemost_recorder_api.app:create_app --factory --port 8006 &
sleep 2
curl -s http://localhost:8006/health | python -m json.tool
kill %1
```

Expected: JSON `{"status": "ok", "checks": {...}}`.

- [ ] **Step 7: Commit**

```bash
git add services/telemost_recorder_api/app.py services/telemost_recorder_api/routes/health.py tests/services/telemost_recorder_api/test_health.py
git commit -m "feat(telemost-api): FastAPI skeleton + /health"
```

---

## Task 9: Telegram Webhook Route + Dispatcher

**Files:**
- Create: `services/telemost_recorder_api/routes/telegram.py`
- Modify: `services/telemost_recorder_api/app.py` — include router
- Test: `tests/services/telemost_recorder_api/test_telegram_routes.py`

- [ ] **Step 1: Написать failing test**

`tests/services/telemost_recorder_api/test_telegram_routes.py`:

```python
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from services.telemost_recorder_api.app import create_app
from services.telemost_recorder_api.config import TELEMOST_WEBHOOK_SECRET


def _msg_update(text: str, chat_id: int = 100, user_id: int = 100):
    return {
        "update_id": 1,
        "message": {
            "message_id": 5,
            "date": 1700000000,
            "chat": {"id": chat_id, "type": "private"},
            "from": {"id": user_id, "is_bot": False, "first_name": "X"},
            "text": text,
        },
    }


def test_webhook_rejects_missing_secret():
    app = create_app()
    client = TestClient(app)
    resp = client.post("/telegram/webhook", json=_msg_update("/start"))
    assert resp.status_code == 401


def test_webhook_rejects_wrong_secret():
    app = create_app()
    client = TestClient(app)
    resp = client.post(
        "/telegram/webhook",
        json=_msg_update("/start"),
        headers={"X-Telegram-Bot-Api-Secret-Token": "WRONG"},
    )
    assert resp.status_code == 401


def test_webhook_accepts_correct_secret_and_dispatches():
    dispatched: list = []

    async def fake_dispatch(update):
        dispatched.append(update)

    with patch(
        "services.telemost_recorder_api.routes.telegram.dispatch_update",
        AsyncMock(side_effect=fake_dispatch),
    ):
        app = create_app()
        client = TestClient(app)
        resp = client.post(
            "/telegram/webhook",
            json=_msg_update("/start"),
            headers={"X-Telegram-Bot-Api-Secret-Token": TELEMOST_WEBHOOK_SECRET},
        )

    assert resp.status_code == 200
    assert len(dispatched) == 1
    assert dispatched[0]["message"]["text"] == "/start"


def test_webhook_returns_200_on_handler_error():
    """Telegram retries on non-2xx → must return 200 even if our handler crashes."""
    async def boom(*a, **kw):
        raise RuntimeError("handler crashed")

    with patch(
        "services.telemost_recorder_api.routes.telegram.dispatch_update",
        AsyncMock(side_effect=boom),
    ):
        app = create_app()
        client = TestClient(app)
        resp = client.post(
            "/telegram/webhook",
            json=_msg_update("/whatever"),
            headers={"X-Telegram-Bot-Api-Secret-Token": TELEMOST_WEBHOOK_SECRET},
        )
    assert resp.status_code == 200
```

- [ ] **Step 2: Run — failing**

```bash
pytest tests/services/telemost_recorder_api/test_telegram_routes.py -v
```

Expected: FAIL — route не существует.

- [ ] **Step 3: Реализовать routes/telegram.py**

`services/telemost_recorder_api/routes/telegram.py`:

```python
"""Telegram webhook entry point. Validates secret, hands off to dispatcher.

Returns 200 always on dispatch errors (Telegram retries non-2xx for ~24h).
"""
from __future__ import annotations

import hmac
import logging

from fastapi import APIRouter, Header, HTTPException, Request

from services.telemost_recorder_api.config import TELEMOST_WEBHOOK_SECRET

logger = logging.getLogger(__name__)
router = APIRouter()


async def dispatch_update(update: dict) -> None:
    """Route a Telegram Update to the appropriate command handler.

    Implemented in handlers module; imported here to allow patching in tests.
    """
    from services.telemost_recorder_api.handlers import handle_update
    await handle_update(update)


@router.post("/telegram/webhook")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
):
    if not x_telegram_bot_api_secret_token or not hmac.compare_digest(
        x_telegram_bot_api_secret_token, TELEMOST_WEBHOOK_SECRET
    ):
        raise HTTPException(status_code=401, detail="invalid secret token")
    update = await request.json()
    try:
        await dispatch_update(update)
    except Exception:
        logger.exception("dispatch_update failed for update=%s", update.get("update_id"))
    return {"ok": True}
```

- [ ] **Step 4: Создать пустой handlers stub**

`services/telemost_recorder_api/handlers.py`:

```python
"""Telegram command dispatch. Phase 0 commands: /start /help /record /status /list."""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


async def handle_update(update: dict) -> None:
    msg = update.get("message")
    if not msg:
        return
    text = (msg.get("text") or "").strip()
    chat_id = msg["chat"]["id"]
    user_id = msg["from"]["id"]
    chat_type = msg["chat"]["type"]
    if chat_type != "private":
        # Phase 1 will handle group leave; Phase 0 just ignores.
        return
    logger.info("Received from %d in chat %d: %s", user_id, chat_id, text[:100])
    # Routing implemented in subsequent tasks; Phase 0 stub.
```

- [ ] **Step 5: Регистрация router в app.py**

В `services/telemost_recorder_api/app.py` импортировать и подключить:

```python
from services.telemost_recorder_api.routes import health, telegram
# ...
def create_app() -> FastAPI:
    app = FastAPI(...)
    app.include_router(health.router)
    app.include_router(telegram.router)
    return app
```

- [ ] **Step 6: Run — passing**

```bash
pytest tests/services/telemost_recorder_api/test_telegram_routes.py -v
```

Expected: PASS (4 tests).

- [ ] **Step 7: Commit**

```bash
git add services/telemost_recorder_api/routes/telegram.py services/telemost_recorder_api/handlers.py services/telemost_recorder_api/app.py tests/services/telemost_recorder_api/test_telegram_routes.py
git commit -m "feat(telemost-api): /telegram/webhook with secret validation + dispatcher stub"
```

---

## Task 10: /start and /help Commands

**Files:**
- Create: `services/telemost_recorder_api/handlers/__init__.py` (рефакторим из handlers.py)
- Create: `services/telemost_recorder_api/handlers/start.py`
- Create: `services/telemost_recorder_api/handlers/help.py`
- Modify: `services/telemost_recorder_api/handlers/__init__.py` — add router
- Test: `tests/services/telemost_recorder_api/test_handlers_start_help.py`

- [ ] **Step 1: Превратить handlers.py в пакет**

```bash
mv services/telemost_recorder_api/handlers.py services/telemost_recorder_api/handlers/__init__.py
```

(Перед mv создать каталог: `mkdir services/telemost_recorder_api/handlers`)

- [ ] **Step 2: Написать failing test**

`tests/services/telemost_recorder_api/test_handlers_start_help.py`:

```python
from unittest.mock import AsyncMock, patch

import pytest

from services.telemost_recorder_api.handlers import handle_update


def _msg(text: str, user_id: int = 555):
    return {
        "message": {
            "chat": {"id": user_id, "type": "private"},
            "from": {"id": user_id, "is_bot": False, "first_name": "Test"},
            "text": text,
        },
    }


@pytest.mark.asyncio
async def test_start_known_user_gets_welcome():
    sent = []
    with patch(
        "services.telemost_recorder_api.handlers.start.get_user_by_telegram_id",
        AsyncMock(return_value={"telegram_id": 555, "name": "Полина", "is_active": True}),
    ), patch(
        "services.telemost_recorder_api.handlers.start.tg_send_message",
        AsyncMock(side_effect=lambda chat_id, text, **kw: sent.append((chat_id, text))),
    ):
        await handle_update(_msg("/start"))
    assert len(sent) == 1
    assert "Полина" in sent[0][1]
    assert "/record" in sent[0][1]


@pytest.mark.asyncio
async def test_start_unknown_user_gets_auth_instructions():
    sent = []
    with patch(
        "services.telemost_recorder_api.handlers.start.get_user_by_telegram_id",
        AsyncMock(return_value=None),
    ), patch(
        "services.telemost_recorder_api.handlers.start.tg_send_message",
        AsyncMock(side_effect=lambda chat_id, text, **kw: sent.append((chat_id, text))),
    ):
        await handle_update(_msg("/start"))
    assert len(sent) == 1
    assert "Bitrix24" in sent[0][1]
    assert "Telegram" in sent[0][1]


@pytest.mark.asyncio
async def test_help_returns_command_list():
    sent = []
    with patch(
        "services.telemost_recorder_api.handlers.help.tg_send_message",
        AsyncMock(side_effect=lambda chat_id, text, **kw: sent.append(text)),
    ):
        await handle_update(_msg("/help"))
    assert "/record" in sent[0]
    assert "/status" in sent[0]
    assert "/list" in sent[0]
```

- [ ] **Step 3: Run — failing**

Expected: FAIL.

- [ ] **Step 4: Реализовать handlers/start.py**

`services/telemost_recorder_api/handlers/start.py`:

```python
"""/start command — auth check + welcome."""
from __future__ import annotations

from services.telemost_recorder_api.auth import get_user_by_telegram_id
from services.telemost_recorder_api.telegram_client import tg_send_message

_WELCOME = """Привет, {name}! 👋

Я Wookiee Recorder — записываю встречи Я.Телемоста и присылаю summary.

Команды:
• `/record <ссылка>` — записать встречу
• `/status` — твои активные/последние записи
• `/list` — последние 10 встреч с твоим участием
• `/help` — справка
"""

_AUTH_FAIL = """Не нашёл твой Telegram-ID в Bitrix-roster.

Чтобы получить доступ:
1. Открой свой профиль в Bitrix24 → «Контактная информация» → «Telegram»
2. Введи `@matveev_danila` (либо свой numeric ID)
3. Сохрани
4. Через час напиши мне `/start` снова

Если что-то не работает — скинь скриншот @matveev_danila."""


async def handle_start(chat_id: int, user_id: int) -> None:
    user = await get_user_by_telegram_id(user_id)
    if user:
        await tg_send_message(chat_id, _WELCOME.format(name=user.get("short_name") or user["name"]))
    else:
        await tg_send_message(chat_id, _AUTH_FAIL)
```

- [ ] **Step 5: Реализовать handlers/help.py**

`services/telemost_recorder_api/handlers/help.py`:

```python
"""/help command."""
from __future__ import annotations

from services.telemost_recorder_api.telegram_client import tg_send_message

_HELP = """*Wookiee Recorder — справка*

`/record <ссылка>` — поставить встречу в очередь записи. Поддерживаются ссылки `telemost.yandex.ru/j/...` и `telemost.360.yandex.ru/j/...`.

`/status` — твои активные записи (`queued` / `recording` / `postprocessing`) и 5 последних завершённых.

`/list` — 10 последних встреч, где ты триггерщик/организатор/инвайт.

После завершения записи я пришлю в DM:
• краткий summary с темами, решениями и задачами
• полный transcript как `.txt` attachment

Аудио хранится 30 дней, текст — бессрочно.
"""


async def handle_help(chat_id: int) -> None:
    await tg_send_message(chat_id, _HELP)
```

- [ ] **Step 6: Обновить handlers/__init__.py с роутингом**

`services/telemost_recorder_api/handlers/__init__.py`:

```python
"""Telegram command dispatch."""
from __future__ import annotations

import logging

from services.telemost_recorder_api.handlers.help import handle_help
from services.telemost_recorder_api.handlers.start import handle_start

logger = logging.getLogger(__name__)


async def handle_update(update: dict) -> None:
    msg = update.get("message")
    if not msg:
        return
    text = (msg.get("text") or "").strip()
    chat_id = msg["chat"]["id"]
    user_id = msg["from"]["id"]
    chat_type = msg["chat"]["type"]
    if chat_type != "private":
        return  # Phase 1: leave group
    logger.info("Cmd from %d: %s", user_id, text[:100])

    cmd, _, args = text.partition(" ")
    cmd = cmd.split("@", 1)[0]  # strip @bot_username for group-style mentions
    if cmd == "/start":
        await handle_start(chat_id, user_id)
    elif cmd == "/help":
        await handle_help(chat_id)
    # /record /status /list — added in next tasks
```

- [ ] **Step 7: Run — passing**

```bash
pytest tests/services/telemost_recorder_api/test_handlers_start_help.py -v
```

Expected: PASS (3 tests).

- [ ] **Step 8: Commit**

```bash
git add services/telemost_recorder_api/handlers/ tests/services/telemost_recorder_api/test_handlers_start_help.py
git commit -m "feat(telemost-api): /start with auth check + /help command"
```

---

## Task 11: /record Command with Concurrent-Recording Uniqueness

**Files:**
- Create: `services/telemost_recorder_api/handlers/record.py`
- Modify: `services/telemost_recorder_api/handlers/__init__.py`
- Test: `tests/services/telemost_recorder_api/test_handlers_record.py`

- [ ] **Step 1: Написать failing test**

`tests/services/telemost_recorder_api/test_handlers_record.py`:

```python
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from services.telemost_recorder_api.handlers import handle_update


def _msg(text: str, user_id: int = 555):
    return {
        "message": {
            "chat": {"id": user_id, "type": "private"},
            "from": {"id": user_id, "is_bot": False, "first_name": "X"},
            "text": text,
        },
    }


_AUTHED_USER = {"telegram_id": 555, "name": "Полина", "short_name": "Полина", "is_active": True}


@pytest.mark.asyncio
async def test_record_rejects_unknown_user():
    sent = []
    with patch(
        "services.telemost_recorder_api.handlers.record.get_user_by_telegram_id",
        AsyncMock(return_value=None),
    ), patch(
        "services.telemost_recorder_api.handlers.record.tg_send_message",
        AsyncMock(side_effect=lambda c, t, **k: sent.append(t)),
    ):
        await handle_update(_msg("/record https://telemost.yandex.ru/j/abc"))
    assert "не нашёл" in sent[0].lower() or "bitrix" in sent[0].lower()


@pytest.mark.asyncio
async def test_record_rejects_invalid_url():
    sent = []
    with patch(
        "services.telemost_recorder_api.handlers.record.get_user_by_telegram_id",
        AsyncMock(return_value=_AUTHED_USER),
    ), patch(
        "services.telemost_recorder_api.handlers.record.tg_send_message",
        AsyncMock(side_effect=lambda c, t, **k: sent.append(t)),
    ):
        await handle_update(_msg("/record not-a-url"))
    assert "ссылк" in sent[0].lower()


@pytest.mark.asyncio
async def test_record_no_args_shows_usage():
    sent = []
    with patch(
        "services.telemost_recorder_api.handlers.record.get_user_by_telegram_id",
        AsyncMock(return_value=_AUTHED_USER),
    ), patch(
        "services.telemost_recorder_api.handlers.record.tg_send_message",
        AsyncMock(side_effect=lambda c, t, **k: sent.append(t)),
    ):
        await handle_update(_msg("/record"))
    assert "/record <ссылка>" in sent[0]


@pytest.mark.asyncio
async def test_record_enqueues_meeting():
    new_id = uuid4()
    sent = []

    class FakeConn:
        async def fetchval(self, query, *args):
            assert "INSERT" in query.upper()
            return new_id

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

    class FakePool:
        def acquire(self):
            return FakeConn()

    with patch(
        "services.telemost_recorder_api.handlers.record.get_user_by_telegram_id",
        AsyncMock(return_value=_AUTHED_USER),
    ), patch(
        "services.telemost_recorder_api.handlers.record.get_pool",
        AsyncMock(return_value=FakePool()),
    ), patch(
        "services.telemost_recorder_api.handlers.record.tg_send_message",
        AsyncMock(side_effect=lambda c, t, **k: sent.append(t)),
    ):
        await handle_update(_msg("/record https://telemost.360.yandex.ru/j/abc"))

    assert any(str(new_id)[:8] in s for s in sent)
    assert any("очередь" in s.lower() for s in sent)


@pytest.mark.asyncio
async def test_record_duplicate_concurrent_returns_already():
    """ON CONFLICT DO NOTHING returns NULL → user gets 'already recording' message."""
    sent = []

    class FakeConn:
        async def fetchval(self, query, *args):
            return None  # ON CONFLICT — никто не вернулся

        async def fetchrow(self, query, *args):
            from uuid import UUID
            return {"id": UUID("11111111-1111-1111-1111-111111111111"), "status": "recording"}

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

    class FakePool:
        def acquire(self):
            return FakeConn()

    with patch(
        "services.telemost_recorder_api.handlers.record.get_user_by_telegram_id",
        AsyncMock(return_value=_AUTHED_USER),
    ), patch(
        "services.telemost_recorder_api.handlers.record.get_pool",
        AsyncMock(return_value=FakePool()),
    ), patch(
        "services.telemost_recorder_api.handlers.record.tg_send_message",
        AsyncMock(side_effect=lambda c, t, **k: sent.append(t)),
    ):
        await handle_update(_msg("/record https://telemost.yandex.ru/j/abc"))

    assert any("уже" in s.lower() for s in sent)
```

- [ ] **Step 2: Run — failing**

Expected: FAIL.

- [ ] **Step 3: Реализовать handlers/record.py**

`services/telemost_recorder_api/handlers/record.py`:

```python
"""/record <url> — auth, validate, enqueue with concurrent-recording uniqueness."""
from __future__ import annotations

import logging

from services.telemost_recorder_api.auth import get_user_by_telegram_id
from services.telemost_recorder_api.db import get_pool
from services.telemost_recorder_api.telegram_client import tg_send_message
from services.telemost_recorder_api.url_canon import (
    canonicalize_telemost_url,
    is_valid_telemost_url,
)

logger = logging.getLogger(__name__)


async def handle_record(chat_id: int, user_id: int, args: str) -> None:
    user = await get_user_by_telegram_id(user_id)
    if not user:
        await tg_send_message(
            chat_id,
            "Не нашёл твой Telegram-ID в Bitrix-roster. Напиши /start для инструкций.",
        )
        return

    args = args.strip()
    if not args:
        await tg_send_message(chat_id, "Использование: `/record <ссылка>`\n\nПример: `/record https://telemost.yandex.ru/j/abc-def-ghi`")
        return

    raw_url = args.split()[0]
    if not is_valid_telemost_url(raw_url):
        await tg_send_message(
            chat_id,
            "Это не похоже на ссылку Я.Телемоста. Жду формат `https://telemost.yandex.ru/j/<id>` или `https://telemost.360.yandex.ru/j/<id>`.",
        )
        return

    canonical = canonicalize_telemost_url(raw_url)
    pool = await get_pool()
    async with pool.acquire() as conn:
        new_id = await conn.fetchval(
            """
            INSERT INTO telemost.meetings
                (source, triggered_by, meeting_url, organizer_id, invitees, status)
            VALUES ('telegram', $1, $2, $1, '[]'::jsonb, 'queued')
            ON CONFLICT (meeting_url) WHERE status IN ('queued','recording','postprocessing')
            DO NOTHING
            RETURNING id
            """,
            user_id, canonical,
        )
        if new_id is None:
            existing = await conn.fetchrow(
                """
                SELECT id, status FROM telemost.meetings
                WHERE meeting_url = $1 AND status IN ('queued','recording','postprocessing')
                ORDER BY created_at DESC LIMIT 1
                """,
                canonical,
            )
            await tg_send_message(
                chat_id,
                f"Эта встреча уже в работе (id `{str(existing['id'])[:8]}`, статус `{existing['status']}`). Дождись результата.",
            )
            return

    await tg_send_message(
        chat_id,
        f"✅ Поставил в очередь. id `{str(new_id)[:8]}`. Пришлю summary в DM, когда встреча закончится.",
    )
    logger.info("Enqueued meeting %s by user %d for url %s", new_id, user_id, canonical)
```

- [ ] **Step 4: Подключить /record в handlers/__init__.py**

В роутер добавить:
```python
from services.telemost_recorder_api.handlers.record import handle_record
# ...
    elif cmd == "/record":
        await handle_record(chat_id, user_id, args)
```

- [ ] **Step 5: Run — passing**

```bash
pytest tests/services/telemost_recorder_api/test_handlers_record.py -v
```

Expected: PASS (5 tests).

- [ ] **Step 6: Commit**

```bash
git add services/telemost_recorder_api/handlers/record.py services/telemost_recorder_api/handlers/__init__.py tests/services/telemost_recorder_api/test_handlers_record.py
git commit -m "feat(telemost-api): /record command with concurrent-uniqueness via partial unique index"
```

---

## Task 12: /status and /list Commands with Privacy Scope

**Files:**
- Create: `services/telemost_recorder_api/handlers/status.py`
- Create: `services/telemost_recorder_api/handlers/list_meetings.py`
- Modify: `services/telemost_recorder_api/handlers/__init__.py`
- Test: `tests/services/telemost_recorder_api/test_handlers_status_list.py`

- [ ] **Step 1: Написать failing test**

`tests/services/telemost_recorder_api/test_handlers_status_list.py`:

```python
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest

from services.telemost_recorder_api.handlers import handle_update


def _msg(text: str, user_id: int = 555):
    return {
        "message": {
            "chat": {"id": user_id, "type": "private"},
            "from": {"id": user_id, "is_bot": False, "first_name": "X"},
            "text": text,
        },
    }


_USER = {"telegram_id": 555, "name": "X", "short_name": "X", "is_active": True}


@pytest.mark.asyncio
async def test_status_shows_active_and_recent():
    rows = [
        {"id": UUID("11111111-1111-1111-1111-111111111111"),
         "status": "recording", "title": "Дейли", "started_at": datetime(2026, 5, 8, 10, 0, tzinfo=timezone.utc),
         "ended_at": None},
        {"id": UUID("22222222-2222-2222-2222-222222222222"),
         "status": "done", "title": "Бренд-стратегия",
         "started_at": datetime(2026, 5, 7, 14, 0, tzinfo=timezone.utc),
         "ended_at": datetime(2026, 5, 7, 15, 0, tzinfo=timezone.utc)},
    ]

    class FakeConn:
        async def fetch(self, query, *args):
            return rows

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

    class FakePool:
        def acquire(self):
            return FakeConn()

    sent = []
    with patch(
        "services.telemost_recorder_api.handlers.status.get_user_by_telegram_id",
        AsyncMock(return_value=_USER),
    ), patch(
        "services.telemost_recorder_api.handlers.status.get_pool",
        AsyncMock(return_value=FakePool()),
    ), patch(
        "services.telemost_recorder_api.handlers.status.tg_send_message",
        AsyncMock(side_effect=lambda c, t, **k: sent.append(t)),
    ):
        await handle_update(_msg("/status"))

    assert "Дейли" in sent[0]
    assert "recording" in sent[0]
    assert "Бренд-стратегия" in sent[0]


@pytest.mark.asyncio
async def test_status_empty():
    class FakeConn:
        async def fetch(self, query, *args):
            return []

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

    class FakePool:
        def acquire(self):
            return FakeConn()

    sent = []
    with patch(
        "services.telemost_recorder_api.handlers.status.get_user_by_telegram_id",
        AsyncMock(return_value=_USER),
    ), patch(
        "services.telemost_recorder_api.handlers.status.get_pool",
        AsyncMock(return_value=FakePool()),
    ), patch(
        "services.telemost_recorder_api.handlers.status.tg_send_message",
        AsyncMock(side_effect=lambda c, t, **k: sent.append(t)),
    ):
        await handle_update(_msg("/status"))

    assert "нет" in sent[0].lower() or "пусто" in sent[0].lower()


@pytest.mark.asyncio
async def test_list_uses_privacy_filter():
    captured_args = []

    class FakeConn:
        async def fetch(self, query, *args):
            captured_args.append((query, args))
            return []

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

    class FakePool:
        def acquire(self):
            return FakeConn()

    sent = []
    with patch(
        "services.telemost_recorder_api.handlers.list_meetings.get_user_by_telegram_id",
        AsyncMock(return_value=_USER),
    ), patch(
        "services.telemost_recorder_api.handlers.list_meetings.get_pool",
        AsyncMock(return_value=FakePool()),
    ), patch(
        "services.telemost_recorder_api.handlers.list_meetings.tg_send_message",
        AsyncMock(side_effect=lambda c, t, **k: sent.append(t)),
    ):
        await handle_update(_msg("/list"))

    q, args = captured_args[0]
    assert "triggered_by" in q
    assert "organizer_id" in q
    assert "invitees" in q
    assert args[0] == 555
```

- [ ] **Step 2: Run — failing**

Expected: FAIL.

- [ ] **Step 3: Реализовать handlers/status.py**

`services/telemost_recorder_api/handlers/status.py`:

```python
"""/status — твои active + recent meetings."""
from __future__ import annotations

from services.telemost_recorder_api.auth import get_user_by_telegram_id
from services.telemost_recorder_api.db import get_pool
from services.telemost_recorder_api.telegram_client import tg_send_message


def _format_row(row) -> str:
    title = row["title"] or "(без названия)"
    started = row["started_at"].strftime("%d.%m %H:%M") if row["started_at"] else "—"
    return f"• `{str(row['id'])[:8]}` [{row['status']}] {title} ({started})"


async def handle_status(chat_id: int, user_id: int) -> None:
    user = await get_user_by_telegram_id(user_id)
    if not user:
        await tg_send_message(chat_id, "Сначала /start.")
        return
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            (SELECT id, status, title, started_at, ended_at
             FROM telemost.meetings
             WHERE triggered_by = $1
                AND status IN ('queued','recording','postprocessing'))
            UNION ALL
            (SELECT id, status, title, started_at, ended_at
             FROM telemost.meetings
             WHERE triggered_by = $1
                AND status IN ('done','failed')
             ORDER BY ended_at DESC NULLS LAST
             LIMIT 5)
            """,
            user_id,
        )
    if not rows:
        await tg_send_message(chat_id, "У тебя пока нет записей.")
        return
    lines = ["*Твои записи:*"]
    lines.extend(_format_row(r) for r in rows)
    await tg_send_message(chat_id, "\n".join(lines))
```

- [ ] **Step 4: Реализовать handlers/list_meetings.py**

`services/telemost_recorder_api/handlers/list_meetings.py`:

```python
"""/list — последние 10 встреч с твоим участием (privacy scope §15.8)."""
from __future__ import annotations

import json

from services.telemost_recorder_api.auth import get_user_by_telegram_id
from services.telemost_recorder_api.db import get_pool
from services.telemost_recorder_api.telegram_client import tg_send_message


def _format_row(row) -> str:
    title = row["title"] or "(без названия)"
    started = row["started_at"].strftime("%d.%m %H:%M") if row["started_at"] else "—"
    return f"• `{str(row['id'])[:8]}` [{row['status']}] {title} ({started})"


async def handle_list(chat_id: int, user_id: int) -> None:
    user = await get_user_by_telegram_id(user_id)
    if not user:
        await tg_send_message(chat_id, "Сначала /start.")
        return
    pool = await get_pool()
    invitee_filter = json.dumps([{"telegram_id": user_id}])
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, status, title, started_at
            FROM telemost.meetings
            WHERE triggered_by = $1
               OR organizer_id = $1
               OR invitees @> $2::jsonb
            ORDER BY COALESCE(started_at, created_at) DESC
            LIMIT 10
            """,
            user_id, invitee_filter,
        )
    if not rows:
        await tg_send_message(chat_id, "Не нашёл ни одной твоей встречи.")
        return
    lines = ["*Последние 10 встреч:*"]
    lines.extend(_format_row(r) for r in rows)
    await tg_send_message(chat_id, "\n".join(lines))
```

- [ ] **Step 5: Подключить в handlers/__init__.py**

```python
from services.telemost_recorder_api.handlers.list_meetings import handle_list
from services.telemost_recorder_api.handlers.status import handle_status
# ...
    elif cmd == "/status":
        await handle_status(chat_id, user_id)
    elif cmd == "/list":
        await handle_list(chat_id, user_id)
```

- [ ] **Step 6: Run — passing**

```bash
pytest tests/services/telemost_recorder_api/test_handlers_status_list.py -v
```

Expected: PASS (3 tests).

- [ ] **Step 7: Commit**

```bash
git add services/telemost_recorder_api/handlers/status.py services/telemost_recorder_api/handlers/list_meetings.py services/telemost_recorder_api/handlers/__init__.py tests/services/telemost_recorder_api/test_handlers_status_list.py
git commit -m "feat(telemost-api): /status + /list with privacy scope"
```

---

## Task 13: Docker SDK Wrapper — spawn recorder container

**Files:**
- Create: `services/telemost_recorder_api/docker_client.py`
- Test: `tests/services/telemost_recorder_api/test_docker_client.py`

- [ ] **Step 1: Написать failing test**

`tests/services/telemost_recorder_api/test_docker_client.py`:

```python
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from services.telemost_recorder_api.docker_client import (
    spawn_recorder_container,
    monitor_container,
    list_orphan_containers,
)


def test_spawn_passes_meeting_id_label_and_volume():
    captured = {}

    def fake_run(image, **kwargs):
        captured["image"] = image
        captured["kwargs"] = kwargs
        m = MagicMock()
        m.id = "container_abc"
        return m

    fake_client = MagicMock()
    fake_client.containers.run = fake_run

    meeting_id = uuid4()
    with patch("services.telemost_recorder_api.docker_client._get_client", return_value=fake_client):
        cid = spawn_recorder_container(
            meeting_id=meeting_id,
            meeting_url="https://telemost.yandex.ru/j/abc",
            data_dir="/app/data/telemost",
        )

    assert cid == "container_abc"
    assert captured["image"] == "telemost_recorder:latest"
    assert captured["kwargs"]["labels"]["telemost.meeting_id"] == str(meeting_id)
    assert captured["kwargs"]["detach"] is True
    assert any("https://telemost.yandex.ru/j/abc" in str(arg) for arg in captured["kwargs"]["command"])
    assert "/app/data/telemost" in captured["kwargs"]["volumes"]


@pytest.mark.asyncio
async def test_monitor_returns_exit_code():
    container = MagicMock()
    container.wait.return_value = {"StatusCode": 0}
    container.logs.return_value = b"ok\n"

    with patch("services.telemost_recorder_api.docker_client._get_client") as gc:
        gc.return_value.containers.get.return_value = container
        result = await monitor_container("container_abc", timeout_seconds=300)

    assert result["exit_code"] == 0
    assert "ok" in result["logs"]


def test_list_orphan_containers():
    c1 = MagicMock(); c1.labels = {"telemost.meeting_id": "abc"}
    c2 = MagicMock(); c2.labels = {"telemost.meeting_id": "xyz"}
    fake_client = MagicMock()
    fake_client.containers.list.return_value = [c1, c2]

    with patch("services.telemost_recorder_api.docker_client._get_client", return_value=fake_client):
        orphans = list_orphan_containers()

    assert {o["meeting_id"] for o in orphans} == {"abc", "xyz"}
```

- [ ] **Step 2: Run — failing**

Expected: FAIL.

- [ ] **Step 3: Реализовать docker_client.py**

`services/telemost_recorder_api/docker_client.py`:

```python
"""Spawn, monitor, and reconcile telemost_recorder containers via Docker SDK.

Mounts host /app/data/telemost into the spawned container so the recorder's
audio.opus + raw_segments.json artefacts land in shared volume.
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Optional
from uuid import UUID

import docker
from docker.errors import NotFound

from services.telemost_recorder_api.config import RECORDING_HARD_LIMIT_HOURS

logger = logging.getLogger(__name__)

_RECORDER_IMAGE = "telemost_recorder:latest"

_client: Optional[docker.DockerClient] = None


def _get_client() -> docker.DockerClient:
    global _client
    if _client is None:
        _client = docker.from_env()
    return _client


def spawn_recorder_container(
    *,
    meeting_id: UUID,
    meeting_url: str,
    data_dir: str,
    headless: bool = True,
    max_minutes: Optional[int] = None,
) -> str:
    """Run telemost_recorder:latest detached. Returns container id."""
    client = _get_client()
    artefact_subdir = f"{data_dir}/{meeting_id}"
    cmd = [
        "python", "-m", "scripts.telemost_record",
        meeting_url,
        "--meeting-id", str(meeting_id),
        "--output-dir", f"/app/data/telemost/{meeting_id}",
    ]
    if not headless:
        cmd.append("--no-headless")
    if max_minutes:
        cmd.extend(["--max-minutes", str(max_minutes)])

    container = client.containers.run(
        _RECORDER_IMAGE,
        command=cmd,
        detach=True,
        labels={
            "telemost.meeting_id": str(meeting_id),
            "telemost.role": "recorder",
        },
        volumes={
            data_dir: {"bind": "/app/data/telemost", "mode": "rw"},
        },
        environment={
            "TELEMOST_HEADLESS": "true" if headless else "false",
            # Spawned recorder needs Yandex creds; proxy from API container env.
            **{k: os.environ[k] for k in (
                "SPEECHKIT_API_KEY", "YANDEX_FOLDER_ID", "Bitrix_rest_api",
                "TELEMOST_BOT_NAME",
            ) if k in os.environ},
        },
        network="n8n-docker-caddy_default",
        remove=False,
        name=f"telemost_rec_{str(meeting_id)[:8]}",
    )
    logger.info("Spawned recorder container %s for meeting %s", container.id, meeting_id)
    return container.id


async def monitor_container(container_id: str, timeout_seconds: int) -> dict:
    """Wait for container to exit with timeout. Returns {exit_code, logs}.

    On timeout: docker stop + return exit_code=-1.
    """
    client = _get_client()

    def _wait():
        try:
            c = client.containers.get(container_id)
            result = c.wait(timeout=timeout_seconds)
            logs = c.logs(tail=200).decode("utf-8", errors="replace")
            return {"exit_code": result["StatusCode"], "logs": logs}
        except Exception as e:
            logger.exception("monitor_container failed for %s", container_id)
            return {"exit_code": -1, "logs": str(e)}

    return await asyncio.to_thread(_wait)


def stop_container(container_id: str) -> None:
    client = _get_client()
    try:
        c = client.containers.get(container_id)
        c.stop(timeout=10)
        c.remove()
    except NotFound:
        pass
    except Exception:
        logger.exception("stop_container %s failed", container_id)


def list_orphan_containers() -> list[dict]:
    """Return all running containers with telemost.meeting_id label."""
    client = _get_client()
    containers = client.containers.list(filters={"label": "telemost.meeting_id"})
    return [
        {"container_id": c.id, "meeting_id": c.labels.get("telemost.meeting_id")}
        for c in containers
    ]
```

- [ ] **Step 4: Run — passing**

```bash
pytest tests/services/telemost_recorder_api/test_docker_client.py -v
```

Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add services/telemost_recorder_api/docker_client.py tests/services/telemost_recorder_api/test_docker_client.py
git commit -m "feat(telemost-api): docker SDK wrapper (spawn + monitor + orphan listing)"
```

---

## Task 14: Recorder Worker — picks queued, spawns, transitions

**Files:**
- Create: `services/telemost_recorder_api/workers/recorder_worker.py`
- Modify: `services/telemost_recorder_api/app.py` — start worker as asyncio task in lifespan
- Test: `tests/services/telemost_recorder_api/test_recorder_worker.py`

- [ ] **Step 1: Написать failing test**

`tests/services/telemost_recorder_api/test_recorder_worker.py`:

```python
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest

from services.telemost_recorder_api.workers.recorder_worker import process_one


_MEETING_ID = UUID("11111111-1111-1111-1111-111111111111")
_MEETING_URL = "https://telemost.yandex.ru/j/abc"


@pytest.mark.asyncio
async def test_process_one_picks_queued_and_spawns():
    pick = {"id": _MEETING_ID, "meeting_url": _MEETING_URL, "triggered_by": 555}

    async def fake_pick(*a, **k):
        return pick

    spawned = {}

    def fake_spawn(*, meeting_id, meeting_url, data_dir, **kwargs):
        spawned["meeting_id"] = meeting_id
        spawned["url"] = meeting_url
        return "container_abc"

    async def fake_monitor(cid, timeout_seconds):
        return {"exit_code": 0, "logs": "done"}

    async def fake_finalize(meeting_id, exit_code, logs):
        spawned["finalized"] = (meeting_id, exit_code)

    with patch(
        "services.telemost_recorder_api.workers.recorder_worker._pick_queued",
        AsyncMock(side_effect=fake_pick),
    ), patch(
        "services.telemost_recorder_api.workers.recorder_worker.spawn_recorder_container",
        side_effect=fake_spawn,
    ), patch(
        "services.telemost_recorder_api.workers.recorder_worker.monitor_container",
        AsyncMock(side_effect=fake_monitor),
    ), patch(
        "services.telemost_recorder_api.workers.recorder_worker._finalize_recording",
        AsyncMock(side_effect=fake_finalize),
    ):
        result = await process_one()

    assert result is True
    assert spawned["meeting_id"] == _MEETING_ID
    assert spawned["finalized"][0] == _MEETING_ID
    assert spawned["finalized"][1] == 0


@pytest.mark.asyncio
async def test_process_one_returns_false_when_queue_empty():
    with patch(
        "services.telemost_recorder_api.workers.recorder_worker._pick_queued",
        AsyncMock(return_value=None),
    ):
        result = await process_one()
    assert result is False


@pytest.mark.asyncio
async def test_process_one_marks_failed_on_nonzero_exit():
    pick = {"id": _MEETING_ID, "meeting_url": _MEETING_URL, "triggered_by": 555}

    finalize_args = {}

    async def fake_finalize(meeting_id, exit_code, logs):
        finalize_args["exit_code"] = exit_code

    with patch(
        "services.telemost_recorder_api.workers.recorder_worker._pick_queued",
        AsyncMock(return_value=pick),
    ), patch(
        "services.telemost_recorder_api.workers.recorder_worker.spawn_recorder_container",
        return_value="cid",
    ), patch(
        "services.telemost_recorder_api.workers.recorder_worker.monitor_container",
        AsyncMock(return_value={"exit_code": 1, "logs": "boom"}),
    ), patch(
        "services.telemost_recorder_api.workers.recorder_worker._finalize_recording",
        AsyncMock(side_effect=fake_finalize),
    ):
        await process_one()

    assert finalize_args["exit_code"] == 1
```

- [ ] **Step 2: Run — failing**

Expected: FAIL.

- [ ] **Step 3: Реализовать workers/recorder_worker.py**

`services/telemost_recorder_api/workers/recorder_worker.py`:

```python
"""Recorder worker.

Loop:
1. SELECT one queued meeting FOR UPDATE SKIP LOCKED, transition to 'recording'.
2. Spawn telemost_recorder container with meeting_id label.
3. Wait for exit (hard limit RECORDING_HARD_LIMIT_HOURS).
4. On exit, call finalize_recording: load artefacts, transition to 'postprocessing',
   triggers postprocess worker via DB poll.
5. Sleep 5s, repeat.
"""
from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Optional
from uuid import UUID

from services.telemost_recorder_api.config import (
    DATA_DIR,
    MAX_PARALLEL_RECORDINGS,
    RECORDING_HARD_LIMIT_HOURS,
)
from services.telemost_recorder_api.db import get_pool
from services.telemost_recorder_api.docker_client import (
    monitor_container,
    spawn_recorder_container,
)

logger = logging.getLogger(__name__)


async def _pick_queued() -> Optional[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                """
                UPDATE telemost.meetings SET status='recording', started_at=now()
                WHERE id = (
                    SELECT id FROM telemost.meetings
                    WHERE status = 'queued'
                    ORDER BY created_at
                    FOR UPDATE SKIP LOCKED
                    LIMIT 1
                )
                RETURNING id, meeting_url, triggered_by
                """,
            )
    return dict(row) if row else None


async def _finalize_recording(meeting_id: UUID, exit_code: int, logs: str) -> None:
    pool = await get_pool()
    artefact_dir = DATA_DIR / str(meeting_id)
    raw_segments_path = artefact_dir / "raw_segments.json"
    audio_path = artefact_dir / "audio.opus"

    raw_segments = None
    if raw_segments_path.exists():
        try:
            raw_segments = json.loads(raw_segments_path.read_text())
        except Exception:
            logger.exception("Failed to parse raw_segments for %s", meeting_id)

    has_audio = audio_path.exists()

    async with pool.acquire() as conn:
        if exit_code == 0 and (raw_segments is not None or has_audio):
            await conn.execute(
                """
                UPDATE telemost.meetings
                SET status='postprocessing',
                    ended_at=now(),
                    raw_segments=$2::jsonb
                WHERE id = $1
                """,
                meeting_id,
                json.dumps(raw_segments or []),
            )
        else:
            await conn.execute(
                """
                UPDATE telemost.meetings
                SET status='failed',
                    ended_at=now(),
                    error=$2
                WHERE id = $1
                """,
                meeting_id,
                f"recorder exit_code={exit_code}; logs tail: {logs[-500:]}",
            )


async def process_one() -> bool:
    """Pick + record + finalize one meeting. Returns True if processed, False if queue empty."""
    pick = await _pick_queued()
    if not pick:
        return False
    meeting_id = pick["id"]
    logger.info("Recording meeting %s url=%s", meeting_id, pick["meeting_url"])
    container_id = spawn_recorder_container(
        meeting_id=meeting_id,
        meeting_url=pick["meeting_url"],
        data_dir=str(DATA_DIR),
    )
    timeout = RECORDING_HARD_LIMIT_HOURS * 3600
    result = await monitor_container(container_id, timeout_seconds=timeout)
    await _finalize_recording(meeting_id, result["exit_code"], result["logs"])
    return True


async def run_forever() -> None:
    """Worker loop. Phase 0 keeps MAX_PARALLEL_RECORDINGS=1."""
    logger.info("Recorder worker starting (max_parallel=%d)", MAX_PARALLEL_RECORDINGS)
    while True:
        try:
            processed = await process_one()
        except Exception:
            logger.exception("recorder_worker.process_one crashed")
            processed = False
        await asyncio.sleep(2 if processed else 5)
```

- [ ] **Step 4: Запустить worker в lifespan app.py**

В `services/telemost_recorder_api/app.py` обновить lifespan:

```python
import asyncio
from services.telemost_recorder_api.workers.recorder_worker import run_forever as recorder_loop


@asynccontextmanager
async def _lifespan(app: FastAPI):
    logger.info("telemost-recorder-api starting up")
    await get_pool()
    recorder_task = asyncio.create_task(recorder_loop(), name="recorder_worker")
    yield
    logger.info("telemost-recorder-api shutting down")
    recorder_task.cancel()
    try:
        await recorder_task
    except asyncio.CancelledError:
        pass
    await close_pool()
```

- [ ] **Step 5: Run — passing**

```bash
pytest tests/services/telemost_recorder_api/test_recorder_worker.py -v
```

Expected: PASS (3 tests).

- [ ] **Step 6: Commit**

```bash
git add services/telemost_recorder_api/workers/recorder_worker.py services/telemost_recorder_api/app.py tests/services/telemost_recorder_api/test_recorder_worker.py
git commit -m "feat(telemost-api): recorder worker loop (FOR UPDATE SKIP LOCKED + container spawn)"
```

---

## Task 15: LLM Postprocess (single Gemini Flash call)

**Files:**
- Create: `services/telemost_recorder_api/llm_postprocess.py`
- Test: `tests/services/telemost_recorder_api/test_llm_postprocess.py`

- [ ] **Step 1: Написать failing test**

`tests/services/telemost_recorder_api/test_llm_postprocess.py`:

```python
import json
from unittest.mock import AsyncMock, patch

import pytest

from services.telemost_recorder_api.llm_postprocess import (
    build_prompt,
    postprocess_meeting,
    LLMPostprocessError,
)


def test_build_prompt_includes_segments_and_participants():
    segments = [
        {"speaker": "Speaker 0", "start_ms": 0, "end_ms": 25000, "text": "Привет команда"},
        {"speaker": "Speaker 0", "start_ms": 25000, "end_ms": 50000, "text": "Сегодня обсудим венди"},
    ]
    participants = [{"name": "Полина Ермилова", "telegram_id": 123}]
    prompt = build_prompt(segments, participants)
    assert "Привет команда" in prompt
    assert "Полина Ермилова" in prompt
    assert "JSON" in prompt


@pytest.mark.asyncio
async def test_postprocess_returns_structured_json():
    valid_response = {
        "paragraphs": [
            {"speaker": "Полина Ермилова", "start_ms": 0, "text": "Привет, команда. Сегодня обсудим Wendy."},
        ],
        "speakers_map": {"Speaker 0": "Полина Ермилова"},
        "tags": ["продукт", "ассортимент"],
        "summary": {
            "participants": ["Полина Ермилова"],
            "topics": [{"title": "Обсуждение Wendy", "anchor": "[00:00]"}],
            "decisions": ["Закупить ткань для Wendy"],
            "tasks": [{"assignee": "Полина", "what": "Найти поставщика", "when": "до пятницы"}],
        },
    }

    async def fake_call(prompt, model, timeout_seconds):
        return json.dumps(valid_response, ensure_ascii=False)

    segments = [{"speaker": "Speaker 0", "start_ms": 0, "end_ms": 25000, "text": "Привет"}]
    participants = [{"name": "Полина Ермилова", "telegram_id": 123}]

    with patch(
        "services.telemost_recorder_api.llm_postprocess._call_openrouter",
        AsyncMock(side_effect=fake_call),
    ):
        result = await postprocess_meeting(segments, participants)

    assert result["speakers_map"]["Speaker 0"] == "Полина Ермилова"
    assert "продукт" in result["tags"]
    assert result["summary"]["decisions"] == ["Закупить ткань для Wendy"]


@pytest.mark.asyncio
async def test_postprocess_raises_on_invalid_json():
    async def fake_call(prompt, model, timeout_seconds):
        return "not json at all"

    with patch(
        "services.telemost_recorder_api.llm_postprocess._call_openrouter",
        AsyncMock(side_effect=fake_call),
    ):
        with pytest.raises(LLMPostprocessError):
            await postprocess_meeting([{"speaker": "S0", "start_ms": 0, "end_ms": 1, "text": "x"}], [])


@pytest.mark.asyncio
async def test_postprocess_strips_markdown_codefence():
    """LLM любит оборачивать JSON в ```json ... ``` — должны парсить."""
    async def fake_call(prompt, model, timeout_seconds):
        return '```json\n{"paragraphs":[],"speakers_map":{},"tags":[],"summary":{"participants":[],"topics":[],"decisions":[],"tasks":[]}}\n```'

    with patch(
        "services.telemost_recorder_api.llm_postprocess._call_openrouter",
        AsyncMock(side_effect=fake_call),
    ):
        result = await postprocess_meeting([], [])

    assert result["paragraphs"] == []
    assert result["summary"]["participants"] == []
```

- [ ] **Step 2: Run — failing**

Expected: FAIL.

- [ ] **Step 3: Реализовать llm_postprocess.py**

`services/telemost_recorder_api/llm_postprocess.py`:

```python
"""Single-call Gemini Flash postprocessing through OpenRouter.

Phase 0 hardcodes prompts; Phase 2 adds Wookiee dictionary loader.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Optional

import httpx

from services.telemost_recorder_api.config import (
    LLM_POSTPROCESS_MODEL,
    LLM_POSTPROCESS_TIMEOUT_SECONDS,
    OPENROUTER_API_KEY,
)

logger = logging.getLogger(__name__)


class LLMPostprocessError(RuntimeError):
    pass


_PROMPT_TEMPLATE = """Ты постпроцессор русскоязычной транскрипции встречи команды Wookiee. Бренд продаёт нижнее бельё на Wildberries и Ozon.

Дано: список 25-сек чанков сырой транскрипции и имена приглашённых.

Задачи:
1. Склей чанки в связные параграфы по смыслу. Если фраза разрезана на границе чанка — соедини.
2. Восстанови пунктуацию, заглавные буквы, нормализуй фамильярные формы.
3. Сопоставь Speaker N → реальное имя из participants по контексту (если непонятно — оставь Speaker N).
4. Извлеки темы (multi-select из канонического списка): креативы, реклама, маркетинг, продажи, разработка, отчётность, HR, финансы, ассортимент, поставки, логистика, упаковка, бренд, маркетплейс, конкуренты, аналитика, продукт, контент, операции, прочее.
5. Структурированный summary: участники, темы (с цитатой-якорем в формате [MM:SS]), решения, задачи.

Output STRICTLY valid JSON, без markdown-обёрток:
{{
  "paragraphs": [{{"speaker": "<имя или Speaker N>", "start_ms": <int>, "text": "<нормализованный текст>"}}],
  "speakers_map": {{"Speaker 0": "<имя или Speaker 0>"}},
  "tags": ["<canonical topic>"],
  "summary": {{
    "participants": ["<имя>"],
    "topics": [{{"title": "<short>", "anchor": "[MM:SS]"}}],
    "decisions": ["<краткая формулировка>"],
    "tasks": [{{"assignee": "<имя или null>", "what": "<задача>", "when": "<срок или null>"}}]
  }}
}}

Participants:
{participants}

Segments:
{segments}
"""


def build_prompt(segments: list[dict], participants: list[dict]) -> str:
    seg_text = "\n".join(
        f"[{s['start_ms']//1000:>4}s {s['speaker']}] {s['text']}"
        for s in segments
    )
    p_text = "\n".join(f"- {p['name']}" for p in participants) or "(нет данных)"
    return _PROMPT_TEMPLATE.format(participants=p_text, segments=seg_text)


def _strip_markdown_codefence(text: str) -> str:
    text = text.strip()
    m = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.DOTALL)
    if m:
        return m.group(1).strip()
    return text


async def _call_openrouter(prompt: str, model: str, timeout_seconds: int) -> str:
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer": "https://wookiee.shop",
        "X-Title": "Wookiee Telemost Recorder",
        "Content-Type": "application/json",
    }
    body = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
    }
    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        resp = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=body,
        )
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"]


def _validate_shape(data: dict) -> None:
    required = {"paragraphs", "speakers_map", "tags", "summary"}
    missing = required - set(data.keys())
    if missing:
        raise LLMPostprocessError(f"missing keys: {missing}")
    summary = data["summary"]
    sub_required = {"participants", "topics", "decisions", "tasks"}
    if not sub_required.issubset(summary.keys()):
        raise LLMPostprocessError(f"summary missing: {sub_required - set(summary.keys())}")


async def postprocess_meeting(
    segments: list[dict],
    participants: list[dict],
    *,
    model: Optional[str] = None,
) -> dict:
    """Single-call postprocess. Raises LLMPostprocessError on JSON parse / shape failure."""
    prompt = build_prompt(segments, participants)
    raw = await _call_openrouter(
        prompt,
        model or LLM_POSTPROCESS_MODEL,
        LLM_POSTPROCESS_TIMEOUT_SECONDS,
    )
    cleaned = _strip_markdown_codefence(raw)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        logger.error("LLM returned non-JSON: %r", cleaned[:500])
        raise LLMPostprocessError(f"invalid JSON: {e}") from e
    _validate_shape(data)
    return data
```

- [ ] **Step 4: Run — passing**

```bash
pytest tests/services/telemost_recorder_api/test_llm_postprocess.py -v
```

Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add services/telemost_recorder_api/llm_postprocess.py tests/services/telemost_recorder_api/test_llm_postprocess.py
git commit -m "feat(telemost-api): single-call LLM postprocess via OpenRouter Gemini Flash"
```

---

## Task 16: Postprocess Worker + Empty-Meeting Fallback

**Files:**
- Create: `services/telemost_recorder_api/workers/postprocess_worker.py`
- Modify: `services/telemost_recorder_api/app.py` — добавить вторую asyncio task
- Test: `tests/services/telemost_recorder_api/test_postprocess_worker.py`

- [ ] **Step 1: Написать failing test**

`tests/services/telemost_recorder_api/test_postprocess_worker.py`:

```python
import json
from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest

from services.telemost_recorder_api.workers.postprocess_worker import process_one


_MEETING_ID = UUID("11111111-1111-1111-1111-111111111111")


@pytest.mark.asyncio
async def test_empty_segments_marks_done_without_llm():
    pick = {
        "id": _MEETING_ID, "raw_segments": [], "triggered_by": 555,
        "title": None, "invitees": [],
    }

    llm_called = False

    async def fake_llm(*a, **k):
        nonlocal llm_called
        llm_called = True
        return {}

    captured_update = {}

    async def fake_update(meeting_id, status, **fields):
        captured_update["meeting_id"] = meeting_id
        captured_update["status"] = status
        captured_update["fields"] = fields

    notify_called = False

    async def fake_notify(*a, **k):
        nonlocal notify_called
        notify_called = True

    with patch(
        "services.telemost_recorder_api.workers.postprocess_worker._pick_postprocessing",
        AsyncMock(return_value=pick),
    ), patch(
        "services.telemost_recorder_api.workers.postprocess_worker.postprocess_meeting",
        AsyncMock(side_effect=fake_llm),
    ), patch(
        "services.telemost_recorder_api.workers.postprocess_worker._update_meeting",
        AsyncMock(side_effect=fake_update),
    ), patch(
        "services.telemost_recorder_api.workers.postprocess_worker.notify_meeting_result",
        AsyncMock(side_effect=fake_notify),
    ):
        result = await process_one()

    assert result is True
    assert llm_called is False
    assert captured_update["status"] == "done"
    assert captured_update["fields"]["summary"] == {"empty": True, "note": "no_speech_detected"}
    assert notify_called is True


@pytest.mark.asyncio
async def test_normal_segments_runs_llm_and_updates_done():
    pick = {
        "id": _MEETING_ID,
        "raw_segments": [{"speaker": "Speaker 0", "start_ms": 0, "end_ms": 25000, "text": "Привет"}],
        "triggered_by": 555, "title": "Test", "invitees": [],
    }

    llm_result = {
        "paragraphs": [{"speaker": "Полина", "start_ms": 0, "text": "Привет"}],
        "speakers_map": {"Speaker 0": "Полина"},
        "tags": ["прочее"],
        "summary": {
            "participants": ["Полина"], "topics": [], "decisions": [], "tasks": [],
        },
    }

    captured_update = {}

    async def fake_update(meeting_id, status, **fields):
        captured_update["status"] = status
        captured_update["fields"] = fields

    with patch(
        "services.telemost_recorder_api.workers.postprocess_worker._pick_postprocessing",
        AsyncMock(return_value=pick),
    ), patch(
        "services.telemost_recorder_api.workers.postprocess_worker.postprocess_meeting",
        AsyncMock(return_value=llm_result),
    ), patch(
        "services.telemost_recorder_api.workers.postprocess_worker._update_meeting",
        AsyncMock(side_effect=fake_update),
    ), patch(
        "services.telemost_recorder_api.workers.postprocess_worker.notify_meeting_result",
        AsyncMock(),
    ):
        await process_one()

    assert captured_update["status"] == "done"
    assert captured_update["fields"]["tags"] == ["прочее"]
    assert captured_update["fields"]["speakers_map"] == {"Speaker 0": "Полина"}


@pytest.mark.asyncio
async def test_llm_failure_marks_failed():
    pick = {
        "id": _MEETING_ID,
        "raw_segments": [{"speaker": "S0", "start_ms": 0, "end_ms": 1, "text": "x"}],
        "triggered_by": 555, "title": None, "invitees": [],
    }
    captured_update = {}

    async def fake_update(meeting_id, status, **fields):
        captured_update["status"] = status
        captured_update["fields"] = fields

    from services.telemost_recorder_api.llm_postprocess import LLMPostprocessError

    with patch(
        "services.telemost_recorder_api.workers.postprocess_worker._pick_postprocessing",
        AsyncMock(return_value=pick),
    ), patch(
        "services.telemost_recorder_api.workers.postprocess_worker.postprocess_meeting",
        AsyncMock(side_effect=LLMPostprocessError("bad json")),
    ), patch(
        "services.telemost_recorder_api.workers.postprocess_worker._update_meeting",
        AsyncMock(side_effect=fake_update),
    ), patch(
        "services.telemost_recorder_api.workers.postprocess_worker.notify_meeting_result",
        AsyncMock(),
    ):
        await process_one()

    assert captured_update["status"] == "failed"
    assert "bad json" in captured_update["fields"]["error"]
```

- [ ] **Step 2: Run — failing**

Expected: FAIL.

- [ ] **Step 3: Реализовать workers/postprocess_worker.py**

`services/telemost_recorder_api/workers/postprocess_worker.py`:

```python
"""Postprocess worker.

Loop:
1. Pick a meeting with status='postprocessing' (FOR UPDATE SKIP LOCKED).
2. If raw_segments is empty → mark done with empty-fallback summary, notify.
3. Else: call LLM postprocess, update fields, mark done, notify.
4. On exception: mark failed, notify with error message.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Optional
from uuid import UUID

from services.telemost_recorder_api.db import get_pool
from services.telemost_recorder_api.llm_postprocess import (
    LLMPostprocessError,
    postprocess_meeting,
)
from services.telemost_recorder_api.notifier import notify_meeting_result

logger = logging.getLogger(__name__)


async def _pick_postprocessing() -> Optional[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                """
                SELECT id, raw_segments, triggered_by, title, invitees
                FROM telemost.meetings
                WHERE status = 'postprocessing'
                ORDER BY ended_at NULLS LAST
                FOR UPDATE SKIP LOCKED
                LIMIT 1
                """,
            )
    if not row:
        return None
    out = dict(row)
    if isinstance(out.get("raw_segments"), str):
        out["raw_segments"] = json.loads(out["raw_segments"])
    if isinstance(out.get("invitees"), str):
        out["invitees"] = json.loads(out["invitees"])
    return out


_JSONB_FIELDS = {"summary", "speakers_map", "processed_paragraphs", "raw_segments", "invitees"}


async def _update_meeting(meeting_id: UUID, status: str, **fields: Any) -> None:
    """Update meeting row. Knows which fields are jsonb vs text[] vs scalar."""
    pool = await get_pool()
    set_clauses = ["status = $2"]
    args: list[Any] = [meeting_id, status]
    idx = 3
    for k, v in fields.items():
        if k in _JSONB_FIELDS:
            args.append(json.dumps(v, ensure_ascii=False))
            set_clauses.append(f"{k} = ${idx}::jsonb")
        else:
            # `tags text[]` and scalars (text/timestamptz/int) — pass directly,
            # asyncpg adapts python list[str] → text[] natively.
            args.append(v)
            set_clauses.append(f"{k} = ${idx}")
        idx += 1
    query = f"UPDATE telemost.meetings SET {', '.join(set_clauses)} WHERE id = $1"
    async with pool.acquire() as conn:
        await conn.execute(query, *args)


async def process_one() -> bool:
    pick = await _pick_postprocessing()
    if not pick:
        return False
    meeting_id = pick["id"]
    segments = pick["raw_segments"] or []
    invitees = pick["invitees"] or []
    logger.info("Postprocessing meeting %s (segments=%d)", meeting_id, len(segments))

    try:
        if not segments:
            await _update_meeting(
                meeting_id,
                "done",
                summary={"empty": True, "note": "no_speech_detected"},
                tags=[],
            )
        else:
            result = await postprocess_meeting(segments, invitees)
            await _update_meeting(
                meeting_id,
                "done",
                processed_paragraphs=result["paragraphs"],
                speakers_map=result["speakers_map"],
                tags=result["tags"],
                summary=result["summary"],
            )
        await notify_meeting_result(meeting_id)
    except LLMPostprocessError as e:
        logger.exception("LLM failed for meeting %s", meeting_id)
        await _update_meeting(meeting_id, "failed", error=f"LLM: {e}")
        await notify_meeting_result(meeting_id)
    except Exception as e:
        logger.exception("Postprocess crashed for meeting %s", meeting_id)
        await _update_meeting(meeting_id, "failed", error=f"unexpected: {e}")
        await notify_meeting_result(meeting_id)
    return True


async def run_forever() -> None:
    logger.info("Postprocess worker starting")
    while True:
        try:
            processed = await process_one()
        except Exception:
            logger.exception("postprocess_worker.process_one crashed")
            processed = False
        await asyncio.sleep(2 if processed else 5)
```

- [ ] **Step 4: Запустить worker в lifespan app.py**

Дополнить lifespan ещё одной asyncio task:

```python
from services.telemost_recorder_api.workers.postprocess_worker import run_forever as postprocess_loop

@asynccontextmanager
async def _lifespan(app: FastAPI):
    await get_pool()
    recorder_task = asyncio.create_task(recorder_loop(), name="recorder_worker")
    postprocess_task = asyncio.create_task(postprocess_loop(), name="postprocess_worker")
    yield
    for t in (recorder_task, postprocess_task):
        t.cancel()
        try:
            await t
        except asyncio.CancelledError:
            pass
    await close_pool()
```

- [ ] **Step 5: Run — passing**

```bash
pytest tests/services/telemost_recorder_api/test_postprocess_worker.py -v
```

Expected: PASS (3 tests).

- [ ] **Step 6: Commit**

```bash
git add services/telemost_recorder_api/workers/postprocess_worker.py services/telemost_recorder_api/app.py tests/services/telemost_recorder_api/test_postprocess_worker.py
git commit -m "feat(telemost-api): postprocess worker with empty-meeting fallback"
```

---

## Task 17: Notifier — idempotent DM with chunking + transcript attachment

**Files:**
- Create: `services/telemost_recorder_api/notifier.py`
- Test: `tests/services/telemost_recorder_api/test_notifier.py`

- [ ] **Step 1: Написать failing test**

`tests/services/telemost_recorder_api/test_notifier.py`:

```python
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest

from services.telemost_recorder_api.notifier import (
    notify_meeting_result,
    format_summary_message,
    build_transcript_text,
)


_MEETING_ID = UUID("11111111-1111-1111-1111-111111111111")


def test_format_summary_message_normal():
    meeting = {
        "id": _MEETING_ID,
        "title": "Дейли",
        "started_at": datetime(2026, 5, 8, 10, 0, tzinfo=timezone.utc),
        "duration_seconds": 1800,
        "summary": {
            "participants": ["Полина", "Иван"],
            "topics": [{"title": "Релиз", "anchor": "[01:23]"}],
            "decisions": ["Релизим в пятницу"],
            "tasks": [{"assignee": "Иван", "what": "Подготовить чейнджлог", "when": "до четверга"}],
        },
        "tags": ["разработка"],
    }
    msg = format_summary_message(meeting)
    assert "Дейли" in msg
    assert "Полина" in msg
    assert "Релиз" in msg
    assert "Релизим в пятницу" in msg
    assert "Иван — Подготовить чейнджлог" in msg
    assert "разработка" in msg


def test_format_summary_message_empty():
    meeting = {
        "id": _MEETING_ID, "title": None,
        "started_at": datetime(2026, 5, 8, 10, 0, tzinfo=timezone.utc),
        "duration_seconds": 600,
        "summary": {"empty": True, "note": "no_speech_detected"},
        "tags": [],
    }
    msg = format_summary_message(meeting)
    assert "речь" in msg.lower() or "тишин" in msg.lower()


def test_build_transcript_text():
    paragraphs = [
        {"speaker": "Полина", "start_ms": 0, "text": "Привет, команда."},
        {"speaker": "Иван", "start_ms": 25000, "text": "Привет."},
    ]
    text = build_transcript_text(paragraphs)
    assert "[00:00] Полина: Привет, команда." in text
    assert "[00:25] Иван: Привет." in text


@pytest.mark.asyncio
async def test_notify_idempotent_skips_already_notified():
    """Если notified_at уже не NULL → не шлём."""
    class FakeConn:
        async def fetchval(self, query, *args):
            return None  # ничего не вернулось — уже нотифицировано

        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False

    class FakePool:
        def acquire(self): return FakeConn()

    sent = []
    with patch(
        "services.telemost_recorder_api.notifier.get_pool",
        AsyncMock(return_value=FakePool()),
    ), patch(
        "services.telemost_recorder_api.notifier.tg_send_message",
        AsyncMock(side_effect=lambda c, t, **k: sent.append(t)),
    ):
        await notify_meeting_result(_MEETING_ID)

    assert sent == []


@pytest.mark.asyncio
async def test_notify_sends_summary_and_transcript():
    meeting_row = {
        "id": _MEETING_ID,
        "title": "Дейли",
        "triggered_by": 555,
        "started_at": datetime(2026, 5, 8, 10, 0, tzinfo=timezone.utc),
        "duration_seconds": 1800,
        "status": "done",
        "summary": {
            "participants": ["Полина"], "topics": [],
            "decisions": ["реш"], "tasks": [],
        },
        "tags": ["прочее"],
        "processed_paragraphs": [
            {"speaker": "Полина", "start_ms": 0, "text": "Привет."},
        ],
        "error": None,
    }

    class FakeConn:
        async def fetchval(self, query, *args):
            return datetime(2026, 5, 8, 11, 0, tzinfo=timezone.utc)

        async def fetchrow(self, query, *args):
            return meeting_row

        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False

    class FakePool:
        def acquire(self): return FakeConn()

    msgs = []
    docs = []

    with patch(
        "services.telemost_recorder_api.notifier.get_pool",
        AsyncMock(return_value=FakePool()),
    ), patch(
        "services.telemost_recorder_api.notifier.tg_send_message",
        AsyncMock(side_effect=lambda c, t, **k: msgs.append((c, t))),
    ), patch(
        "services.telemost_recorder_api.notifier.tg_send_document",
        AsyncMock(side_effect=lambda c, file_bytes, filename, **k: docs.append((c, filename))),
    ):
        await notify_meeting_result(_MEETING_ID)

    assert msgs[0][0] == 555
    assert "Дейли" in msgs[0][1]
    assert docs[0][0] == 555
    assert docs[0][1].endswith(".txt")


@pytest.mark.asyncio
async def test_notify_failed_meeting_sends_error():
    meeting_row = {
        "id": _MEETING_ID,
        "title": None,
        "triggered_by": 555,
        "started_at": None,
        "duration_seconds": None,
        "status": "failed",
        "summary": None,
        "tags": None,
        "processed_paragraphs": None,
        "error": "recorder exit_code=1",
    }

    class FakeConn:
        async def fetchval(self, query, *args):
            return datetime.now(timezone.utc)
        async def fetchrow(self, query, *args):
            return meeting_row
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False

    class FakePool:
        def acquire(self): return FakeConn()

    msgs = []
    docs = []

    with patch(
        "services.telemost_recorder_api.notifier.get_pool",
        AsyncMock(return_value=FakePool()),
    ), patch(
        "services.telemost_recorder_api.notifier.tg_send_message",
        AsyncMock(side_effect=lambda c, t, **k: msgs.append((c, t))),
    ), patch(
        "services.telemost_recorder_api.notifier.tg_send_document",
        AsyncMock(side_effect=lambda *a, **k: docs.append(1)),
    ):
        await notify_meeting_result(_MEETING_ID)

    assert any("ошибк" in m[1].lower() or "fail" in m[1].lower() for m in msgs)
    assert docs == []  # для failed transcript не шлём
```

- [ ] **Step 2: Run — failing**

Expected: FAIL.

- [ ] **Step 3: Реализовать notifier.py**

`services/telemost_recorder_api/notifier.py`:

```python
"""Notifier — sends meeting result DM with idempotent claim.

Idempotency: атомарный UPDATE ... WHERE notified_at IS NULL RETURNING.
Если RETURNING ничего не вернул → уже нотифицировано, skip.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any
from uuid import UUID

from services.telemost_recorder_api.db import get_pool
from services.telemost_recorder_api.telegram_client import (
    TelegramAPIError,
    tg_send_document,
    tg_send_message,
)

logger = logging.getLogger(__name__)


def _ms_to_mmss(ms: int) -> str:
    s = ms // 1000
    return f"{s // 60:02d}:{s % 60:02d}"


def _fmt_duration(seconds: int | None) -> str:
    if not seconds:
        return "—"
    m = seconds // 60
    if m < 60:
        return f"{m} мин"
    return f"{m // 60} ч {m % 60} мин"


def format_summary_message(meeting: dict) -> str:
    title = meeting.get("title") or "(без названия)"
    started = meeting["started_at"].strftime("%d.%m %H:%M") if meeting.get("started_at") else "—"
    duration = _fmt_duration(meeting.get("duration_seconds"))
    summary = meeting.get("summary") or {}

    if summary.get("empty"):
        return (
            f"📭 *{title}* ({started}, {duration})\n\n"
            f"Запись завершена, речи не было распознано."
        )

    lines = [f"📝 *{title}* ({started}, {duration})"]

    participants = summary.get("participants") or []
    if participants:
        lines.append(f"\n👥 *Участники:* {', '.join(participants)}")

    topics = summary.get("topics") or []
    if topics:
        lines.append("\n🎯 *Темы:*")
        for t in topics[:8]:
            anchor = t.get("anchor") or ""
            lines.append(f"• {t.get('title', '?')} {anchor}")

    decisions = summary.get("decisions") or []
    if decisions:
        lines.append("\n✅ *Решения:*")
        for d in decisions[:6]:
            lines.append(f"• {d}")

    tasks = summary.get("tasks") or []
    if tasks:
        lines.append("\n📋 *Задачи:*")
        for t in tasks[:8]:
            assignee = t.get("assignee") or "—"
            when = f" ({t['when']})" if t.get("when") else ""
            lines.append(f"• {assignee} — {t.get('what', '?')}{when}")

    tags = meeting.get("tags") or []
    if tags:
        lines.append(f"\n🏷 {', '.join(tags)}")

    lines.append(f"\n_id_ `{str(meeting['id'])[:8]}`")
    return "\n".join(lines)


def build_transcript_text(paragraphs: list[dict]) -> str:
    if not paragraphs:
        return "(пустой transcript)"
    out = []
    for p in paragraphs:
        ts = _ms_to_mmss(p.get("start_ms", 0))
        speaker = p.get("speaker", "?")
        text = p.get("text", "")
        out.append(f"[{ts}] {speaker}: {text}")
    return "\n".join(out)


async def _claim_notification(meeting_id: UUID) -> datetime | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval(
            """
            UPDATE telemost.meetings SET notified_at = now()
            WHERE id = $1 AND notified_at IS NULL
            RETURNING notified_at
            """,
            meeting_id,
        )


async def _load_meeting(meeting_id: UUID) -> dict | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, title, triggered_by, started_at, duration_seconds,
                   status, summary, tags, processed_paragraphs, error
            FROM telemost.meetings WHERE id = $1
            """,
            meeting_id,
        )
    if not row:
        return None
    out = dict(row)
    for k in ("summary", "processed_paragraphs"):
        if isinstance(out.get(k), str):
            out[k] = json.loads(out[k])
    return out


async def notify_meeting_result(meeting_id: UUID) -> None:
    """Idempotent: only one notification per meeting."""
    claimed = await _claim_notification(meeting_id)
    if claimed is None:
        logger.info("Meeting %s already notified, skipping", meeting_id)
        return

    meeting = await _load_meeting(meeting_id)
    if not meeting:
        logger.warning("Meeting %s vanished after claim", meeting_id)
        return

    triggered_by = meeting["triggered_by"]
    if not triggered_by:
        logger.warning("Meeting %s has no triggered_by, skip notify", meeting_id)
        return

    if meeting["status"] == "failed":
        err = meeting.get("error") or "unknown"
        try:
            await tg_send_message(
                triggered_by,
                f"❌ Запись `{str(meeting_id)[:8]}` завершилась ошибкой:\n```\n{err[:500]}\n```",
            )
        except TelegramAPIError:
            logger.exception("Failed to notify failure for %s", meeting_id)
        return

    summary_text = format_summary_message(meeting)
    try:
        await tg_send_message(triggered_by, summary_text)
    except TelegramAPIError:
        logger.exception("Failed to send summary for %s", meeting_id)
        return

    paragraphs = meeting.get("processed_paragraphs") or []
    if paragraphs:
        transcript = build_transcript_text(paragraphs)
        filename = f"transcript_{str(meeting_id)[:8]}.txt"
        try:
            await tg_send_document(
                triggered_by,
                transcript.encode("utf-8"),
                filename=filename,
                caption=f"Полный transcript ({len(paragraphs)} параграфов)",
            )
        except TelegramAPIError:
            logger.exception("Failed to send transcript for %s", meeting_id)
```

- [ ] **Step 4: Run — passing**

```bash
pytest tests/services/telemost_recorder_api/test_notifier.py -v
```

Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add services/telemost_recorder_api/notifier.py tests/services/telemost_recorder_api/test_notifier.py
git commit -m "feat(telemost-api): notifier with idempotent claim + transcript attachment"
```

---

## Task 18: Audio Uploader to Supabase Storage

**Files:**
- Create: `services/telemost_recorder_api/audio_uploader.py`
- Modify: `services/telemost_recorder_api/workers/recorder_worker.py` — call uploader на успехе
- Test: `tests/services/telemost_recorder_api/test_audio_uploader.py`

- [ ] **Step 1: Написать failing test**

`tests/services/telemost_recorder_api/test_audio_uploader.py`:

```python
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import httpx
import pytest

from services.telemost_recorder_api.audio_uploader import upload_audio_to_storage


_MEETING_ID = UUID("11111111-1111-1111-1111-111111111111")


@pytest.mark.asyncio
async def test_upload_returns_signed_url(tmp_path):
    audio_file = tmp_path / "audio.opus"
    audio_file.write_bytes(b"fake audio")

    upload_resp = httpx.Response(200, json={"Key": f"telemost-audio/meetings/{_MEETING_ID}/audio.opus"})
    sign_resp = httpx.Response(200, json={"signedURL": "/storage/v1/object/sign/telemost-audio/abc?token=xyz"})

    async def fake_post(url, *a, **kw):
        if "object/" in url and "sign" not in url:
            return upload_resp
        if "sign" in url:
            return sign_resp
        raise AssertionError(f"unexpected url {url}")

    with patch("httpx.AsyncClient.post", AsyncMock(side_effect=fake_post)):
        result = await upload_audio_to_storage(audio_file, meeting_id=_MEETING_ID, ttl_days=30)

    assert result["signed_url"].startswith("https://")
    assert "telemost-audio" in result["signed_url"]
    assert isinstance(result["expires_at"], datetime)


@pytest.mark.asyncio
async def test_upload_raises_on_upload_failure(tmp_path):
    audio_file = tmp_path / "audio.opus"
    audio_file.write_bytes(b"fake")

    fail_resp = httpx.Response(500, json={"error": "boom"})

    with patch("httpx.AsyncClient.post", AsyncMock(return_value=fail_resp)):
        with pytest.raises(RuntimeError):
            await upload_audio_to_storage(audio_file, meeting_id=_MEETING_ID, ttl_days=30)
```

- [ ] **Step 2: Run — failing**

Expected: FAIL.

- [ ] **Step 3: Реализовать audio_uploader.py**

`services/telemost_recorder_api/audio_uploader.py`:

```python
"""Upload recorded audio to Supabase Storage bucket telemost-audio + signed URL."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

import httpx

from services.telemost_recorder_api.config import (
    SUPABASE_SERVICE_ROLE_KEY,
    SUPABASE_URL,
)

logger = logging.getLogger(__name__)

_BUCKET = "telemost-audio"


async def upload_audio_to_storage(
    audio_path: Path,
    *,
    meeting_id: UUID,
    ttl_days: int,
) -> dict:
    object_key = f"meetings/{meeting_id}/audio.opus"
    headers = {"Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}"}

    async with httpx.AsyncClient(timeout=300) as client:
        with audio_path.open("rb") as f:
            upload_url = f"{SUPABASE_URL}/storage/v1/object/{_BUCKET}/{object_key}"
            resp = await client.post(
                upload_url,
                headers={**headers, "Content-Type": "audio/ogg", "x-upsert": "true"},
                content=f.read(),
            )
        if resp.status_code >= 400:
            raise RuntimeError(f"Storage upload failed [{resp.status_code}]: {resp.text}")

        ttl_seconds = ttl_days * 86400
        sign_url = f"{SUPABASE_URL}/storage/v1/object/sign/{_BUCKET}/{object_key}"
        sign_resp = await client.post(
            sign_url,
            headers={**headers, "Content-Type": "application/json"},
            json={"expiresIn": ttl_seconds},
        )
        if sign_resp.status_code >= 400:
            raise RuntimeError(f"Sign URL failed [{sign_resp.status_code}]: {sign_resp.text}")
        rel = sign_resp.json()["signedURL"]
        signed = f"{SUPABASE_URL}/storage/v1{rel}" if rel.startswith("/") else rel

    expires_at = datetime.now(timezone.utc) + timedelta(days=ttl_days)
    logger.info("Uploaded audio for %s, expires %s", meeting_id, expires_at)
    return {"signed_url": signed, "expires_at": expires_at, "object_key": object_key}
```

- [ ] **Step 4: Подключить uploader в recorder_worker._finalize_recording**

В `services/telemost_recorder_api/workers/recorder_worker.py` обновить `_finalize_recording`: после успешного recording (exit_code==0 и есть audio) — загрузить в Storage, записать `audio_path` (signed_url) и `audio_expires_at`. На ошибке upload — оставить локально, лог + продолжить (raw_segments всё равно пишем).

```python
# Добавить вверху:
from services.telemost_recorder_api.audio_uploader import upload_audio_to_storage
from services.telemost_recorder_api.config import AUDIO_RETENTION_DAYS

# В _finalize_recording, ветка success:
        if exit_code == 0 and (raw_segments is not None or has_audio):
            audio_signed_url = None
            audio_expires = None
            if has_audio:
                try:
                    upload = await upload_audio_to_storage(
                        audio_path, meeting_id=meeting_id, ttl_days=AUDIO_RETENTION_DAYS,
                    )
                    audio_signed_url = upload["signed_url"]
                    audio_expires = upload["expires_at"]
                except Exception:
                    logger.exception("Audio upload failed for %s — leaving local", meeting_id)

            await conn.execute(
                """
                UPDATE telemost.meetings
                SET status='postprocessing',
                    ended_at=now(),
                    raw_segments=$2::jsonb,
                    audio_path=$3,
                    audio_expires_at=$4
                WHERE id = $1
                """,
                meeting_id,
                json.dumps(raw_segments or []),
                audio_signed_url,
                audio_expires,
            )
```

- [ ] **Step 5: Run — passing**

```bash
pytest tests/services/telemost_recorder_api/test_audio_uploader.py -v
pytest tests/services/telemost_recorder_api/test_recorder_worker.py -v
```

Expected: PASS (existing recorder_worker tests should still pass — uploader is mocked or not triggered when has_audio=False).

- [ ] **Step 6: Commit**

```bash
git add services/telemost_recorder_api/audio_uploader.py services/telemost_recorder_api/workers/recorder_worker.py tests/services/telemost_recorder_api/test_audio_uploader.py
git commit -m "feat(telemost-api): upload recorded audio to Supabase Storage with signed URL"
```

---

## Task 19: Bot Avatar + setMyCommands + Webhook Setup Script

**Files:**
- Create: `services/telemost_recorder_api/assets/avatar.png` (binary asset, 512×512)
- Create: `scripts/telemost_setup_webhook.py` (one-shot setWebhook + setMyCommands + setMyDescription + setMyPhoto)
- Test: `tests/scripts/test_telemost_setup_webhook.py`

- [ ] **Step 1: Скачать/создать avatar.png**

Положить файл `services/telemost_recorder_api/assets/avatar.png` (512×512 PNG, брендированный микрофон + Wookiee mark). Если ассета пока нет — генерим заглушку через ImageMagick:

```bash
mkdir -p services/telemost_recorder_api/assets
convert -size 512x512 xc:'#1a1a1a' -fill '#f5b800' -gravity center \
  -font 'Helvetica-Bold' -pointsize 96 -annotate 0 'WR' \
  services/telemost_recorder_api/assets/avatar.png
file services/telemost_recorder_api/assets/avatar.png
```

Expected: `PNG image data, 512 x 512`.

- [ ] **Step 2: Написать failing test для скрипта**

`tests/scripts/test_telemost_setup_webhook.py`:

```python
from unittest.mock import AsyncMock, patch

import pytest

from scripts.telemost_setup_webhook import setup


@pytest.mark.asyncio
async def test_setup_calls_all_endpoints():
    captured = []

    async def fake_call(method, **payload):
        captured.append(method)
        return {}

    with patch(
        "scripts.telemost_setup_webhook.tg_call",
        AsyncMock(side_effect=fake_call),
    ), patch(
        "scripts.telemost_setup_webhook.tg_set_photo_if_missing",
        AsyncMock(),
    ):
        await setup(webhook_url="https://recorder.os.wookiee.shop/telegram/webhook")

    assert "setWebhook" in captured
    assert "setMyCommands" in captured
    assert "setMyDescription" in captured
```

- [ ] **Step 3: Run — failing**

Expected: FAIL.

- [ ] **Step 4: Реализовать scripts/telemost_setup_webhook.py**

`scripts/telemost_setup_webhook.py`:

```python
"""One-shot bot setup: webhook, commands, description, avatar.

Usage: python scripts/telemost_setup_webhook.py [--webhook-url <url>]
"""
from __future__ import annotations

import argparse
import asyncio
import logging
from pathlib import Path

from services.telemost_recorder_api.config import (
    ASSETS_DIR,
    TELEMOST_WEBHOOK_SECRET,
)
from services.telemost_recorder_api.telegram_client import tg_call

logger = logging.getLogger(__name__)


_COMMANDS = [
    {"command": "start", "description": "Начать работу"},
    {"command": "help", "description": "Справка"},
    {"command": "record", "description": "Записать встречу: /record <ссылка>"},
    {"command": "status", "description": "Твои активные/последние записи"},
    {"command": "list", "description": "Последние 10 встреч с твоим участием"},
]

_DESCRIPTION = (
    "Wookiee Recorder — записываю встречи Я.Телемоста, "
    "присылаю summary и transcript в DM. Доступ через Bitrix24-roster."
)


async def tg_set_photo_if_missing(avatar_path: Path) -> None:
    import httpx

    from services.telemost_recorder_api.config import TELEMOST_BOT_TOKEN

    photos = await tg_call("getUserProfilePhotos", user_id=int(__import__("services.telemost_recorder_api.config", fromlist=["TELEMOST_BOT_ID"]).TELEMOST_BOT_ID), limit=1)
    if photos.get("total_count", 0) > 0:
        logger.info("Bot already has avatar, skip")
        return

    url = f"https://api.telegram.org/bot{TELEMOST_BOT_TOKEN}/setMyPhoto"
    with avatar_path.open("rb") as f:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(url, files={"photo": ("avatar.png", f, "image/png")})
        body = resp.json()
        if not body.get("ok"):
            logger.warning("setMyPhoto failed: %s", body.get("description"))
        else:
            logger.info("Avatar set")


async def setup(webhook_url: str) -> None:
    await tg_call(
        "setWebhook",
        url=webhook_url,
        secret_token=TELEMOST_WEBHOOK_SECRET,
        allowed_updates=["message", "callback_query"],
    )
    await tg_call("setMyCommands", commands=_COMMANDS)
    await tg_call("setMyDescription", description=_DESCRIPTION)

    avatar = ASSETS_DIR / "avatar.png"
    if avatar.exists():
        await tg_set_photo_if_missing(avatar)
    else:
        logger.warning("Avatar not found at %s", avatar)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    p = argparse.ArgumentParser()
    p.add_argument("--webhook-url", default="https://recorder.os.wookiee.shop/telegram/webhook")
    args = p.parse_args()
    asyncio.run(setup(args.webhook_url))


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run — passing**

```bash
pytest tests/scripts/test_telemost_setup_webhook.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add services/telemost_recorder_api/assets/avatar.png scripts/telemost_setup_webhook.py tests/scripts/test_telemost_setup_webhook.py
git commit -m "feat(telemost-api): bot avatar + webhook setup runbook script"
```

---

## Task 20: Dockerfile + docker-compose service + Caddy

**Files:**
- Create: `deploy/Dockerfile.telemost_recorder_api`
- Modify: `deploy/docker-compose.yml`
- Modify: `deploy/Caddyfile`

- [ ] **Step 1: Создать Dockerfile**

`deploy/Dockerfile.telemost_recorder_api`:

```dockerfile
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    TZ=Europe/Moscow

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY services/telemost_recorder_api/requirements.txt /app/requirements.txt
RUN pip install -r /app/requirements.txt

COPY services/telemost_recorder_api/ /app/services/telemost_recorder_api/
COPY shared/ /app/shared/
COPY scripts/telemost_setup_webhook.py /app/scripts/

EXPOSE 8006

CMD ["uvicorn", "services.telemost_recorder_api.app:create_app", \
     "--factory", "--host", "0.0.0.0", "--port", "8006"]
```

- [ ] **Step 2: Добавить service в docker-compose.yml**

В `deploy/docker-compose.yml` добавить:

```yaml
  telemost-recorder-api:
    build:
      context: ..
      dockerfile: deploy/Dockerfile.telemost_recorder_api
    container_name: telemost_recorder_api
    restart: unless-stopped
    env_file: [../.env]
    environment:
      - PYTHONUNBUFFERED=1
      - TZ=Europe/Moscow
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - ../data/telemost:/app/data/telemost
    networks: [n8n-docker-caddy_default]
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8006/health"]
      interval: 60s
      timeout: 10s
      retries: 3
      start_period: 30s
    deploy:
      resources:
        limits: {cpus: '1.0', memory: 1024M}
        reservations: {cpus: '0.5', memory: 512M}
```

- [ ] **Step 3: Добавить Caddy block**

В `deploy/Caddyfile` добавить:

```
recorder.os.wookiee.shop {
    reverse_proxy telemost_recorder_api:8006
}
```

- [ ] **Step 4: Локальная сборка-проверка**

```bash
docker build -f deploy/Dockerfile.telemost_recorder_api -t telemost_recorder_api:latest .
docker images | grep telemost_recorder_api
```

Expected: image создан без ошибок.

- [ ] **Step 5: Деплой на сервер**

```bash
ssh timeweb "cd /home/danila/projects/wookiee && git pull && cd deploy && docker compose up -d --build telemost-recorder-api && sleep 5 && docker compose logs --tail=30 telemost-recorder-api"
ssh timeweb "docker exec telemost_recorder_api curl -s http://localhost:8006/health"
```

Expected: `{"status": "ok", "checks": {...}}`.

- [ ] **Step 6: Перезагрузить Caddy (если правил Caddyfile)**

```bash
ssh timeweb "docker exec n8n-docker-caddy-caddy-1 caddy reload --config /etc/caddy/Caddyfile"
```

- [ ] **Step 7: Запустить webhook setup**

```bash
ssh timeweb "docker exec telemost_recorder_api python scripts/telemost_setup_webhook.py --webhook-url https://recorder.os.wookiee.shop/telegram/webhook"
ssh timeweb "curl -s 'https://api.telegram.org/bot${TELEMOST_BOT_TOKEN}/getWebhookInfo' | python3 -m json.tool"
```

Expected: `url=https://recorder.os.wookiee.shop/telegram/webhook`, `pending_update_count=0`.

- [ ] **Step 8: Sync users из Bitrix (one-shot)**

```bash
ssh timeweb "docker exec telemost_recorder_api python -c 'import asyncio; from services.telemost_recorder_api.auth import sync_users_from_bitrix; print(asyncio.run(sync_users_from_bitrix()))'"
```

Expected: число синхронизированных пользователей > 0 (включая твой `telegram_id`).

- [ ] **Step 9: Commit**

```bash
git add deploy/Dockerfile.telemost_recorder_api deploy/docker-compose.yml deploy/Caddyfile
git commit -m "feat(telemost-api): Dockerfile + docker-compose service + Caddy + deploy runbook"
```

---

## Task 21: E2E Acceptance Test (manual)

**Files:**
- No new files; manual verification против live deploy.

- [ ] **Step 1: Открыть `@wookiee_recorder_bot` в Telegram**

Send `/start`. Expected: welcome-сообщение с твоим именем (значит auth-sync прошёл).

- [ ] **Step 2: `/help` — справка**

Expected: список команд.

- [ ] **Step 3: Создать тестовую встречу в Я.Телемост**

Открыть https://telemost.yandex.ru, создать встречу. Скопировать URL.

- [ ] **Step 4: Поставить запись в очередь**

Send `/record <url>`. Expected: «✅ Поставил в очередь. id `xxxxxxxx`. Пришлю summary в DM…».

- [ ] **Step 5: Проверить статус**

Send `/status`. Expected: запись в статусе `recording`.

- [ ] **Step 6: Зайти в встречу самому, говорить ~3 минуты**

Включить микрофон, сказать пару фраз про работу: имена, продукты, темы. Затем выйти.

- [ ] **Step 7: Подождать ~3-5 минут (короткая встреча → меньше chunks)**

Recorder должен detect_meeting_ended → exit. Worker подбирает раны postprocess.

- [ ] **Step 8: Проверить DM**

Expected:
- Текстовое сообщение с *summary* (участники, темы, решения, задачи) с `id` встречи
- Файл-аттач `transcript_xxxxxxxx.txt` с пара-форматом `[MM:SS] <speaker>: <text>`

- [ ] **Step 9: Проверить /list**

Send `/list`. Expected: запись в статусе `done` появилась в списке.

- [ ] **Step 10: Edge — пустая встреча**

Создать ещё одну встречу. Записать без речи (молча 2 минуты). Expected: «📭 Запись завершена, речи не было распознано.».

- [ ] **Step 11: Edge — невалидный URL**

Send `/record not-a-url`. Expected: «Это не похоже на ссылку Я.Телемоста…».

- [ ] **Step 12: Edge — concurrent uniqueness**

Send `/record <url>` дважды быстро. Expected: вторая команда → «Эта встреча уже в работе…».

- [ ] **Step 13: Edge — unknown user**

С другого Telegram-аккаунта (без записи в `telemost.users`) написать `/record <url>`. Expected: instructions про Bitrix24 → Telegram field.

- [ ] **Step 14: Проверить в БД**

```bash
ssh timeweb "docker exec telemost_recorder_api python -c \"
import asyncio, json
from services.telemost_recorder_api.db import get_pool
async def go():
    pool = await get_pool()
    async with pool.acquire() as c:
        rows = await c.fetch('SELECT id, status, title, duration_seconds, jsonb_array_length(processed_paragraphs) AS para_count, tags, notified_at FROM telemost.meetings ORDER BY created_at DESC LIMIT 5')
    for r in rows: print(dict(r))
asyncio.run(go())
\""
```

Expected: видно тестовые записи с заполненными `processed_paragraphs`, `summary`, `tags`, `notified_at`.

- [ ] **Step 15: Run финальный sweep тестов**

```bash
cd /Users/danilamatveev/Projects/Wookiee
pytest tests/services/telemost_recorder_api/ -v
```

Expected: все тесты PASS.

- [ ] **Step 16: Финальный commit + готовность к Phase 1**

Если все шаги выше прошли:

```bash
git status  # должно быть чисто
git log --oneline main..HEAD  # видна история Task 1-21
```

Phase 0 ready for review.

---

## Self-Review

**Spec coverage** (Phase 0 чек-лист из spec §11):
- ✅ Capacity check → Task 1
- ✅ Migrations 3 таблицы → Task 2
- ✅ FastAPI с /telegram/webhook + /health → Tasks 8, 9
- ✅ Команды /record /status /list /help /start → Tasks 10, 11, 12
- ✅ Auth-синк из Bitrix → Task 7
- ✅ URL канонизация (§15.1) → Task 5
- ✅ Worker-loop (1 параллельная) → Task 14
- ✅ LLM-постпроцессор single-call → Task 15
- ✅ Empty-meeting fallback (§15.4) → Task 16 (test `test_empty_segments_marks_done_without_llm`)
- ✅ Telegram DM с idempotent защитой (§15.7) → Task 17 (`_claim_notification`)
- ✅ Telegram message chunking (§15.5) → Task 6 (`tg_send_message` chunks > 4000)
- ✅ Recording timeouts (§15.3) → Task 14 (hard limit через `monitor_container(timeout=4h*3600)`)
- ✅ Audio upload (§15.6) → Task 18
- ✅ /list privacy scope (§15.8) → Task 12 (`triggered_by OR organizer_id OR invitees @>`)
- ✅ Аватарка для бота (§7.6) → Task 19
- ✅ Webhook setup runbook (§7.7) → Task 19 + Task 20 step 7

**Placeholder scan:** все шаги имеют конкретный код или конкретные команды. Нет «TBD», «implement later», «similar to Task N».

**Type consistency:**
- `meeting_id: UUID` везде
- `chat_id: int`, `user_id: int` (Telegram numeric ID)
- `signed_url: str`, `expires_at: datetime`
- Worker function `process_one() -> bool` — одинаково в recorder_worker и postprocess_worker
- `tg_send_message(chat_id, text)` сигнатура одинаковая везде

**Известные риски, флагируемые перед стартом:**
1. Существующий `scripts/telemost_record.py` принимает аргументы `--meeting-id` и `--output-dir`? Если нет — нужен мини-патч в Task 13. **Action:** перед Task 13 проверить `python scripts/telemost_record.py --help`. Если CLI не поддерживает — добавить argparse в `telemost_record.py` отдельным шагом 13.0.
2. `recorder.os.wookiee.shop` поддомен — wildcard `*.os` уже резолвится в DNS (см. memory `project_dns_subdomain_setup.md`), Caddy сам выдаст TLS. Если автоматический LE handshake не пройдёт — fallback на основной домен `os.wookiee.shop/recorder` через path-routing.
3. Поле Bitrix UF_USR_TELEGRAM может называться иначе на конкретном инстансе. Перед Task 7 проверить через `curl ${BITRIX24_WEBHOOK_URL}/user.fields.json | jq`.

---

## Execution Handoff

После того как пользователь утвердит план:

**1. Subagent-Driven (рекомендую)** — дispatch fresh subagent на каждую задачу через superpowers:subagent-driven-development. Между задачами: spec-review → code-review. Контекст оркестратора остаётся свободным.

**2. Inline Execution** — executing-plans, batch с checkpoints.

Phase 0 — 21 задача, ~6-8 часов суммарно. Phase 1/2 будут отдельными планами после смоук-теста на реальной встрече.


