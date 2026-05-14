# Telemost Recorder — UX & Bitrix Enrichment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Сделать DM-результат полезным (заголовок встречи из Bitrix-календаря, участники по именам, inline-кнопки действий) и убрать ключевые операционные боли — sequential ASR и нечитаемый `/list`.

**Architecture:** 4 параллельных направления — (1) асинхронная ASR через `asyncio.gather` с ограничением по семафору, (2) on-demand обогащение `telemost.meetings.title/invitees` из Bitrix `calendar.event.get` по запуску записи, (3) inline-клавиатуры на `/list` и DM (1 кнопка на встречу + блок действий "Транскрипт / Сводка / Удалить"), (4) callback-роутер `meet:<uuid>:<action>` с тонкими handlers.

**Tech Stack:** Python 3.11, asyncio + httpx (async Bitrix REST), asyncpg, Telegram Bot API (callback_query + inline_keyboard), Yandex SpeechKit v1 sync (с pooled httpx + bounded semaphore), pytest-asyncio.

---

## CTO + DevOps Critique (snapshot 2026-05-11)

**Что болит в проде прямо сейчас:**

1. **ASR — главный bottleneck throughput.** [services/telemost_recorder/transcribe.py:61-100](services/telemost_recorder/transcribe.py#L61-L100) гонит чанки строго последовательно: `while offset < duration` → `subprocess.run(ffmpeg)` → `requests.post(SpeechKit)` → `time.sleep(0.1)`. На 90-минутной записи это ≈216 чанков по 25 с × ~2 с каждый = **~7 минут чистой CPU/network walltime в идеале, реально 20–30 мин** из-за blocking sync. Это не масштабируется: одна параллельная встреча + один recovery скрипт = час простоя. Фикс: `asyncio.gather` через bounded semaphore (8–16), httpx async, ffmpeg тоже асинхронно. Цель — **1h аудио → ≤2 мин ASR**.

2. **DM пуст по смыслу.** [services/telemost_recorder_api/notifier.py:57-109](services/telemost_recorder_api/notifier.py#L57-L109) формирует summary, но: `title` всегда "(без названия)" потому что [services/telemost_recorder_api/migrations/001_schema_users_meetings.sql:23](services/telemost_recorder_api/migrations/001_schema_users_meetings.sql#L23) никем не пишется при `/record` URL. `invitees` всегда `'[]'`. В LLM-prompt не передаётся реальный roster — speakers остаются `Speaker 0/1/2`. У DM нет ни одной inline-кнопки. Фикс: при запуске записи бот ищет Bitrix-событие по `meeting_url` через `calendar.event.get`, забирает `NAME`, `ATTENDEES_CODES` → пишет в `meetings.title` + `meetings.invitees`. LLM получает имена → speakers получают атрибуцию.

3. **`/list` — мёртвая стена текста.** [services/telemost_recorder_api/handlers/list_meetings.py:42-43](services/telemost_recorder_api/handlers/list_meetings.py#L42-L43) строит `\n`.join без `reply_markup`. ID встречи в backticks — копируется руками, нет действий. Фикс: каждая строка → одна inline-кнопка `📝 Title (date) · 18 мин` → `callback_data="meet:<uuid8>:show"`. Реакция: либо отдельный DM с summary + action keyboard, либо edit_message с раскрытием.

4. **Нет per-meeting действий.** В [services/telemost_recorder_api/handlers/__init__.py:109-116](services/telemost_recorder_api/handlers/__init__.py#L109-L116) callback-router знает только `menu:list / menu:status / menu:help`. Нельзя ни запросить транскрипт, ни удалить старую запись, ни перепослать summary. Фикс: новый namespace `meet:<uuid8>:<action>` где action ∈ {`show`, `transcript`, `summary`, `delete`, `confirm_delete`}.

5. **DevOps: тестовый цикл слишком длинный.** Сейчас "позвонил 90 минут → жди 30 мин ASR → читай DM" = 2-часовая итерация на один баг. Это в 30 раз медленнее, чем нужно для отладки UX. Фикс: dev-loop test rig — один длинный созвон + cron/скрипт перезапускает recorder каждые N минут на фиксированном URL. После ASR-фикса итерация уже становится ~5 мин, rig делает 10 циклов/час реалистичными.

6. **Observability gap.** В логах нет таймингов по фазам (record → upload → ASR → LLM → notify). Нельзя ответить "где висим 20 минут". Это не блочит фичи, но точно надо после ASR-рефакторинга — добавим `logger.info` со временем каждой фазы + сохранение в `meetings.metrics` (JSON: `{record_ms, asr_ms, llm_ms, notify_ms}`).

7. **Безопасность delete.** Удаление встречи через inline-кнопку = опасная операция (Postgres row + Supabase Storage signed URL + локальный артефакт). Обязательно two-step confirm: первая кнопка → новое сообщение "точно удалить?", вторая кнопка → реальный delete. Никаких прямых `meet:<uuid>:delete` без подтверждения.

**Что НЕ трогаем в этом плане (явный YAGNI):**
- Многоязычный summary (RU достаточно).
- Diarization speakers (отдельная задача, нужен другой ASR-провайдер).
- Группы и broadcast в общий чат (Phase 1 фичи).
- `/transcript`, `/summary` как отдельные slash-команды — inline-кнопок хватает.
- Уведомления в Bitrix (через 2 недели может появиться отдельная задача).

---

## File Structure

**Create:**
- `services/telemost_recorder_api/bitrix_calendar.py` — async-клиент `calendar.event.get` + поиск события по `meeting_url`.
- `services/telemost_recorder_api/handlers/meeting_actions.py` — callback-handlers `meet:<uuid8>:<action>`.
- `services/telemost_recorder_api/meetings_repo.py` — helpers для загрузки встречи по prefix-id, удаления, transcript-render (вынесем из `notifier.py` для переиспользования).
- `services/telemost_recorder_api/migrations/003_meeting_metrics.sql` — добавить `metrics jsonb` для phase timings.
- `scripts/telemost_dev_loop.sh` — dev-loop test rig (cron-friendly).
- `tests/services/telemost_recorder/test_transcribe_async.py`
- `tests/services/telemost_recorder_api/test_bitrix_calendar.py`
- `tests/services/telemost_recorder_api/test_meeting_actions.py`
- `tests/services/telemost_recorder_api/test_meetings_repo.py`

**Modify:**
- `services/telemost_recorder/transcribe.py` — async-рефакторинг с bounded semaphore.
- `services/telemost_recorder_api/handlers/list_meetings.py` — inline-клавиатура per row.
- `services/telemost_recorder_api/handlers/__init__.py` — роутер `meet:` namespace.
- `services/telemost_recorder_api/notifier.py` — attach action keyboard, вынести transcript-builder.
- `services/telemost_recorder_api/keyboards.py` — фабрики `list_row_button`, `meeting_actions`, `confirm_delete`.
- `services/telemost_recorder_api/handlers/record.py` — после INSERT в `telemost.meetings` дёрнуть Bitrix-enrichment.
- `services/telemost_recorder_api/llm_postprocess.py` — передавать `invitees` в LLM-prompt для атрибуции speakers.

**Test:** все тестовые пути — pytest, мок httpx/asyncpg.

---

### Task 1: Async ASR — refactor `transcribe.py` (parallel chunks)

**Files:**
- Modify: `services/telemost_recorder/transcribe.py`
- Test: `tests/services/telemost_recorder/test_transcribe_async.py`

**Context:** Текущая реализация — sync, sequential, не масштабируется. Делаем `transcribe_audio_async(audio_path)`, который через `asyncio.gather` параллелит чанки, ограничиваясь `_ASR_PARALLEL = 8` через `asyncio.Semaphore`. ffmpeg извлекает все чанки одной операцией через `-f segment -segment_time 25`, чтобы не плодить subprocess'ы. SpeechKit вызывается через `httpx.AsyncClient` с переиспользуемым connection pool. Sync wrapper `transcribe_audio(audio_path)` остаётся для обратной совместимости и теперь просто `return asyncio.run(transcribe_audio_async(audio_path))`.

- [ ] **Step 1: Написать failing test для async-сегментации**

Создать `tests/services/telemost_recorder/test_transcribe_async.py`:

```python
"""Async ASR — параллельные чанки + сохранение порядка по offset_ms."""
from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import patch, AsyncMock

import pytest

from services.telemost_recorder.transcribe import (
    TranscriptSegment,
    transcribe_audio_async,
)


@pytest.mark.asyncio
async def test_async_chunks_preserved_in_order(tmp_path: Path):
    audio = tmp_path / "audio.opus"
    audio.write_bytes(b"x")  # ffmpeg stub will not read

    async def fake_split(_path, chunk_secs):
        return [
            (0, b"a"),
            (25000, b"b"),
            (50000, b"c"),
        ]

    async def fake_transcribe(_bytes, offset_ms):
        await asyncio.sleep(0.01)
        return TranscriptSegment(
            speaker="Speaker 0",
            start_ms=offset_ms,
            end_ms=offset_ms + 25000,
            text=f"text-{offset_ms}",
        )

    with patch(
        "services.telemost_recorder.transcribe._split_into_chunks_async",
        AsyncMock(side_effect=fake_split),
    ), patch(
        "services.telemost_recorder.transcribe._transcribe_chunk_async",
        AsyncMock(side_effect=fake_transcribe),
    ):
        segments = await transcribe_audio_async(audio)

    assert [s.start_ms for s in segments] == [0, 25000, 50000]
    assert [s.text for s in segments] == ["text-0", "text-25000", "text-50000"]


@pytest.mark.asyncio
async def test_async_semaphore_limits_concurrency(tmp_path: Path, monkeypatch):
    audio = tmp_path / "audio.opus"
    audio.write_bytes(b"x")

    monkeypatch.setattr(
        "services.telemost_recorder.transcribe._ASR_PARALLEL", 2
    )

    in_flight = 0
    max_in_flight = 0

    async def fake_split(_path, chunk_secs):
        return [(i * 25000, b"x") for i in range(10)]

    async def fake_transcribe(_bytes, offset_ms):
        nonlocal in_flight, max_in_flight
        in_flight += 1
        max_in_flight = max(max_in_flight, in_flight)
        await asyncio.sleep(0.02)
        in_flight -= 1
        return TranscriptSegment("Speaker 0", offset_ms, offset_ms + 25000, "ok")

    with patch(
        "services.telemost_recorder.transcribe._split_into_chunks_async",
        AsyncMock(side_effect=fake_split),
    ), patch(
        "services.telemost_recorder.transcribe._transcribe_chunk_async",
        AsyncMock(side_effect=fake_transcribe),
    ):
        await transcribe_audio_async(audio)

    assert max_in_flight <= 2


@pytest.mark.asyncio
async def test_async_skips_empty_chunks(tmp_path: Path):
    audio = tmp_path / "audio.opus"
    audio.write_bytes(b"x")

    async def fake_split(_path, chunk_secs):
        return [(0, b"a"), (25000, b"b")]

    async def fake_transcribe(_bytes, offset_ms):
        if offset_ms == 0:
            return None  # silence chunk → SpeechKit returned empty text
        return TranscriptSegment("Speaker 0", offset_ms, offset_ms + 25000, "ok")

    with patch(
        "services.telemost_recorder.transcribe._split_into_chunks_async",
        AsyncMock(side_effect=fake_split),
    ), patch(
        "services.telemost_recorder.transcribe._transcribe_chunk_async",
        AsyncMock(side_effect=fake_transcribe),
    ):
        segments = await transcribe_audio_async(audio)
    assert len(segments) == 1
    assert segments[0].start_ms == 25000
```

- [ ] **Step 2: Запустить — должно упасть с ImportError**

Run: `pytest tests/services/telemost_recorder/test_transcribe_async.py -v`
Expected: FAIL — `ImportError: cannot import name 'transcribe_audio_async'`

- [ ] **Step 3: Реализовать async-вариант в `services/telemost_recorder/transcribe.py`**

Заменить файл целиком:

```python
"""SpeechKit v1 sync REST — параллельная транскрибация через asyncio.

Sequential pipeline на 1h аудио = ~10 мин walltime. Async + semaphore (8)
сокращает до ~1 мин на той же оплате (SpeechKit чарджит за длительность,
не за количество запросов).
"""
from __future__ import annotations

import asyncio
import logging
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import httpx

from services.telemost_recorder.config import SPEECHKIT_API_KEY, YANDEX_FOLDER_ID

logger = logging.getLogger(__name__)

_SYNC_URL = "https://stt.api.cloud.yandex.net/speech/v1/stt:recognize"
_CHUNK_SECS = 25
_ASR_PARALLEL = 8
_HTTP_TIMEOUT = 60.0


@dataclass
class TranscriptSegment:
    speaker: str
    start_ms: int
    end_ms: int
    text: str


async def _get_duration_async(audio_path: Path) -> float:
    proc = await asyncio.create_subprocess_exec(
        "ffprobe", "-v", "quiet",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(audio_path),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await proc.communicate()
    return float(stdout.decode().strip())


async def _split_into_chunks_async(
    audio_path: Path,
    chunk_secs: int,
) -> list[tuple[int, bytes]]:
    """Split audio into Opus chunks in one ffmpeg pass via -f segment.

    Returns [(offset_ms, opus_bytes), ...] in offset order.
    """
    duration = await _get_duration_async(audio_path)
    tmp_dir = Path(tempfile.mkdtemp(prefix="tmasr-"))
    try:
        pattern = tmp_dir / "chunk_%04d.ogg"
        proc = await asyncio.create_subprocess_exec(
            "ffmpeg", "-y",
            "-i", str(audio_path),
            "-f", "segment",
            "-segment_time", str(chunk_secs),
            "-c:a", "libopus",
            "-b:a", "64k",
            "-ar", "48000",
            "-ac", "1",
            "-reset_timestamps", "1",
            str(pattern),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, err = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(f"ffmpeg split failed: {err.decode()[:500]}")

        chunks: list[tuple[int, bytes]] = []
        for i, f in enumerate(sorted(tmp_dir.glob("chunk_*.ogg"))):
            offset_ms = i * chunk_secs * 1000
            if offset_ms >= duration * 1000:
                break
            chunks.append((offset_ms, f.read_bytes()))
        return chunks
    finally:
        for f in tmp_dir.glob("*"):
            try:
                f.unlink()
            except OSError:
                pass
        try:
            tmp_dir.rmdir()
        except OSError:
            pass


async def _transcribe_chunk_async(
    chunk_bytes: bytes,
    offset_ms: int,
    client: httpx.AsyncClient | None = None,
) -> Optional[TranscriptSegment]:
    headers = {
        "Authorization": f"Api-Key {SPEECHKIT_API_KEY}",
        "x-folder-id": YANDEX_FOLDER_ID,
    }
    params = {"lang": "ru-RU", "format": "oggopus", "sampleRateHertz": "48000"}

    async def _do(c: httpx.AsyncClient) -> Optional[TranscriptSegment]:
        resp = await c.post(_SYNC_URL, headers=headers, params=params, content=chunk_bytes)
        if not resp.is_success:
            logger.warning(
                "SpeechKit chunk %dms failed: %d %s",
                offset_ms, resp.status_code, resp.text[:200],
            )
            return None
        data = resp.json()
        text = data.get("result", "").strip()
        if not text:
            return None
        return TranscriptSegment(
            speaker="Speaker 0",
            start_ms=offset_ms,
            end_ms=offset_ms + _CHUNK_SECS * 1000,
            text=text,
        )

    if client is not None:
        return await _do(client)
    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as c:
        return await _do(c)


async def transcribe_audio_async(audio_path: Path) -> list[TranscriptSegment]:
    """Parallel SpeechKit calls bounded by _ASR_PARALLEL."""
    chunks = await _split_into_chunks_async(audio_path, _CHUNK_SECS)
    if not chunks:
        return []

    sem = asyncio.Semaphore(_ASR_PARALLEL)

    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
        async def _bounded(chunk: bytes, offset_ms: int) -> Optional[TranscriptSegment]:
            async with sem:
                return await _transcribe_chunk_async(chunk, offset_ms, client=client)

        results = await asyncio.gather(*(_bounded(b, o) for o, b in chunks))

    return [r for r in results if r is not None]


def transcribe_audio(audio_path: Path) -> list[TranscriptSegment]:
    """Sync wrapper kept for the recorder container's main entrypoint."""
    return asyncio.run(transcribe_audio_async(audio_path))
```

- [ ] **Step 4: Запустить тесты — должны пройти**

Run: `pytest tests/services/telemost_recorder/test_transcribe_async.py -v`
Expected: PASS все 3 теста.

- [ ] **Step 5: Также убедиться, что старые тесты (если есть) не сломались**

Run: `pytest tests/services/telemost_recorder/ -v`
Expected: PASS (только новые тесты + старые `test_participants_filter.py`).

- [ ] **Step 6: Commit**

```bash
git add services/telemost_recorder/transcribe.py tests/services/telemost_recorder/test_transcribe_async.py
git commit -m "perf(telemost): async parallel ASR (bounded semaphore=8, single ffmpeg split)"
```

---

### Task 2: Bitrix calendar enrichment — async client + meeting writer

**Files:**
- Create: `services/telemost_recorder_api/bitrix_calendar.py`
- Test: `tests/services/telemost_recorder_api/test_bitrix_calendar.py`

**Context:** Bitrix-вебхук в `.env` — `Bitrix_rest_api`. Метод `calendar.event.get?type=user&ownerId=<bitrix_id>&from=...&to=...` возвращает события пользователя в диапазоне. Ищем событие с `LOCATION` или `DESCRIPTION` содержащим `meeting_url`. Возвращаем `(title, [attendee_telegram_ids])`. Делать ровно по одному запросу для `triggered_by` (того, кто запустил `/record`) с окном ±2 часа от `now()`.

- [ ] **Step 1: Failing test**

Создать `tests/services/telemost_recorder_api/test_bitrix_calendar.py`:

```python
"""Bitrix calendar lookup by meeting_url."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from services.telemost_recorder_api.bitrix_calendar import (
    find_event_by_url,
    enrich_meeting_from_bitrix,
)


@pytest.mark.asyncio
async def test_find_event_by_url_matches_in_location():
    url = "https://telemost.360.yandex.ru/j/abc"
    fake_resp = httpx.Response(
        200,
        json={
            "result": [
                {
                    "NAME": "Sync с командой",
                    "LOCATION": url,
                    "DATE_FROM": "2026-05-12T10:00:00+03:00",
                    "ATTENDEES_CODES": ["U1", "U42"],
                },
                {
                    "NAME": "Другая встреча",
                    "LOCATION": "https://example.com",
                    "ATTENDEES_CODES": ["U7"],
                },
            ]
        },
    )
    with patch("httpx.AsyncClient.get", AsyncMock(return_value=fake_resp)):
        ev = await find_event_by_url(bitrix_user_id="42", meeting_url=url)
    assert ev["title"] == "Sync с командой"
    assert ev["bitrix_attendee_ids"] == [1, 42]


@pytest.mark.asyncio
async def test_find_event_by_url_matches_in_description():
    url = "https://telemost.360.yandex.ru/j/xyz"
    fake_resp = httpx.Response(
        200,
        json={
            "result": [
                {
                    "NAME": "Встреча",
                    "LOCATION": "",
                    "DESCRIPTION": f"Ссылка: {url}",
                    "ATTENDEES_CODES": ["U9"],
                }
            ]
        },
    )
    with patch("httpx.AsyncClient.get", AsyncMock(return_value=fake_resp)):
        ev = await find_event_by_url(bitrix_user_id="42", meeting_url=url)
    assert ev["title"] == "Встреча"


@pytest.mark.asyncio
async def test_find_event_by_url_no_match_returns_none():
    fake_resp = httpx.Response(200, json={"result": []})
    with patch("httpx.AsyncClient.get", AsyncMock(return_value=fake_resp)):
        ev = await find_event_by_url(
            bitrix_user_id="42",
            meeting_url="https://telemost.360.yandex.ru/j/nope",
        )
    assert ev is None


@pytest.mark.asyncio
async def test_enrich_meeting_resolves_attendees_to_telegram_ids():
    from uuid import uuid4
    meeting_id = uuid4()

    bitrix_event = {
        "title": "Daily",
        "bitrix_attendee_ids": [1, 42, 99],
        "scheduled_at": "2026-05-12T10:00:00+03:00",
        "source_event_id": "BX-EV-7",
    }

    async def fake_find(bitrix_user_id, meeting_url):
        return bitrix_event

    fake_pool = AsyncMock()
    fake_conn = AsyncMock()
    fake_conn.fetch.return_value = [
        {"telegram_id": 111, "name": "Иван Иванов", "bitrix_id": "1"},
        {"telegram_id": 222, "name": "Алина А.", "bitrix_id": "42"},
    ]
    fake_pool.acquire.return_value.__aenter__.return_value = fake_conn

    with patch(
        "services.telemost_recorder_api.bitrix_calendar.find_event_by_url",
        AsyncMock(side_effect=fake_find),
    ), patch(
        "services.telemost_recorder_api.bitrix_calendar.get_pool",
        AsyncMock(return_value=fake_pool),
    ):
        updated = await enrich_meeting_from_bitrix(
            meeting_id=meeting_id,
            meeting_url="https://telemost.360.yandex.ru/j/abc",
            triggered_by_bitrix_id="1",
        )

    assert updated is True
    fake_conn.execute.assert_called_once()
    args = fake_conn.execute.call_args.args
    assert "UPDATE telemost.meetings" in args[0]
    assert args[1] == "Daily"
    invitees_json = args[2]
    assert '"telegram_id": 111' in invitees_json
    assert '"telegram_id": 222' in invitees_json
    assert "Иван Иванов" in invitees_json


@pytest.mark.asyncio
async def test_enrich_meeting_no_event_returns_false():
    from uuid import uuid4
    with patch(
        "services.telemost_recorder_api.bitrix_calendar.find_event_by_url",
        AsyncMock(return_value=None),
    ):
        updated = await enrich_meeting_from_bitrix(
            meeting_id=uuid4(),
            meeting_url="https://telemost.360.yandex.ru/j/x",
            triggered_by_bitrix_id="1",
        )
    assert updated is False
```

- [ ] **Step 2: Запустить — упадёт**

Run: `pytest tests/services/telemost_recorder_api/test_bitrix_calendar.py -v`
Expected: FAIL — `ImportError`.

- [ ] **Step 3: Реализовать `bitrix_calendar.py`**

Создать `services/telemost_recorder_api/bitrix_calendar.py`:

```python
"""Bitrix24 calendar lookup — find a calendar event by meeting URL.

Used at /record-time to enrich telemost.meetings.title + invitees so the DM
shows a real subject and Bitrix-mapped participant list (rather than the
generic "(без названия)" + Speaker 0/1/2).
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import UUID

import httpx

from services.telemost_recorder_api.config import BITRIX24_WEBHOOK_URL
from services.telemost_recorder_api.db import get_pool

logger = logging.getLogger(__name__)

_LOOKUP_WINDOW_HOURS = 4  # ±2 ч от now()
_HTTP_TIMEOUT = 15.0


def _extract_attendee_ids(codes: list[Any] | None) -> list[int]:
    out: list[int] = []
    for c in codes or []:
        if isinstance(c, str) and c.startswith("U"):
            try:
                out.append(int(c[1:]))
            except ValueError:
                continue
    return out


def _event_mentions_url(ev: dict, url: str) -> bool:
    haystacks = (
        str(ev.get("LOCATION") or ""),
        str(ev.get("DESCRIPTION") or ""),
        str(ev.get("NAME") or ""),
    )
    return any(url in h for h in haystacks)


async def find_event_by_url(
    bitrix_user_id: str,
    meeting_url: str,
    window_hours: int = _LOOKUP_WINDOW_HOURS,
) -> Optional[dict[str, Any]]:
    """Return normalized event dict matching meeting_url, or None."""
    now = datetime.now(timezone.utc)
    frm = (now - timedelta(hours=window_hours / 2)).strftime("%Y-%m-%dT%H:%M:%S")
    to = (now + timedelta(hours=window_hours / 2)).strftime("%Y-%m-%dT%H:%M:%S")
    base = BITRIX24_WEBHOOK_URL.rstrip("/")
    params = {"type": "user", "ownerId": bitrix_user_id, "from": frm, "to": to}

    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as c:
        resp = await c.get(f"{base}/calendar.event.get.json", params=params)

    if not resp.is_success:
        logger.warning("Bitrix calendar.event.get failed %d", resp.status_code)
        return None

    items = resp.json().get("result") or []
    if not isinstance(items, list):
        return None

    for ev in items:
        if _event_mentions_url(ev, meeting_url):
            return {
                "title": (ev.get("NAME") or "").strip() or None,
                "bitrix_attendee_ids": _extract_attendee_ids(
                    ev.get("ATTENDEES_CODES")
                ),
                "scheduled_at": ev.get("DATE_FROM"),
                "source_event_id": str(ev.get("ID")) if ev.get("ID") else None,
            }
    return None


async def enrich_meeting_from_bitrix(
    meeting_id: UUID,
    meeting_url: str,
    triggered_by_bitrix_id: str,
) -> bool:
    """Find Bitrix event by URL, write title + invitees into telemost.meetings.

    Returns True if a matching event was found and the row was updated.
    """
    ev = await find_event_by_url(
        bitrix_user_id=triggered_by_bitrix_id,
        meeting_url=meeting_url,
    )
    if not ev:
        return False

    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT telegram_id, name, bitrix_id
            FROM telemost.users
            WHERE bitrix_id = ANY($1::text[]) AND is_active = true
            """,
            [str(i) for i in ev["bitrix_attendee_ids"]],
        )
        invitees = [
            {"telegram_id": r["telegram_id"], "name": r["name"], "bitrix_id": r["bitrix_id"]}
            for r in rows
        ]
        await conn.execute(
            """
            UPDATE telemost.meetings
            SET title = $2,
                invitees = $3::jsonb,
                source_event_id = COALESCE(source_event_id, $4),
                scheduled_at = COALESCE(scheduled_at, $5::timestamptz)
            WHERE id = $1
            """,
            meeting_id,
            ev["title"],
            json.dumps(invitees, ensure_ascii=False),
            ev["source_event_id"],
            ev["scheduled_at"],
        )
    logger.info(
        "Enriched meeting %s: title=%r invitees=%d",
        meeting_id, ev["title"], len(invitees),
    )
    return True
```

- [ ] **Step 4: Запустить тесты — должны пройти**

Run: `pytest tests/services/telemost_recorder_api/test_bitrix_calendar.py -v`
Expected: PASS все 5.

- [ ] **Step 5: Подключить enrichment в `/record` handler**

В [services/telemost_recorder_api/handlers/record.py] (читаем сначала, чтобы не сломать существующее) — после успешного INSERT встречи добавить fire-and-forget вызов через `asyncio.create_task(enrich_meeting_from_bitrix(...))` так, чтобы DM "записываю..." уходил мгновенно, а title/invitees дописывались в фоне (до того, как recorder завершится — у нас минуты на это).

Найти место, где `INSERT INTO telemost.meetings` возвращает `id`, сразу после него добавить:

```python
import asyncio
from services.telemost_recorder_api.bitrix_calendar import enrich_meeting_from_bitrix

# user is the dict from get_user_by_telegram_id(...)
asyncio.create_task(
    enrich_meeting_from_bitrix(
        meeting_id=meeting_id,
        meeting_url=canonical_url,
        triggered_by_bitrix_id=user["bitrix_id"],
    )
)
```

- [ ] **Step 6: Smoke-import test**

Run: `python -c "from services.telemost_recorder_api.handlers.record import handle_record; print('ok')"`
Expected: `ok` без ImportError.

- [ ] **Step 7: Commit**

```bash
git add services/telemost_recorder_api/bitrix_calendar.py services/telemost_recorder_api/handlers/record.py tests/services/telemost_recorder_api/test_bitrix_calendar.py
git commit -m "feat(telemost): Bitrix calendar enrichment writes meetings.title + invitees"
```

---

### Task 3: LLM prompt — pass invitee names for speaker attribution

**Files:**
- Modify: `services/telemost_recorder_api/llm_postprocess.py`
- Test: `tests/services/telemost_recorder_api/test_llm_postprocess.py` (add a new test)

**Context:** Сейчас в prompt идут только сегменты `Speaker 0: ...`. LLM не знает, кто эти спикеры. После enrichment у нас есть `meetings.invitees` — JSON-array с `{"telegram_id", "name", "bitrix_id"}`. Передадим имена в prompt как hint: "Возможные участники: Иван Иванов, Алина А.". LLM в `processed_paragraphs` будет писать реальные имена вместо Speaker N, насколько сможет (если ни один сегмент не совпал — оставит Speaker 0). Это не строгая diarization, а лучший effort.

- [ ] **Step 1: Прочитать `llm_postprocess.py` (≈100 строк) и найти место, где формируется user-message**

Run: `wc -l services/telemost_recorder_api/llm_postprocess.py && head -120 services/telemost_recorder_api/llm_postprocess.py`
Expected: понять, где формируется `_render_inputs(segments)` и user-prompt.

- [ ] **Step 2: Failing test — invitee names появляются в user prompt**

В `tests/services/telemost_recorder_api/test_llm_postprocess.py` добавить тест:

```python
@pytest.mark.asyncio
async def test_prompt_includes_invitee_names():
    """invitees from meetings.invitees should be surfaced in the LLM prompt."""
    from services.telemost_recorder_api.llm_postprocess import process_segments

    sent = {}

    async def fake_post(self, url, **kwargs):
        sent["body"] = kwargs.get("json")
        import httpx as _h
        return _h.Response(200, json={
            "choices": [{"message": {"content": '{"summary":"x","tags":[],"participants":[],"topics":[],"decisions":[],"tasks":[],"processed_paragraphs":[]}'}}]
        })

    with patch("httpx.AsyncClient.post", new=fake_post):
        await process_segments(
            segments=[{"speaker": "Speaker 0", "start_ms": 0, "end_ms": 5000, "text": "Привет"}],
            invitees=[{"name": "Иван Иванов"}, {"name": "Алина А."}],
        )

    user_msg = next(
        m for m in sent["body"]["messages"] if m["role"] == "user"
    )["content"]
    assert "Иван Иванов" in user_msg
    assert "Алина А." in user_msg
```

- [ ] **Step 3: Реализовать — добавить параметр `invitees` в `process_segments(...)` и встроить блок в prompt**

В `llm_postprocess.py`:
- Расширить сигнатуру `process_segments(segments, *, invitees: list[dict] | None = None)`.
- В user-prompt перед сегментами добавить:
  ```
  Возможные участники встречи: <comma-separated names>.
  Атрибутируй реплики реальным именам там, где это уверенно следует из контекста. Иначе оставь Speaker N.
  ```
- В местах, где `process_segments` вызывается из `postprocess_worker.py`, прокинуть `invitees` — берём из загруженной строки `meetings.invitees` (JSON-decoded list of dicts).

- [ ] **Step 4: Тесты**

Run: `pytest tests/services/telemost_recorder_api/test_llm_postprocess.py -v`
Expected: PASS (включая старые и новый).

- [ ] **Step 5: Commit**

```bash
git add services/telemost_recorder_api/llm_postprocess.py services/telemost_recorder_api/workers/postprocess_worker.py tests/services/telemost_recorder_api/test_llm_postprocess.py
git commit -m "feat(telemost): pass invitees to LLM for speaker name attribution"
```

---

### Task 4: meetings_repo — общая работа с встречами (загрузка, удаление, transcript-render)

**Files:**
- Create: `services/telemost_recorder_api/meetings_repo.py`
- Test: `tests/services/telemost_recorder_api/test_meetings_repo.py`

**Context:** Нужно три операции, переиспользуемые в нескольких handlers: (1) `load_meeting_by_short_id(prefix8, owner_telegram_id)` — поиск встречи по 8-символьному префиксу UUID с проверкой, что owner = triggered_by/organizer/invitee, (2) `build_transcript_text(paragraphs)` — уже есть в `notifier.py`, выносим как pure-функцию, (3) `delete_meeting_for_owner(meeting_id, owner_telegram_id)` — soft + hard delete: помечаем row как deleted_at + чистим Supabase Storage. Возвращаем `True/False`. Запрещаем удаление активных (`recording`, `postprocessing`).

Также нужна миграция: добавить `deleted_at timestamptz` в `telemost.meetings`.

- [ ] **Step 1: Failing test (мокаем pool)**

`tests/services/telemost_recorder_api/test_meetings_repo.py`:

```python
"""Repo helpers: load by short id, delete with ownership check, transcript text."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from services.telemost_recorder_api.meetings_repo import (
    build_transcript_text,
    delete_meeting_for_owner,
    load_meeting_by_short_id,
)


@pytest.mark.asyncio
async def test_load_by_short_id_returns_row_if_owner_matches():
    mid = uuid4()
    row = {"id": mid, "title": "X", "triggered_by": 111, "status": "done"}

    fake_pool = AsyncMock()
    fake_conn = AsyncMock()
    fake_conn.fetchrow.return_value = row
    fake_pool.acquire.return_value.__aenter__.return_value = fake_conn

    with patch(
        "services.telemost_recorder_api.meetings_repo.get_pool",
        AsyncMock(return_value=fake_pool),
    ):
        got = await load_meeting_by_short_id(str(mid)[:8], owner_telegram_id=111)
    assert got["id"] == mid


@pytest.mark.asyncio
async def test_load_by_short_id_returns_none_if_not_found():
    fake_pool = AsyncMock()
    fake_conn = AsyncMock()
    fake_conn.fetchrow.return_value = None
    fake_pool.acquire.return_value.__aenter__.return_value = fake_conn
    with patch(
        "services.telemost_recorder_api.meetings_repo.get_pool",
        AsyncMock(return_value=fake_pool),
    ):
        got = await load_meeting_by_short_id("00000000", owner_telegram_id=111)
    assert got is None


@pytest.mark.asyncio
async def test_delete_meeting_blocks_when_active():
    mid = uuid4()
    fake_pool = AsyncMock()
    fake_conn = AsyncMock()
    fake_conn.fetchrow.return_value = {
        "id": mid, "status": "recording", "triggered_by": 111,
    }
    fake_pool.acquire.return_value.__aenter__.return_value = fake_conn
    with patch(
        "services.telemost_recorder_api.meetings_repo.get_pool",
        AsyncMock(return_value=fake_pool),
    ):
        ok = await delete_meeting_for_owner(mid, owner_telegram_id=111)
    assert ok is False


@pytest.mark.asyncio
async def test_delete_meeting_succeeds_when_done():
    mid = uuid4()
    fake_pool = AsyncMock()
    fake_conn = AsyncMock()
    fake_conn.fetchrow.return_value = {
        "id": mid, "status": "done", "triggered_by": 111,
    }
    fake_pool.acquire.return_value.__aenter__.return_value = fake_conn
    with patch(
        "services.telemost_recorder_api.meetings_repo.get_pool",
        AsyncMock(return_value=fake_pool),
    ):
        ok = await delete_meeting_for_owner(mid, owner_telegram_id=111)
    assert ok is True
    fake_conn.execute.assert_called_once()
    sql = fake_conn.execute.call_args.args[0]
    assert "deleted_at" in sql


def test_build_transcript_text_renders():
    text = build_transcript_text([
        {"start_ms": 0, "speaker": "Иван", "text": "Привет"},
        {"start_ms": 65000, "speaker": "Алина", "text": "Хай"},
    ])
    assert "[00:00] Иван: Привет" in text
    assert "[01:05] Алина: Хай" in text


def test_build_transcript_text_empty():
    assert build_transcript_text([]) == "(пустой transcript)"
```

- [ ] **Step 2: Запустить — упадёт**

Run: `pytest tests/services/telemost_recorder_api/test_meetings_repo.py -v`
Expected: FAIL — ImportError.

- [ ] **Step 3: Создать миграцию `003_meeting_deleted_at.sql`**

Файл `services/telemost_recorder_api/migrations/003_meeting_deleted_at.sql`:

```sql
-- 003_meeting_deleted_at.sql
ALTER TABLE telemost.meetings
    ADD COLUMN deleted_at timestamptz;

CREATE INDEX idx_meetings_not_deleted
    ON telemost.meetings(triggered_by)
    WHERE deleted_at IS NULL;
```

- [ ] **Step 4: Реализовать `meetings_repo.py`**

```python
"""Repository helpers: load, delete, transcript render."""
from __future__ import annotations

import json
import logging
from typing import Any, Optional
from uuid import UUID

from services.telemost_recorder_api.db import get_pool

logger = logging.getLogger(__name__)

_ID_PREFIX_LEN = 8
_BLOCK_STATUSES = {"queued", "recording", "postprocessing"}


def _ms_to_mmss(ms: int) -> str:
    s = ms // 1000
    return f"{s // 60:02d}:{s % 60:02d}"


def build_transcript_text(paragraphs: list[dict[str, Any]]) -> str:
    if not paragraphs:
        return "(пустой transcript)"
    out = []
    for p in paragraphs:
        ts = _ms_to_mmss(p.get("start_ms", 0))
        speaker = p.get("speaker", "?")
        text = p.get("text", "")
        out.append(f"[{ts}] {speaker}: {text}")
    return "\n".join(out)


async def load_meeting_by_short_id(
    short_id: str,
    owner_telegram_id: int,
) -> Optional[dict[str, Any]]:
    """Find a non-deleted meeting whose UUID starts with short_id AND user is owner/invitee."""
    if not short_id or len(short_id) < 4:
        return None
    pool = await get_pool()
    invitee_filter = json.dumps([{"telegram_id": owner_telegram_id}])
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, title, triggered_by, organizer_id, status, started_at,
                   duration_seconds, summary, tags, processed_paragraphs, error,
                   invitees, deleted_at
            FROM telemost.meetings
            WHERE deleted_at IS NULL
              AND id::text LIKE $1 || '%'
              AND (
                triggered_by = $2
                OR organizer_id = $2
                OR invitees @> $3::jsonb
              )
            LIMIT 1
            """,
            short_id,
            owner_telegram_id,
            invitee_filter,
        )
    if not row:
        return None
    out = dict(row)
    for k in ("summary", "processed_paragraphs", "invitees"):
        if isinstance(out.get(k), str):
            out[k] = json.loads(out[k])
    return out


async def delete_meeting_for_owner(
    meeting_id: UUID,
    owner_telegram_id: int,
) -> bool:
    """Soft-delete (deleted_at=now()) iff owner matches and status not in active set."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, status, triggered_by
            FROM telemost.meetings
            WHERE id = $1 AND deleted_at IS NULL AND triggered_by = $2
            """,
            meeting_id,
            owner_telegram_id,
        )
        if not row:
            return False
        if row["status"] in _BLOCK_STATUSES:
            return False
        await conn.execute(
            "UPDATE telemost.meetings SET deleted_at = now() WHERE id = $1",
            meeting_id,
        )
    logger.info("Soft-deleted meeting %s by user %s", meeting_id, owner_telegram_id)
    return True
```

- [ ] **Step 5: Запустить тесты**

Run: `pytest tests/services/telemost_recorder_api/test_meetings_repo.py -v`
Expected: PASS все 6.

- [ ] **Step 6: Применить миграцию на проде** (после merge)

Этот шаг — **только заметка**, миграция применяется через стандартный путь Supabase MCP / asyncpg-runner. **Не выполнять в этой задаче — запустим вручную после merge.**

- [ ] **Step 7: Commit**

```bash
git add services/telemost_recorder_api/meetings_repo.py services/telemost_recorder_api/migrations/003_meeting_deleted_at.sql tests/services/telemost_recorder_api/test_meetings_repo.py
git commit -m "feat(telemost): meetings_repo helpers + soft-delete column (migration 003)"
```

---

### Task 5: Keyboards — inline buttons per meeting

**Files:**
- Modify: `services/telemost_recorder_api/keyboards.py`
- Test: `tests/services/telemost_recorder_api/test_keyboards.py`

**Context:** Нужны 3 новые фабрики: `list_row_button(meeting)` — одна кнопка с заголовком встречи и датой → callback `meet:<short_id>:show`. `meeting_actions(short_id)` — клавиатура с 3 кнопками "📄 Транскрипт / 🧾 Сводка / 🗑 Удалить". `confirm_delete(short_id)` — клавиатура с двумя кнопками "✅ Да, удалить / ↩ Отмена".

- [ ] **Step 1: Failing test**

Создать `tests/services/telemost_recorder_api/test_keyboards.py`:

```python
"""Inline keyboard factories for per-meeting actions."""
from __future__ import annotations

from services.telemost_recorder_api.keyboards import (
    confirm_delete,
    list_row_button,
    meeting_actions,
)


def test_list_row_button_contains_callback():
    btn = list_row_button(short_id="abcdef12", title="Daily sync", when_str="12.05 10:00")
    assert btn["text"].startswith("✅") or "📝" in btn["text"]
    assert "Daily sync" in btn["text"]
    assert "12.05 10:00" in btn["text"]
    assert btn["callback_data"] == "meet:abcdef12:show"


def test_meeting_actions_has_3_buttons():
    kb = meeting_actions(short_id="abcdef12")
    flat = [b for row in kb["inline_keyboard"] for b in row]
    cbs = [b["callback_data"] for b in flat]
    assert "meet:abcdef12:transcript" in cbs
    assert "meet:abcdef12:summary" in cbs
    assert "meet:abcdef12:delete" in cbs


def test_confirm_delete_has_yes_and_no():
    kb = confirm_delete(short_id="abcdef12")
    flat = [b for row in kb["inline_keyboard"] for b in row]
    cbs = [b["callback_data"] for b in flat]
    assert "meet:abcdef12:confirm_delete" in cbs
    assert "meet:abcdef12:show" in cbs  # cancel returns to show
```

- [ ] **Step 2: Запустить — упадёт**

Run: `pytest tests/services/telemost_recorder_api/test_keyboards.py -v`
Expected: FAIL — ImportError.

- [ ] **Step 3: Расширить `keyboards.py`**

Добавить в конец `services/telemost_recorder_api/keyboards.py`:

```python
def list_row_button(short_id: str, title: str, when_str: str) -> dict:
    """One row's button: '📝 Title (date)' → meet:<id>:show."""
    label = f"📝 {title} ({when_str})"
    if len(label) > 64:
        label = label[:61] + "..."
    return {"text": label, "callback_data": f"meet:{short_id}:show"}


def meeting_actions(short_id: str) -> dict:
    return {
        "inline_keyboard": [
            [
                {"text": "📄 Транскрипт", "callback_data": f"meet:{short_id}:transcript"},
                {"text": "🧾 Сводка", "callback_data": f"meet:{short_id}:summary"},
            ],
            [{"text": "🗑 Удалить", "callback_data": f"meet:{short_id}:delete"}],
        ]
    }


def confirm_delete(short_id: str) -> dict:
    return {
        "inline_keyboard": [
            [
                {"text": "✅ Да, удалить", "callback_data": f"meet:{short_id}:confirm_delete"},
                {"text": "↩ Отмена", "callback_data": f"meet:{short_id}:show"},
            ]
        ]
    }
```

- [ ] **Step 4: Тесты**

Run: `pytest tests/services/telemost_recorder_api/test_keyboards.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add services/telemost_recorder_api/keyboards.py tests/services/telemost_recorder_api/test_keyboards.py
git commit -m "feat(telemost): inline keyboard factories for /list rows + meeting actions"
```

---

### Task 6: `/list` — inline buttons per meeting

**Files:**
- Modify: `services/telemost_recorder_api/handlers/list_meetings.py`
- Test: `tests/services/telemost_recorder_api/test_handle_list.py`

**Context:** Заменить plain-text стенку на одну кнопку на встречу. Header сверху — "📋 Последние 10 встреч". Каждая встреча = одна row с одной кнопкой. Тап → callback `meet:<short_id>:show`.

- [ ] **Step 1: Failing test**

Создать `tests/services/telemost_recorder_api/test_handle_list.py`:

```python
"""/list builds inline keyboard, one button per meeting."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from services.telemost_recorder_api.handlers.list_meetings import handle_list


@pytest.mark.asyncio
async def test_list_renders_one_button_per_meeting():
    mid1, mid2 = uuid4(), uuid4()
    fake_pool = AsyncMock()
    fake_conn = AsyncMock()
    fake_conn.fetch.return_value = [
        {"id": mid1, "status": "done", "title": "Sync 1",
         "started_at": datetime(2026, 5, 11, 10, 0, tzinfo=timezone.utc)},
        {"id": mid2, "status": "failed", "title": "Sync 2",
         "started_at": datetime(2026, 5, 10, 9, 0, tzinfo=timezone.utc)},
    ]
    fake_pool.acquire.return_value.__aenter__.return_value = fake_conn

    sent = []

    async def fake_send(chat_id, text, *, reply_markup=None, **_):
        sent.append({"text": text, "reply_markup": reply_markup})

    with patch(
        "services.telemost_recorder_api.handlers.list_meetings.get_pool",
        AsyncMock(return_value=fake_pool),
    ), patch(
        "services.telemost_recorder_api.handlers.list_meetings.get_user_by_telegram_id",
        AsyncMock(return_value={"telegram_id": 111}),
    ), patch(
        "services.telemost_recorder_api.handlers.list_meetings.tg_send_message",
        AsyncMock(side_effect=fake_send),
    ):
        await handle_list(chat_id=999, user_id=111)

    assert len(sent) == 1
    kb = sent[0]["reply_markup"]
    assert kb is not None
    rows = kb["inline_keyboard"]
    assert len(rows) == 2
    cbs = [rows[0][0]["callback_data"], rows[1][0]["callback_data"]]
    assert cbs[0] == f"meet:{str(mid1)[:8]}:show"
    assert cbs[1] == f"meet:{str(mid2)[:8]}:show"
```

- [ ] **Step 2: Запустить — упадёт (no reply_markup attached)**

Run: `pytest tests/services/telemost_recorder_api/test_handle_list.py -v`
Expected: FAIL — `kb is None`.

- [ ] **Step 3: Переписать `handle_list`**

```python
"""/list — последние 10 встреч с твоим участием (privacy scope §15.8)."""
from __future__ import annotations

import json

from services.telemost_recorder_api.auth import get_user_by_telegram_id
from services.telemost_recorder_api.db import get_pool
from services.telemost_recorder_api.keyboards import list_row_button
from services.telemost_recorder_api.telegram_client import tg_send_message

_EMPTY = (
    "📭 *Не нашёл ни одной твоей встречи*\n\n"
    "Пришли мне ссылку на Я.Телемост или /help для справки."
)
_HEADER = "📋 *Последние 10 встреч*\n\nВыбери встречу, чтобы посмотреть детали:"


async def handle_list(chat_id: int, user_id: int) -> None:
    user = await get_user_by_telegram_id(user_id)
    if not user:
        await tg_send_message(chat_id, "🔒 Сначала /start.")
        return
    pool = await get_pool()
    invitee_filter = json.dumps([{"telegram_id": user_id}])
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, status, title, started_at
            FROM telemost.meetings
            WHERE deleted_at IS NULL
              AND (
                triggered_by = $1
                OR organizer_id = $1
                OR invitees @> $2::jsonb
              )
            ORDER BY COALESCE(started_at, created_at) DESC
            LIMIT 10
            """,
            user_id,
            invitee_filter,
        )
    if not rows:
        await tg_send_message(chat_id, _EMPTY)
        return

    keyboard_rows = []
    for r in rows:
        short_id = str(r["id"])[:8]
        title = r["title"] or "(без названия)"
        when_str = (
            r["started_at"].strftime("%d.%m %H:%M") if r["started_at"] else "—"
        )
        keyboard_rows.append([list_row_button(short_id, title, when_str)])

    await tg_send_message(
        chat_id,
        _HEADER,
        reply_markup={"inline_keyboard": keyboard_rows},
    )
```

- [ ] **Step 4: Тесты**

Run: `pytest tests/services/telemost_recorder_api/test_handle_list.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add services/telemost_recorder_api/handlers/list_meetings.py tests/services/telemost_recorder_api/test_handle_list.py
git commit -m "feat(telemost): /list shows one inline button per meeting"
```

---

### Task 7: Per-meeting callback handlers (`meet:<short_id>:<action>`)

**Files:**
- Create: `services/telemost_recorder_api/handlers/meeting_actions.py`
- Modify: `services/telemost_recorder_api/handlers/__init__.py`
- Modify: `services/telemost_recorder_api/notifier.py` (attach action keyboard to DM)
- Test: `tests/services/telemost_recorder_api/test_meeting_actions.py`

**Context:** Все per-meeting actions роутятся через один namespace `meet:<short_id8>:<action>`. Actions: `show` — отрисовать summary встречи + `meeting_actions` keyboard, `transcript` — отправить `transcript_<id>.txt` документом, `summary` — переотправить format_summary_message, `delete` — спросить подтверждение (`confirm_delete` keyboard), `confirm_delete` — реально удалить + DM "удалено". Ownership проверяется через `load_meeting_by_short_id(short_id, user_id)` — если None, callback отвечает "Не нашёл встречу или нет прав".

- [ ] **Step 1: Failing tests**

`tests/services/telemost_recorder_api/test_meeting_actions.py`:

```python
"""meet:<short_id>:<action> callback handlers."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from services.telemost_recorder_api.handlers.meeting_actions import handle_meet


@pytest.mark.asyncio
async def test_meet_show_renders_summary_with_action_keyboard():
    mid = uuid4()
    meeting = {
        "id": mid, "title": "Daily", "started_at": None,
        "duration_seconds": 1800, "status": "done", "tags": [],
        "summary": {"topics": [], "decisions": [], "tasks": []},
        "processed_paragraphs": [],
    }
    sent = []

    async def fake_send(chat_id, text, *, reply_markup=None, **_):
        sent.append({"text": text, "reply_markup": reply_markup})

    with patch(
        "services.telemost_recorder_api.handlers.meeting_actions.load_meeting_by_short_id",
        AsyncMock(return_value=meeting),
    ), patch(
        "services.telemost_recorder_api.handlers.meeting_actions.tg_send_message",
        AsyncMock(side_effect=fake_send),
    ):
        await handle_meet(chat_id=1, user_id=111, short_id=str(mid)[:8], action="show")

    assert len(sent) == 1
    kb = sent[0]["reply_markup"]
    cbs = [b["callback_data"] for row in kb["inline_keyboard"] for b in row]
    assert any(c.endswith(":transcript") for c in cbs)
    assert any(c.endswith(":delete") for c in cbs)


@pytest.mark.asyncio
async def test_meet_transcript_sends_document():
    mid = uuid4()
    meeting = {
        "id": mid, "title": "T", "started_at": None,
        "duration_seconds": 60, "status": "done",
        "processed_paragraphs": [
            {"start_ms": 0, "speaker": "Иван", "text": "Привет"},
        ],
        "summary": {}, "tags": [],
    }
    docs = []

    async def fake_doc(chat_id, file_bytes, *, filename, caption=None):
        docs.append({"filename": filename, "bytes": file_bytes})

    with patch(
        "services.telemost_recorder_api.handlers.meeting_actions.load_meeting_by_short_id",
        AsyncMock(return_value=meeting),
    ), patch(
        "services.telemost_recorder_api.handlers.meeting_actions.tg_send_document",
        AsyncMock(side_effect=fake_doc),
    ):
        await handle_meet(chat_id=1, user_id=111, short_id=str(mid)[:8], action="transcript")

    assert len(docs) == 1
    assert docs[0]["filename"].startswith("transcript_")
    assert b"Iван" in docs[0]["bytes"] or "Иван".encode() in docs[0]["bytes"]


@pytest.mark.asyncio
async def test_meet_delete_asks_confirmation_not_deletes():
    mid = uuid4()
    meeting = {"id": mid, "title": "T", "status": "done", "started_at": None,
               "duration_seconds": 0, "summary": {}, "tags": [],
               "processed_paragraphs": []}
    sent = []

    async def fake_send(chat_id, text, *, reply_markup=None, **_):
        sent.append({"text": text, "reply_markup": reply_markup})

    deleted = []

    async def fake_delete(*a, **kw):
        deleted.append((a, kw))

    with patch(
        "services.telemost_recorder_api.handlers.meeting_actions.load_meeting_by_short_id",
        AsyncMock(return_value=meeting),
    ), patch(
        "services.telemost_recorder_api.handlers.meeting_actions.tg_send_message",
        AsyncMock(side_effect=fake_send),
    ), patch(
        "services.telemost_recorder_api.handlers.meeting_actions.delete_meeting_for_owner",
        AsyncMock(side_effect=fake_delete),
    ):
        await handle_meet(chat_id=1, user_id=111, short_id=str(mid)[:8], action="delete")

    assert deleted == []  # not deleted yet
    assert len(sent) == 1
    kb = sent[0]["reply_markup"]
    cbs = [b["callback_data"] for row in kb["inline_keyboard"] for b in row]
    assert any(c.endswith(":confirm_delete") for c in cbs)


@pytest.mark.asyncio
async def test_meet_confirm_delete_actually_deletes():
    mid = uuid4()
    meeting = {"id": mid, "title": "T", "status": "done", "started_at": None,
               "duration_seconds": 0, "summary": {}, "tags": [],
               "processed_paragraphs": []}
    sent = []

    async def fake_send(chat_id, text, *, reply_markup=None, **_):
        sent.append(text)

    with patch(
        "services.telemost_recorder_api.handlers.meeting_actions.load_meeting_by_short_id",
        AsyncMock(return_value=meeting),
    ), patch(
        "services.telemost_recorder_api.handlers.meeting_actions.tg_send_message",
        AsyncMock(side_effect=fake_send),
    ), patch(
        "services.telemost_recorder_api.handlers.meeting_actions.delete_meeting_for_owner",
        AsyncMock(return_value=True),
    ):
        await handle_meet(
            chat_id=1, user_id=111, short_id=str(mid)[:8], action="confirm_delete"
        )

    assert any("Удалено" in s or "удалена" in s.lower() for s in sent)


@pytest.mark.asyncio
async def test_meet_unknown_action_returns_silently():
    mid = uuid4()
    meeting = {"id": mid, "title": "T", "status": "done", "started_at": None,
               "duration_seconds": 0, "summary": {}, "tags": [],
               "processed_paragraphs": []}
    sent = []

    async def fake_send(chat_id, text, *, reply_markup=None, **_):
        sent.append(text)

    with patch(
        "services.telemost_recorder_api.handlers.meeting_actions.load_meeting_by_short_id",
        AsyncMock(return_value=meeting),
    ), patch(
        "services.telemost_recorder_api.handlers.meeting_actions.tg_send_message",
        AsyncMock(side_effect=fake_send),
    ):
        await handle_meet(chat_id=1, user_id=111, short_id=str(mid)[:8], action="banana")

    assert sent == []  # no spam


@pytest.mark.asyncio
async def test_meet_not_owner_responds_not_found():
    sent = []

    async def fake_send(chat_id, text, *, reply_markup=None, **_):
        sent.append(text)

    with patch(
        "services.telemost_recorder_api.handlers.meeting_actions.load_meeting_by_short_id",
        AsyncMock(return_value=None),
    ), patch(
        "services.telemost_recorder_api.handlers.meeting_actions.tg_send_message",
        AsyncMock(side_effect=fake_send),
    ):
        await handle_meet(chat_id=1, user_id=999, short_id="deadbeef", action="show")

    assert len(sent) == 1
    assert "не нашёл" in sent[0].lower() or "не найдена" in sent[0].lower()
```

- [ ] **Step 2: Запустить — упадёт**

Run: `pytest tests/services/telemost_recorder_api/test_meeting_actions.py -v`
Expected: FAIL — ImportError.

- [ ] **Step 3: Реализовать `meeting_actions.py`**

```python
"""Callback-handlers for inline buttons: meet:<short_id>:<action>.

Actions:
- show          — send summary message + action keyboard
- transcript    — send transcript_<id>.txt as document
- summary       — re-send summary message (no keyboard)
- delete        — ask confirmation (no actual delete)
- confirm_delete — actually soft-delete + DM "Удалено"
"""
from __future__ import annotations

import logging
from typing import Any

from services.telemost_recorder_api.keyboards import (
    confirm_delete,
    meeting_actions,
)
from services.telemost_recorder_api.meetings_repo import (
    build_transcript_text,
    delete_meeting_for_owner,
    load_meeting_by_short_id,
)
from services.telemost_recorder_api.notifier import format_summary_message
from services.telemost_recorder_api.telegram_client import (
    tg_send_document,
    tg_send_message,
)

logger = logging.getLogger(__name__)


_NOT_FOUND = "🤔 Не нашёл такую встречу или у тебя нет прав на неё."


async def handle_meet(
    *, chat_id: int, user_id: int, short_id: str, action: str
) -> None:
    meeting = await load_meeting_by_short_id(short_id, owner_telegram_id=user_id)
    if not meeting:
        await tg_send_message(chat_id, _NOT_FOUND)
        return

    if action == "show":
        await _send_show(chat_id, meeting)
    elif action == "summary":
        await tg_send_message(chat_id, format_summary_message(meeting))
    elif action == "transcript":
        await _send_transcript(chat_id, meeting)
    elif action == "delete":
        await _ask_delete_confirm(chat_id, meeting, short_id)
    elif action == "confirm_delete":
        await _do_delete(chat_id, meeting, user_id)
    else:
        logger.info("Unknown meet action: %s", action)


async def _send_show(chat_id: int, meeting: dict[str, Any]) -> None:
    short_id = str(meeting["id"])[:8]
    await tg_send_message(
        chat_id,
        format_summary_message(meeting),
        reply_markup=meeting_actions(short_id),
    )


async def _send_transcript(chat_id: int, meeting: dict[str, Any]) -> None:
    paragraphs = meeting.get("processed_paragraphs") or []
    text = build_transcript_text(paragraphs)
    filename = f"transcript_{str(meeting['id'])[:8]}.txt"
    await tg_send_document(
        chat_id,
        text.encode("utf-8"),
        filename=filename,
        caption=f"Полный transcript ({len(paragraphs)} параграфов)",
    )


async def _ask_delete_confirm(chat_id: int, meeting: dict[str, Any], short_id: str) -> None:
    title = meeting.get("title") or "(без названия)"
    await tg_send_message(
        chat_id,
        f"🗑 Точно удалить встречу *{title}*?\n\nЭто действие необратимо.",
        reply_markup=confirm_delete(short_id),
    )


async def _do_delete(chat_id: int, meeting: dict[str, Any], user_id: int) -> None:
    ok = await delete_meeting_for_owner(meeting["id"], owner_telegram_id=user_id)
    if ok:
        await tg_send_message(chat_id, "✅ Удалено.")
    else:
        await tg_send_message(chat_id, "❌ Не получилось удалить (встреча активна или нет прав).")
```

- [ ] **Step 4: Подключить роутер в `handlers/__init__.py`**

Модифицировать `_handle_callback_query` — добавить ветку `elif data.startswith("meet:"):`:

```python
# in services/telemost_recorder_api/handlers/__init__.py
from services.telemost_recorder_api.handlers.meeting_actions import handle_meet

# ... inside _handle_callback_query, after the menu:* branches:
    elif data.startswith("meet:"):
        parts = data.split(":", 2)
        if len(parts) == 3:
            _, short_id, action = parts
            await handle_meet(
                chat_id=chat_id, user_id=user_id,
                short_id=short_id, action=action,
            )
        else:
            logger.info("Malformed meet callback: %s", data)
```

- [ ] **Step 5: Прицепить `meeting_actions` keyboard к summary DM в `notifier.py`**

В `notify_meeting_result`, после успешного `tg_send_message(triggered_by, summary_text)` — заменить на:

```python
from services.telemost_recorder_api.keyboards import meeting_actions

short_id = str(meeting_id)[:8]
await tg_send_message(
    triggered_by, summary_text,
    reply_markup=meeting_actions(short_id),
)
```

Так пользователь сразу получает кнопки на свежевыпеченной встрече.

- [ ] **Step 6: Тесты**

Run: `pytest tests/services/telemost_recorder_api/test_meeting_actions.py tests/services/telemost_recorder_api/test_notifier.py -v`
Expected: PASS (старые `test_notifier.py` могут потребовать обновления: ожидаемые kwargs в `tg_send_message` теперь включают `reply_markup`. При необходимости поправить ассерты — для этого читай тесты сначала, прежде чем редактировать notifier).

- [ ] **Step 7: Commit**

```bash
git add services/telemost_recorder_api/handlers/meeting_actions.py services/telemost_recorder_api/handlers/__init__.py services/telemost_recorder_api/notifier.py tests/services/telemost_recorder_api/test_meeting_actions.py
git commit -m "feat(telemost): per-meeting inline actions (show/transcript/summary/delete)"
```

---

### Task 8: Dev-loop test rig — restart recorder every N minutes

**Files:**
- Create: `scripts/telemost_dev_loop.sh`
- Create: `scripts/telemost_dev_loop_README.md` (опционально — оставить в коде комментарий, не отдельный файл)

**Context:** Локально (или на сервере) скрипт берёт фиксированный `MEETING_URL` и каждые `INTERVAL_SECONDS` секунд: (a) останавливает текущий recorder-контейнер (если есть), (b) POSTит `/internal/spawn_recorder` (или ставит row в очередь напрямую через `psql`), (c) спит. Дешёвая итерация для отладки UX/DM без необходимости заново звать коллег в созвон.

**Дизайн:** один внешний созвон, который идёт долго (часы). Скрипт работает на твоей машине, дёргает API на сервере (через ssh-туннель или прямой curl на 8006).

- [ ] **Step 1: Создать `scripts/telemost_dev_loop.sh`**

```bash
#!/usr/bin/env bash
# Dev-loop rig: restart the recorder against the same meeting every N seconds.
# Use when iterating on DM rendering / handlers without burning real meetings.
#
# Required env:
#   TELEMOST_API=http://localhost:8006         # or ssh tunnel
#   TELEMOST_API_TOKEN=...                     # X-API-Key if API enforces it
#   MEETING_URL=https://telemost.360.yandex.ru/j/...
#   TRIGGERED_BY=111111111                     # telegram_id of the test user
# Optional:
#   INTERVAL_SECONDS=300                       # default 5 min
#   MAX_ITER=100                               # default unlimited
set -euo pipefail

: "${TELEMOST_API:?TELEMOST_API is required}"
: "${MEETING_URL:?MEETING_URL is required}"
: "${TRIGGERED_BY:?TRIGGERED_BY is required}"
INTERVAL="${INTERVAL_SECONDS:-300}"
MAX="${MAX_ITER:-0}"
HEADERS=()
if [[ -n "${TELEMOST_API_TOKEN:-}" ]]; then
  HEADERS=(-H "X-API-Key: ${TELEMOST_API_TOKEN}")
fi

i=0
while :; do
  i=$((i+1))
  echo "[$(date -Iseconds)] iter $i — enqueueing $MEETING_URL"
  curl -sS -X POST "$TELEMOST_API/internal/spawn_recorder" \
    "${HEADERS[@]}" \
    -H 'Content-Type: application/json' \
    -d "{\"meeting_url\":\"$MEETING_URL\",\"triggered_by\":$TRIGGERED_BY}" \
    || echo "  spawn failed"
  if [[ "$MAX" != "0" && "$i" -ge "$MAX" ]]; then
    echo "[$(date -Iseconds)] reached MAX_ITER=$MAX, stop"
    exit 0
  fi
  echo "[$(date -Iseconds)] sleeping ${INTERVAL}s..."
  sleep "$INTERVAL"
done
```

- [ ] **Step 2: chmod + dry-run check**

```bash
chmod +x scripts/telemost_dev_loop.sh
bash -n scripts/telemost_dev_loop.sh
```

Expected: no output (валидный скрипт).

- [ ] **Step 3: Убедиться, что `/internal/spawn_recorder` endpoint существует**

Проверить наличие в `services/telemost_recorder_api/app.py` или `routes/*.py`. Если не существует — **создать минимальный endpoint** в новом файле `services/telemost_recorder_api/internal_routes.py`, который принимает `(meeting_url, triggered_by)`, делает INSERT в `telemost.meetings` со status='queued' (recorder worker подхватит сам через _pick_queued). Защитить `X-API-Key` из ENV `TELEMOST_INTERNAL_KEY`. **Если endpoint уже есть** — пропустить этот шаг.

- [ ] **Step 4: README-комментарий**

В шапку `telemost_dev_loop.sh` уже добавлен help; отдельный MD не создаём.

- [ ] **Step 5: Commit**

```bash
git add scripts/telemost_dev_loop.sh
# (если создан) git add services/telemost_recorder_api/internal_routes.py services/telemost_recorder_api/app.py
git commit -m "chore(telemost): dev-loop test rig — restart recorder against same URL every N seconds"
```

---

## Self-Review checklist (после написания плана)

- ✅ Все задачи имеют точные пути файлов и реальные тесты.
- ✅ CTO+DevOps критика покрыта пунктами 1–6 → задачи 1 (ASR), 2-3 (Bitrix+LLM), 5-7 (UX inline buttons), 8 (dev rig).
- ✅ Нет placeholder "TBD / implement later" — каждый код-step содержит код.
- ✅ Sequence: 4 (repo helpers) идёт **перед** 7 (handlers, который их использует). 5 (keyboards) перед 6 и 7.
- ✅ Миграция 003 — в задаче 4, применяем вручную после merge.
- ⚠ Observability (пункт 6 критики) — **сознательно отложен**: не блокирует UX, может уйти в отдельный мини-план после первого прохода.
- ⚠ `_send_show` / `format_summary_message` имеют один и тот же call с разным reply_markup — реально это нормально, kbd на DM = свежая встреча, kbd на `show` = старая встреча; UX одинаков, код переиспользуется.

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-05-12-telemost-recorder-ux-and-bitrix-enrichment.md`.**

User said "будем исправлять по плану, который ты сохранишь, а потом отдельно запустим" — поэтому **не запускаем сейчас**. Запуск отдельно через:

- **Recommended:** `/sp:subagent-driven-development` против этого файла — fresh subagent per task, two-stage review (spec → quality).
- **Alternative:** `/sp:executing-plans` — inline batch execution.

При запуске:
1. Старт с Task 1 (parallel ASR) — это разблокирует dev-loop по скорости.
2. Tasks 4–7 рекомендуется делать одним подходом (репо + клавиатуры + /list + actions) — они тесно связаны.
3. Task 2 (Bitrix) можно делать параллельно с 1, не зависит от UX-цепочки.
