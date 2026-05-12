# Telemost Recorder — Pipeline Stabilization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Полностью замкнуть pipeline записи встреч Я.Телемост — от Chromium WebRTC playback до DM с реальным LLM-summary в Telegram. Закрыть 4 оставшихся бага (LLM JSON truncation, notifier resend lock, other-bots exit detection, serial spawn), восстановить 2 застрявших meeting (`af19b95f`, `36fc0387`), верифицировать E2E.

**Architecture:** Pipeline уже работает по частям (audio→ASR починен коммитами `924ee4d`, `09f597c`). Остаются 4 точечных дефекта в звеньях postprocess (LLM truncation), notifier (idempotency-gate без reset), recorder exit logic (не учитывает не-человеческих участников), recorder_worker (serial). Каждый фикс — локальный, без архитектурных перестановок. TDD во всех task'ах: сначала failing test, потом implementation, потом manual E2E на dev сервере.

**Tech Stack:** Python 3.11+ async, httpx (OpenRouter), asyncpg (Supabase), Playwright (Chromium DOM scraping), pytest. Сервер: Timeweb Cloud, docker-compose API + manually built `telemost_recorder:latest` image. Supabase project `gjvwcdtfglupewcwzfhw`, schema `telemost`.

---

## Контекст: уже сделанные фиксы (НЕ переделывать)

| SHA | Что починено | Status |
|---|---|---|
| `924ee4d` | `docker_client.py:51` default `headless=False` → Chromium launches full binary, WebRTC inbound audio течёт в PulseAudio sink | merged main, deployed |
| `09f597c` | `join.py:_write_transcript` дополнительно пишет `raw_segments.json` для recorder_worker'а | merged main, recorder image rebuilt |

## Известные открытые баги (то, что план закрывает)

| # | Симптом | Корень | Файл:строка |
|---|---|---|---|
| 3 | LLM `LLMPostprocessError: invalid JSON` на длинных встречах | `_call_openrouter` без `max_tokens`/`response_format` → output truncates | `services/telemost_recorder_api/llm_postprocess.py:82-95` |
| 4 | После recovery meeting'а notifier пропускает повторный DM (`"already notified, skipping"`) | `notified_at` не сбрасывается при возврате status в `postprocessing` | `services/telemost_recorder_api/workers/postprocess_worker.py:69-90` |
| 6 | Recorder пишет всё время до hard-limit вместо exit когда люди ушли | `extract_participants` фильтрует только `"Wookiee Recorder"`, не других ботов | `services/telemost_recorder/join.py:178-214` |
| 5 | Задержка 32-40 мин для второй параллельной meeting | `run_forever` обрабатывает по одному, `MAX_PARALLEL_RECORDINGS` объявлен но не используется | `services/telemost_recorder_api/workers/recorder_worker.py:189-204` |

## Pending recovery (one-shot)

- Meeting `af19b95f-50fa-4f60-aef5-fcb543989e94` — transcript в БД (после ручной инъекции), status `failed` из-за LLM truncation. После Task 1+2 — повторный postprocess + DM.
- Meeting `36fc0387-34e1-4d7a-9264-3983784f659c` — recorder сейчас активно пишет на старом образе (без fix `09f597c`). После его exit нужна та же ручная инъекция transcript.

---

## File Structure

### Modify

| Файл | За что отвечает | Что меняем |
|---|---|---|
| `services/telemost_recorder_api/llm_postprocess.py` | Single-call OpenRouter postprocess | `+max_tokens`, `+response_format`, новая chunked-функция для >150 сегментов |
| `services/telemost_recorder_api/workers/postprocess_worker.py` | Pickup `postprocessing` meetings, run LLM, mark done | `_update_meeting` сбрасывает `notified_at` при возврате в `postprocessing` |
| `services/telemost_recorder/join.py` | Meeting loop, participants scraping, end detection | `extract_participants` фильтрует `KNOWN_BOT_NAMES`, `detect_meeting_ended` использует фильтрованный список |
| `services/telemost_recorder/config.py` | Конфиг recorder контейнера | `KNOWN_BOT_NAMES` — frozenset |
| `services/telemost_recorder_api/workers/recorder_worker.py` | Spawn recorder containers | `run_forever` использует `asyncio.Semaphore(MAX_PARALLEL_RECORDINGS)` |

### Create

| Файл | Назначение |
|---|---|
| `scripts/telemost_recover_meeting.py` | CLI: одношаговое восстановление застрявшего meeting из transcript.json на диске |
| `tests/services/telemost_recorder/test_participants_filter.py` | Тесты фильтрации ботов в `extract_participants` |

### Tests to extend (не создавать новые)

| Файл | Что добавляем |
|---|---|
| `tests/services/telemost_recorder_api/test_llm_postprocess.py` | `test_call_openrouter_includes_max_tokens`, `test_call_openrouter_uses_json_mode`, `test_postprocess_meeting_chunked_for_large_segments`, regression `test_truncated_json_raises_postprocess_error` |
| `tests/services/telemost_recorder_api/test_postprocess_worker.py` | `test_status_back_to_postprocessing_resets_notified_at` |
| `tests/services/telemost_recorder_api/test_notifier.py` | `test_resend_after_notified_at_reset` |
| `tests/services/telemost_recorder_api/test_recorder_worker.py` | `test_run_forever_spawns_up_to_max_parallel`, `test_semaphore_releases_on_finalize` |

---

## Task 1: Bug #3 — LLM JSON robustness

**Цель:** OpenRouter всегда возвращает валидный JSON; для transcript'ов >150 сегментов работает chunked fallback (отдельный вызов для `summary+tags`, отдельный для `paragraphs+speakers_map`).

**Files:**
- Modify: `services/telemost_recorder_api/llm_postprocess.py`
- Test: `tests/services/telemost_recorder_api/test_llm_postprocess.py`

- [ ] **Step 1.1: Read existing tests for llm_postprocess**

Run: `cat tests/services/telemost_recorder_api/test_llm_postprocess.py`

Цель — понять структуру fixture'ов (httpx mock или respx), стиль assertion'ов, как сейчас тестируется `_call_openrouter`. Запомни: fixture для OpenRouter response, какие helper'ы есть, какой формат фейк-segments.

- [ ] **Step 1.2: Write failing test для max_tokens + response_format**

Add to `tests/services/telemost_recorder_api/test_llm_postprocess.py`:

```python
import httpx
import pytest
import respx

from services.telemost_recorder_api.llm_postprocess import _call_openrouter


@respx.mock
@pytest.mark.asyncio
async def test_call_openrouter_includes_max_tokens_and_json_mode():
    """Body must request response_format=json_object and max_tokens=16000 to prevent truncation."""
    captured = {}

    def _capture(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.content.decode()
        return httpx.Response(200, json={
            "choices": [{"message": {"content": '{"ok": true}'}}]
        })

    respx.post("https://openrouter.ai/api/v1/chat/completions").mock(side_effect=_capture)

    await _call_openrouter("test prompt", "google/gemini-3-flash-preview", 30)

    import json as _json
    body = _json.loads(captured["body"])
    assert body["max_tokens"] == 16000
    assert body["response_format"] == {"type": "json_object"}
```

- [ ] **Step 1.3: Run test, verify FAIL**

Run: `.venv/bin/python -m pytest tests/services/telemost_recorder_api/test_llm_postprocess.py::test_call_openrouter_includes_max_tokens_and_json_mode -v`

Expected: FAIL — `KeyError: 'max_tokens'` или `body["max_tokens"] != 16000` (тест проверяет ключи которых пока нет).

- [ ] **Step 1.4: Add max_tokens + response_format to _call_openrouter**

Edit `services/telemost_recorder_api/llm_postprocess.py:82-86` — заменить body на:

```python
    body = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
        "max_tokens": 16000,
        "response_format": {"type": "json_object"},
    }
```

После Edit — `Read` файл и убедись что изменение на месте (формат не поломался).

- [ ] **Step 1.5: Run test, verify PASS**

Run: `.venv/bin/python -m pytest tests/services/telemost_recorder_api/test_llm_postprocess.py::test_call_openrouter_includes_max_tokens_and_json_mode -v`

Expected: PASS.

- [ ] **Step 1.6: Write failing test для chunked fallback**

Add to same test file:

```python
import json as _json

@respx.mock
@pytest.mark.asyncio
async def test_postprocess_meeting_chunked_for_large_segments(monkeypatch):
    """For >150 segments, do two LLM calls and merge results (summary+tags first, paragraphs+speakers_map second)."""
    from services.telemost_recorder_api.llm_postprocess import postprocess_meeting

    call_count = {"n": 0}
    summary_response = {
        "tags": ["продажи", "маркетинг"],
        "summary": {
            "participants": ["Данила"],
            "topics": [{"title": "Итоги недели", "anchor": "[00:00]"}],
            "decisions": ["Запустить тест креативов"],
            "tasks": [{"assignee": "Данила", "what": "оптимизировать рекламу", "when": null}],
        },
    }
    paragraphs_response = {
        "paragraphs": [{"speaker": "Speaker 0", "start_ms": 0, "text": "Привет команде"}],
        "speakers_map": {"Speaker 0": "Данила"},
    }

    def _route(request: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        if call_count["n"] == 1:
            return httpx.Response(200, json={"choices": [{"message": {"content": _json.dumps(summary_response)}}]})
        return httpx.Response(200, json={"choices": [{"message": {"content": _json.dumps(paragraphs_response)}}]})

    respx.post("https://openrouter.ai/api/v1/chat/completions").mock(side_effect=_route)

    segments = [{"speaker": "Speaker 0", "start_ms": i * 1000, "end_ms": (i+1)*1000, "text": "test"} for i in range(160)]
    participants = [{"name": "Данила"}]

    result = await postprocess_meeting(segments, participants)
    assert call_count["n"] == 2
    assert "paragraphs" in result and result["paragraphs"][0]["text"] == "Привет команде"
    assert result["speakers_map"] == {"Speaker 0": "Данила"}
    assert result["tags"] == ["продажи", "маркетинг"]
    assert result["summary"]["topics"][0]["title"] == "Итоги недели"
```

(Replace `null` literal with `None` — Python syntax. Fix during write.)

- [ ] **Step 1.7: Run test, verify FAIL**

Run: `.venv/bin/python -m pytest tests/services/telemost_recorder_api/test_llm_postprocess.py::test_postprocess_meeting_chunked_for_large_segments -v`

Expected: FAIL — `call_count["n"] == 1`, not 2.

- [ ] **Step 1.8: Implement chunked path in postprocess_meeting**

Edit `services/telemost_recorder_api/llm_postprocess.py`. Append before `postprocess_meeting`:

```python
_CHUNK_THRESHOLD = 150


_PROMPT_SUMMARY_ONLY = """Ты — редактор расшифровок встреч бренда Wookiee. На вход — сегменты ASR с диаризацией и список участников. Верни СТРОГО один JSON следующей формы (никаких markdown, никаких комментариев):

{{
  "tags": ["<тег>", "..."],
  "summary": {{
    "participants": ["<имя>", "..."],
    "topics": [{{"title": "<тема>", "anchor": "[MM:SS]"}}],
    "decisions": ["<решение>", "..."],
    "tasks": [{{"assignee": "<имя>", "what": "<что сделать>", "when": "<срок или null>"}}]
  }}
}}

Tags — ТОЛЬКО из канонического списка: креативы, реклама, маркетинг, продажи, разработка, отчётность, HR, финансы, ассортимент, поставки, логистика, упаковка, бренд, маркетплейс, конкуренты, аналитика, продукт, контент, операции, прочее. От 1 до 6 наиболее релевантных.

Participants:
{participants}

Segments:
{segments}
"""

_PROMPT_PARAGRAPHS_ONLY = """Ты — редактор расшифровок встреч. На вход — сегменты ASR. Склей соседние короткие чанки одного спикера в смысловые абзацы, восстанови пунктуацию и регистр, сопоставь каждого "Speaker N" с реальным именем участника на основе содержания реплик. Верни СТРОГО один JSON:

{{
  "paragraphs": [
    {{"speaker": "<имя или Speaker N>", "start_ms": <int>, "text": "<текст абзаца>"}}
  ],
  "speakers_map": {{"Speaker 0": "<имя или Speaker 0>"}}
}}

Participants:
{participants}

Segments:
{segments}
"""


def _build_summary_prompt(segments: list[dict], participants: list[dict]) -> str:
    seg_text = "\n".join(
        f"[{s['start_ms'] // 1000:>4}s {s['speaker']}] {s['text']}" for s in segments
    )
    p_text = "\n".join(f"- {p['name']}" for p in participants) or "(нет данных)"
    return _PROMPT_SUMMARY_ONLY.format(participants=p_text, segments=seg_text)


def _build_paragraphs_prompt(segments: list[dict], participants: list[dict]) -> str:
    seg_text = "\n".join(
        f"[{s['start_ms'] // 1000:>4}s {s['speaker']}] {s['text']}" for s in segments
    )
    p_text = "\n".join(f"- {p['name']}" for p in participants) or "(нет данных)"
    return _PROMPT_PARAGRAPHS_ONLY.format(participants=p_text, segments=seg_text)
```

Replace the body of `postprocess_meeting` (~line 114-134) with:

```python
async def postprocess_meeting(
    segments: list[dict],
    participants: list[dict],
    *,
    model: Optional[str] = None,
) -> dict:
    """Run LLM postprocessing. For >150 segments, split into two calls to avoid token-limit truncation."""
    use_model = model or LLM_POSTPROCESS_MODEL

    if len(segments) <= _CHUNK_THRESHOLD:
        prompt = build_prompt(segments, participants)
        raw = await _call_openrouter(prompt, use_model, LLM_POSTPROCESS_TIMEOUT_SECONDS)
        cleaned = _strip_markdown_codefence(raw)
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.error("LLM returned non-JSON: %r", cleaned[:500])
            raise LLMPostprocessError(f"invalid JSON: {e}") from e
        _validate_shape(data)
        return data

    # Chunked path
    summary_prompt = _build_summary_prompt(segments, participants)
    summary_raw = await _call_openrouter(summary_prompt, use_model, LLM_POSTPROCESS_TIMEOUT_SECONDS)
    try:
        summary_data = json.loads(_strip_markdown_codefence(summary_raw))
    except json.JSONDecodeError as e:
        logger.error("LLM (summary chunk) returned non-JSON: %r", summary_raw[:500])
        raise LLMPostprocessError(f"invalid JSON (summary chunk): {e}") from e

    paragraphs_prompt = _build_paragraphs_prompt(segments, participants)
    paragraphs_raw = await _call_openrouter(paragraphs_prompt, use_model, LLM_POSTPROCESS_TIMEOUT_SECONDS)
    try:
        paragraphs_data = json.loads(_strip_markdown_codefence(paragraphs_raw))
    except json.JSONDecodeError as e:
        logger.error("LLM (paragraphs chunk) returned non-JSON: %r", paragraphs_raw[:500])
        raise LLMPostprocessError(f"invalid JSON (paragraphs chunk): {e}") from e

    merged = {
        "paragraphs": paragraphs_data.get("paragraphs", []),
        "speakers_map": paragraphs_data.get("speakers_map", {}),
        "tags": summary_data.get("tags", []),
        "summary": summary_data.get("summary", {}),
    }
    _validate_shape(merged)
    return merged
```

После Edit — `Read` файл и убедись, что обе функции на месте и нет lingering старого кода.

- [ ] **Step 1.9: Run both tests + full suite, verify PASS**

```bash
.venv/bin/python -m pytest tests/services/telemost_recorder_api/test_llm_postprocess.py -v
.venv/bin/python -m pytest tests/services/telemost_recorder/ tests/services/telemost_recorder_api/ -q
```

Expected: оба новых теста PASS, регрессий нет (предыдущие 165 passed, 2 skipped + 2 новых = 167 passed, 2 skipped).

- [ ] **Step 1.10: Commit**

```bash
git add services/telemost_recorder_api/llm_postprocess.py tests/services/telemost_recorder_api/test_llm_postprocess.py
git commit -m "$(cat <<'EOF'
fix(telemost-api): harden LLM postprocess against token-limit truncation

Three layers of defense against OpenRouter response truncation on long
meetings (>150 ASR segments):

1. Force JSON mode (response_format=json_object) — model is more likely
   to close the structure correctly under token pressure.
2. Explicit max_tokens=16000 — gives headroom for full 95+ min meeting
   responses (previously OpenRouter defaulted to ~4096).
3. Chunked fallback for >150 segments: split into two LLM calls
   (summary+tags first, paragraphs+speakers_map second). Each output
   stays well under the per-call limit.

Closes the LLMPostprocessError seen on meeting af19b95f
(230 segments, truncated at char 29785).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
git push origin main
```

- [ ] **Step 1.11: Deploy API**

```bash
ssh timeweb 'cd /home/danila/projects/wookiee && git pull origin main && cd deploy && docker compose up -d --build telemost-recorder-api'
ssh timeweb 'docker ps --filter name=telemost_recorder_api --format "{{.Status}}"'
```

Expected: `Up X seconds (healthy)`.

---

## Task 2: Bug #4 — notifier resend after status flip

**Цель:** Когда meeting возвращается в `postprocessing` (после recovery или LLM retry), `notified_at` сбрасывается и notifier повторно отправляет DM с актуальным summary.

**Files:**
- Modify: `services/telemost_recorder_api/workers/postprocess_worker.py`
- Test: `tests/services/telemost_recorder_api/test_postprocess_worker.py`, `tests/services/telemost_recorder_api/test_notifier.py`

- [ ] **Step 2.1: Read existing postprocess_worker test fixtures**

Run: `cat tests/services/telemost_recorder_api/test_postprocess_worker.py | head -80`

Цель — понять как fixture создаёт meeting row, какой helper для async pg connection (asyncpg-mock / real test DB / in-memory).

- [ ] **Step 2.2: Write failing test для reset notified_at**

Add to `tests/services/telemost_recorder_api/test_postprocess_worker.py`:

```python
@pytest.mark.asyncio
async def test_status_back_to_postprocessing_resets_notified_at(test_pool):
    """When _update_meeting flips status back to 'postprocessing', notified_at must be cleared."""
    from services.telemost_recorder_api.workers.postprocess_worker import _update_meeting

    meeting_id = uuid.uuid4()
    async with test_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO telemost.meetings (id, source, meeting_url, status, notified_at, created_at)
            VALUES ($1, 'test', 'https://t.test/j/1', 'done', now(), now())
            """,
            meeting_id,
        )

    await _update_meeting(meeting_id, "postprocessing")

    async with test_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT status, notified_at FROM telemost.meetings WHERE id=$1",
            meeting_id,
        )
    assert row["status"] == "postprocessing"
    assert row["notified_at"] is None
```

(Подгони fixture name `test_pool` под существующий в conftest; если нет — переиспользуй pattern из других тестов в файле.)

- [ ] **Step 2.3: Run test, verify FAIL**

Run: `.venv/bin/python -m pytest tests/services/telemost_recorder_api/test_postprocess_worker.py::test_status_back_to_postprocessing_resets_notified_at -v`

Expected: FAIL — `notified_at is not None`.

- [ ] **Step 2.4: Modify _update_meeting to reset on postprocessing transition**

Edit `services/telemost_recorder_api/workers/postprocess_worker.py:69-90`. Заменить тело функции на:

```python
async def _update_meeting(meeting_id: UUID, status: str, **fields: Any) -> None:
    """Update meeting row with dynamic SET clause.

    Special case: status='postprocessing' resets notified_at so the notifier
    can re-send after manual recovery / retry. notifier remains idempotent
    per (meeting_id, notified_at IS NULL) — see notifier._claim_notification.

    `_JSONB_FIELDS` are encoded via `json.dumps(..., ensure_ascii=False)`
    and cast to ::jsonb. Other fields (e.g. `tags text[]`, `error text`)
    pass through directly — asyncpg adapts python list[str] to text[] natively.
    """
    pool = await get_pool()
    set_clauses = ["status = $2"]
    args: list[Any] = [meeting_id, status]
    idx = 3
    for k, v in fields.items():
        if k in _JSONB_FIELDS:
            args.append(json.dumps(v, ensure_ascii=False))
            set_clauses.append(f"{k} = ${idx}::jsonb")
        else:
            args.append(v)
            set_clauses.append(f"{k} = ${idx}")
        idx += 1
    if status == "postprocessing":
        set_clauses.append("notified_at = NULL")
    query = f"UPDATE telemost.meetings SET {', '.join(set_clauses)} WHERE id = $1"
    async with pool.acquire() as conn:
        await conn.execute(query, *args)
```

После Edit — `Read` файл, убедись что docstring и signature не сломаны.

- [ ] **Step 2.5: Run test, verify PASS + regression**

```bash
.venv/bin/python -m pytest tests/services/telemost_recorder_api/test_postprocess_worker.py -v
```

Expected: новый PASS, остальные тесты файла без регрессий.

- [ ] **Step 2.6: Write integration test — full notify-after-recovery flow**

Add to `tests/services/telemost_recorder_api/test_notifier.py`:

```python
@pytest.mark.asyncio
async def test_resend_after_notified_at_reset(test_pool, monkeypatch):
    """End-to-end: notifier sends → reset notified_at → second notifier call sends again."""
    from services.telemost_recorder_api.notifier import notify_meeting_result, _claim_notification

    meeting_id = uuid.uuid4()
    async with test_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO telemost.meetings (id, source, meeting_url, status, summary, created_at)
            VALUES ($1, 'test', 'https://t.test/j/1', 'done', '{"empty": true}'::jsonb, now())
            """,
            meeting_id,
        )

    # First claim succeeds
    first = await _claim_notification(meeting_id)
    assert first is not None

    # Second claim blocked (idempotency)
    second = await _claim_notification(meeting_id)
    assert second is None

    # Reset (simulates _update_meeting(... 'postprocessing'))
    async with test_pool.acquire() as conn:
        await conn.execute(
            "UPDATE telemost.meetings SET notified_at=NULL WHERE id=$1",
            meeting_id,
        )

    # Third claim succeeds again
    third = await _claim_notification(meeting_id)
    assert third is not None
    assert third != first  # different timestamp
```

- [ ] **Step 2.7: Run integration test, verify PASS**

Run: `.venv/bin/python -m pytest tests/services/telemost_recorder_api/test_notifier.py::test_resend_after_notified_at_reset -v`

Expected: PASS.

- [ ] **Step 2.8: Commit**

```bash
git add services/telemost_recorder_api/workers/postprocess_worker.py tests/services/telemost_recorder_api/test_postprocess_worker.py tests/services/telemost_recorder_api/test_notifier.py
git commit -m "$(cat <<'EOF'
fix(telemost-api): reset notified_at on postprocessing transition

After manual recovery or LLM retry, status flips done→postprocessing and
the meeting needs a fresh notify with updated summary. Previously the
notifier idempotency-gate (notified_at IS NOT NULL) blocked the resend
silently, leaving the user with the stale "no_speech_detected" DM forever.

Now _update_meeting clears notified_at whenever it sets status to
'postprocessing'. Notifier semantics unchanged (per-meeting-id +
notified_at-IS-NULL atomic claim).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
git push origin main
```

- [ ] **Step 2.9: Deploy API**

```bash
ssh timeweb 'cd /home/danila/projects/wookiee && git pull origin main && cd deploy && docker compose up -d --build telemost-recorder-api'
ssh timeweb 'docker ps --filter name=telemost_recorder_api --format "{{.Status}}"'
```

Expected: `Up X seconds (healthy)`.

---

## Task 3: Manual recovery CLI + восстановление двух застрявших meeting

**Цель:** Один воспроизводимый CLI-скрипт для восстановления любого meeting'а, у которого `raw_segments.json` есть на диске, но в БД пусто. После Task 1+2 этим скриптом восстанавливаются `af19b95f` и `36fc0387`, оба получают полноценный DM с реальным summary.

**Files:**
- Create: `scripts/telemost_recover_meeting.py`

- [ ] **Step 3.1: Verify `36fc0387` recording finished (НЕ переходить пока active)**

Run: `ssh timeweb 'docker ps -a --filter name=telemost_rec_36fc0387 --format "{{.ID}} {{.Status}}"'`

Expected: `Exited (0) X minutes ago`. Если ещё `Up X hours` — подожди или принудительно `docker stop telemost_rec_36fc0387` (audio.opus уже >250 КБ и transcript-stage начнётся после SIGTERM ffmpeg).

После exit убедись что есть transcript:
```bash
ssh timeweb 'ls -la /home/danila/projects/wookiee/data/telemost/36fc0387-34e1-4d7a-9264-3983784f659c/ | grep -E "transcript|raw_segments"'
```

Если `raw_segments.json` отсутствует (старый образ) — есть `transcript.json` с тем же содержимым (формат идентичен). Скрипт ниже умеет читать оба.

- [ ] **Step 3.2: Create recovery script**

Create `scripts/telemost_recover_meeting.py`:

```python
"""Recover a meeting whose transcript exists on disk but isn't in Supabase.

Usage:
    python scripts/telemost_recover_meeting.py <meeting_id>

Reads <DATA_DIR>/<meeting_id>/raw_segments.json (falls back to
transcript.json), loads into telemost.meetings.raw_segments, flips
status to 'postprocessing' so the worker picks it up, and reset
notified_at so the user gets the new DM with real summary.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from services.telemost_recorder_api.config import DATA_DIR
from services.telemost_recorder_api.db import get_pool


async def recover(meeting_id: str) -> None:
    artefact_dir = DATA_DIR / meeting_id
    candidate = artefact_dir / "raw_segments.json"
    if not candidate.exists():
        candidate = artefact_dir / "transcript.json"
    if not candidate.exists():
        print(f"ERROR: neither raw_segments.json nor transcript.json in {artefact_dir}", file=sys.stderr)
        sys.exit(2)

    payload = candidate.read_text()
    segments = json.loads(payload)
    print(f"Loaded {len(segments)} segments from {candidate.name}")

    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            """
            UPDATE telemost.meetings
            SET raw_segments = $2::jsonb,
                status = 'postprocessing',
                notified_at = NULL
            WHERE id = $1
            """,
            meeting_id,
            payload,
        )
    print(f"UPDATE result: {result}")
    print("Postprocess worker will pick up within ~5 sec. Notifier will resend DM.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python scripts/telemost_recover_meeting.py <meeting_id>", file=sys.stderr)
        sys.exit(1)
    asyncio.run(recover(sys.argv[1]))
```

- [ ] **Step 3.3: Smoke-test script syntax (no execution)**

Run: `.venv/bin/python -c "import ast; ast.parse(open('scripts/telemost_recover_meeting.py').read()); print('OK')"`

Expected: `OK`.

- [ ] **Step 3.4: Commit script before recovery (so it's reusable)**

```bash
git add scripts/telemost_recover_meeting.py
git commit -m "$(cat <<'EOF'
feat(telemost-recorder): add recover_meeting CLI for transcript-on-disk recovery

For meetings stuck with empty raw_segments in Supabase but with valid
transcript.json / raw_segments.json on the shared volume. Re-injects
the transcript, flips status to 'postprocessing', resets notified_at.

Used after the silent-audio + raw_segments.json filename-mismatch bugs
to restore meetings that finished before fixes were deployed.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
git push origin main
```

- [ ] **Step 3.5: Recover meeting `af19b95f`**

```bash
ssh timeweb 'cd /home/danila/projects/wookiee && git pull origin main && docker exec telemost_recorder_api python scripts/telemost_recover_meeting.py af19b95f-50fa-4f60-aef5-fcb543989e94'
```

Expected output: `Loaded 230 segments from transcript.json` (или `raw_segments.json` если новый образ уже писал) + `UPDATE result: UPDATE 1`.

- [ ] **Step 3.6: Watch postprocess + notifier for `af19b95f`**

Wait ~30-60 sec, then:
```bash
ssh timeweb 'docker logs --since 2m telemost_recorder_api 2>&1 | grep -iE "af19b95f|postprocess|notif" | tail -20'
```

Expected: видны строки `Postprocessing meeting af19b95f...` → `Postprocess finished` → `Notifier sent ...`. No `LLMPostprocessError`.

Затем проверь через MCP Supabase:
```sql
SELECT status, jsonb_array_length(raw_segments) AS segs,
       summary->'topics' AS topics,
       summary->'tasks' AS tasks,
       notified_at AT TIME ZONE 'Europe/Moscow' AS notified_msk
FROM telemost.meetings WHERE id='af19b95f-50fa-4f60-aef5-fcb543989e94';
```

Expected: `status=done`, `segs=230`, `topics` непустые, `notified_msk` свежий.

- [ ] **Step 3.7: Verify DM в Telegram**

Ask user to open chat with `@wookiee_recorder_bot` и подтвердить что новый DM прилетел с реальным summary (темы, задачи, не «тишина»).

- [ ] **Step 3.8: Recover meeting `36fc0387`**

```bash
ssh timeweb 'docker exec telemost_recorder_api python scripts/telemost_recover_meeting.py 36fc0387-34e1-4d7a-9264-3983784f659c'
```

Same expected output. Watch logs + check Supabase same way. Verify DM.

Если для `36fc0387` нет transcript.json на диске (recorder упал до transcribe) — задокументируй это как known limitation; recovery работает только когда ASR-stage завершился. В таком случае запись потеряна, но скрипт корректно сообщит ERROR.

---

## Task 4: Bug #6 — exclude known bots from participant count for exit detection

**Цель:** Recorder выходит из встречи когда **людей** не осталось, не считая других ботов (`navstreche.com`, `Salut`, etc.). Снижает overrecord time и расходы на SpeechKit.

**Files:**
- Modify: `services/telemost_recorder/config.py`, `services/telemost_recorder/join.py`
- Test: `tests/services/telemost_recorder/test_participants_filter.py` (новый)

- [ ] **Step 4.1: Add KNOWN_BOT_NAMES to config**

Read current `services/telemost_recorder/config.py` чтобы найти подходящее место (после других константных списков, если есть). Затем добавить:

```python
# Display names of known meeting bots that should NOT count as humans for
# meeting-ended detection. Substring match (case-insensitive) so trailing
# emoji / suffixes don't break filtering.
KNOWN_BOT_NAMES: frozenset[str] = frozenset({
    "wookiee recorder",      # this bot itself
    "navstreche.com",        # navstreche AI assistant
    "salut",                 # Sber Salut
    "yandex go",             # Yandex assistant
    "ai assistant",          # generic
    "ии-ассистент",          # russian generic
})
```

После Edit — `Read` файл чтобы убедиться что frozenset на месте.

- [ ] **Step 4.2: Write failing test для filter**

Create `tests/services/telemost_recorder/test_participants_filter.py`:

```python
"""Filter known bots out of participant lists for meeting-ended detection."""
from services.telemost_recorder.join import _filter_human_participants


def test_filter_removes_known_bots_case_insensitive():
    names = ["Данила Матвеев", "Wookiee Recorder", "navstreche.com ИИ-ассистент", "Алина"]
    humans = _filter_human_participants(names)
    assert humans == ["Данила Матвеев", "Алина"]


def test_filter_handles_bot_name_substring():
    names = ["Salut Bot 2.0", "Артём"]
    humans = _filter_human_participants(names)
    assert humans == ["Артём"]


def test_filter_empty_list():
    assert _filter_human_participants([]) == []


def test_filter_only_bots_returns_empty():
    names = ["Wookiee Recorder", "navstreche.com"]
    assert _filter_human_participants(names) == []


def test_filter_preserves_order():
    names = ["Артём", "Wookiee Recorder", "Данила", "Salut"]
    assert _filter_human_participants(names) == ["Артём", "Данила"]
```

- [ ] **Step 4.3: Run test, verify FAIL (import error)**

Run: `.venv/bin/python -m pytest tests/services/telemost_recorder/test_participants_filter.py -v`

Expected: FAIL — `ImportError: cannot import name '_filter_human_participants'`.

- [ ] **Step 4.4: Implement _filter_human_participants in join.py**

Edit `services/telemost_recorder/join.py`. Add import at top of file (after existing imports):

```python
from services.telemost_recorder.config import KNOWN_BOT_NAMES
```

Then add helper before `extract_participants` (around line 175):

```python
def _filter_human_participants(names: list[str]) -> list[str]:
    """Remove known bots (case-insensitive substring match) from participant list."""
    return [
        n for n in names
        if not any(bot in n.lower() for bot in KNOWN_BOT_NAMES)
    ]
```

Then modify `extract_participants` (currently returns `list(dict.fromkeys(names))` at line 214). Change last two lines to:

```python
    # Deduplicate, preserve order, then filter known bots
    deduped = list(dict.fromkeys(names))
    return _filter_human_participants(deduped)
```

После Edit — `Read` файл чтобы убедиться что обе функции на месте.

- [ ] **Step 4.5: Run filter tests, verify PASS**

```bash
.venv/bin/python -m pytest tests/services/telemost_recorder/test_participants_filter.py -v
```

Expected: 5 PASS.

- [ ] **Step 4.6: Update detect_meeting_ended to use filter on count badge**

Edit `services/telemost_recorder/join.py:241-249` — `detect_meeting_ended` использует participants count badge. Это число с UI Я.Телемоста, оно НЕ фильтруется по нашим bot names (там Telemost считает всех включая ботов). Нужно дополнительно дёрнуть `extract_participants` если badge показывает >1, чтобы проверить сколько остаётся **людей**.

Заменить блок `# Bot is alone: participant count badge shows "1"`:

```python
    # Count is dynamic — even if Telemost UI shows 2 participants,
    # they could be us + another bot. Pull names and filter.
    try:
        btn = page.locator("button").filter(has_text="Участники")
        badge_text = (await btn.first.text_content(timeout=500) or "")
        match = re.search(r"\d+", badge_text)
        if match:
            badge_count = int(match.group())
            if badge_count <= 1:
                return True
            # Badge > 1: pull names, filter bots, check if any humans remain.
            # We already exclude Wookiee Recorder; this also strips navstreche etc.
            human_names = await extract_participants(page)
            if not human_names:
                return True
    except Exception:
        pass

    return False
```

После Edit — `Read` файл, убедись что `re` всё ещё импортирован вверху, нет orphan-блоков старого кода.

- [ ] **Step 4.7: Run full recorder test suite, verify no regression**

```bash
.venv/bin/python -m pytest tests/services/telemost_recorder/ -q
```

Expected: все тесты PASS (including 5 новых).

- [ ] **Step 4.8: Commit**

```bash
git add services/telemost_recorder/config.py services/telemost_recorder/join.py tests/services/telemost_recorder/test_participants_filter.py
git commit -m "$(cat <<'EOF'
fix(telemost-recorder): exclude known bots from human-count for exit detection

extract_participants now filters KNOWN_BOT_NAMES (substring, case-insensitive).
detect_meeting_ended uses the filtered count: when participant badge > 1 but
no humans remain (only bots like navstreche.com or Wookiee Recorder), the
bot exits within 90 sec grace.

Previously meeting af19b95f wrote 92 min (host left after 50) because
navstreche.com AI assistant stayed in the call — recorder counted it as
a human and kept writing until ~92min hit hard limit / Telemost ended.

KNOWN_BOT_NAMES is a frozenset in config.py — add entries as new bots
appear in the team's call flow.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
git push origin main
```

- [ ] **Step 4.9: Rebuild recorder image (это recorder, не API)**

```bash
ssh timeweb 'cd /home/danila/projects/wookiee && git pull origin main && docker build -f deploy/Dockerfile.telemost_recorder -t telemost_recorder:latest . 2>&1 | tail -3'
```

Expected: `DONE`. Verify:
```bash
ssh timeweb 'docker run --rm telemost_recorder:latest python -c "from services.telemost_recorder.config import KNOWN_BOT_NAMES; print(sorted(KNOWN_BOT_NAMES))"'
```

Expected: список с `wookiee recorder`, `navstreche.com`, etc.

---

## Task 5: Bug #5 — parallel recorder spawn

**Цель:** Несколько meeting'ов записываются одновременно (до `MAX_PARALLEL_RECORDINGS`). Устраняет 32-40 мин задержку для второй параллельной встречи.

**Files:**
- Modify: `services/telemost_recorder_api/workers/recorder_worker.py`
- Test: `tests/services/telemost_recorder_api/test_recorder_worker.py`

- [ ] **Step 5.1: Write failing test для semaphore**

Add to `tests/services/telemost_recorder_api/test_recorder_worker.py`:

```python
@pytest.mark.asyncio
async def test_run_forever_spawns_up_to_max_parallel(monkeypatch):
    """When MAX_PARALLEL_RECORDINGS=3 and queue has 5 items, 3 should be spawned concurrently."""
    from services.telemost_recorder_api.workers import recorder_worker
    import asyncio

    monkeypatch.setattr(recorder_worker, "MAX_PARALLEL_RECORDINGS", 3)

    spawn_starts: list[asyncio.Event] = []
    active_count = {"n": 0, "max": 0}

    async def fake_process_one():
        active_count["n"] += 1
        active_count["max"] = max(active_count["max"], active_count["n"])
        ev = asyncio.Event()
        spawn_starts.append(ev)
        await ev.wait()
        active_count["n"] -= 1
        return True

    monkeypatch.setattr(recorder_worker, "process_one", fake_process_one)

    task = asyncio.create_task(recorder_worker.run_forever())
    # Wait until 3 starts captured
    for _ in range(50):
        if len(spawn_starts) >= 3:
            break
        await asyncio.sleep(0.05)
    assert active_count["max"] == 3, f"Expected 3 concurrent, got {active_count['max']}"

    # Release one, expect a 4th to start
    spawn_starts[0].set()
    for _ in range(50):
        if len(spawn_starts) >= 4:
            break
        await asyncio.sleep(0.05)
    assert len(spawn_starts) >= 4

    # Cleanup
    for ev in spawn_starts:
        ev.set()
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
```

- [ ] **Step 5.2: Run test, verify FAIL**

Run: `.venv/bin/python -m pytest tests/services/telemost_recorder_api/test_recorder_worker.py::test_run_forever_spawns_up_to_max_parallel -v --timeout=15`

Expected: FAIL — `active_count['max'] == 1` (текущий serial loop) или timeout если test wait долго.

- [ ] **Step 5.3: Refactor run_forever to use Semaphore**

Edit `services/telemost_recorder_api/workers/recorder_worker.py`. Заменить `run_forever` (около строки 189-204):

```python
async def run_forever() -> None:
    """Worker loop with bounded concurrency.

    Up to MAX_PARALLEL_RECORDINGS process_one() coroutines run in parallel.
    Each holds a semaphore slot for the full lifetime of one recorder
    container (spawn → monitor → finalize), so memory/CPU caps on the host
    bound the slot count.
    """
    sem = asyncio.Semaphore(MAX_PARALLEL_RECORDINGS)
    logger.info(
        "Recorder worker starting (max_parallel=%d, hard_limit=%dh)",
        MAX_PARALLEL_RECORDINGS,
        RECORDING_HARD_LIMIT_HOURS,
    )

    async def _slot_runner() -> None:
        while True:
            async with sem:
                try:
                    processed = await process_one()
                except Exception:  # noqa: BLE001
                    logger.exception("recorder_worker.process_one crashed")
                    processed = False
            await asyncio.sleep(
                _BUSY_SLEEP_SECONDS if processed else _IDLE_SLEEP_SECONDS
            )

    runners = [asyncio.create_task(_slot_runner()) for _ in range(MAX_PARALLEL_RECORDINGS)]
    try:
        await asyncio.gather(*runners)
    finally:
        for r in runners:
            r.cancel()
```

После Edit — `Read` файл, убедись что `asyncio` импортирован, нет orphan кода.

- [ ] **Step 5.4: Run test, verify PASS + no regression**

```bash
.venv/bin/python -m pytest tests/services/telemost_recorder_api/test_recorder_worker.py -v --timeout=15
.venv/bin/python -m pytest tests/services/telemost_recorder/ tests/services/telemost_recorder_api/ -q
```

Expected: новый PASS, остальные без регрессий.

- [ ] **Step 5.5: Commit**

```bash
git add services/telemost_recorder_api/workers/recorder_worker.py tests/services/telemost_recorder_api/test_recorder_worker.py
git commit -m "$(cat <<'EOF'
feat(telemost-api): run recorder_worker with bounded concurrency

run_forever now spawns MAX_PARALLEL_RECORDINGS coroutine-slots, each
holding a semaphore for the full lifetime of one recording. Multiple
queued meetings spawn in parallel instead of waiting serially.

Default MAX_PARALLEL_RECORDINGS stays at 1 (env-controlled). Bumping
to 3 in .env unlocks parallel handling without code changes.

Closes the 32-40 min lag seen when two meetings were submitted within
the same hour (second meeting waited for first to finish).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
git push origin main
```

- [ ] **Step 5.6: Set MAX_PARALLEL_RECORDINGS=3 in server .env**

```bash
ssh timeweb 'grep -q "^MAX_PARALLEL_RECORDINGS=" /home/danila/projects/wookiee/.env && sed -i "s/^MAX_PARALLEL_RECORDINGS=.*/MAX_PARALLEL_RECORDINGS=3/" /home/danila/projects/wookiee/.env || echo "MAX_PARALLEL_RECORDINGS=3" >> /home/danila/projects/wookiee/.env'
ssh timeweb 'grep "MAX_PARALLEL_RECORDINGS" /home/danila/projects/wookiee/.env'
```

Expected: `MAX_PARALLEL_RECORDINGS=3`.

- [ ] **Step 5.7: Deploy API**

```bash
ssh timeweb 'cd /home/danila/projects/wookiee && git pull origin main && cd deploy && docker compose up -d --build telemost-recorder-api'
ssh timeweb 'docker logs --tail 5 telemost_recorder_api 2>&1 | grep "Recorder worker starting"'
```

Expected: `max_parallel=3`.

---

## Task 6: E2E verification — полный pipeline live

**Цель:** Подтвердить что свежая встреча проходит весь pipeline без вмешательства — от Telegram ссылки до DM с реальным LLM-summary.

**Files:** нет изменений, только верификация.

- [ ] **Step 6.1: Подготовить тестовую встречу**

User opens `https://telemost.360.yandex.ru/j/5655083346` или новую meeting URL и держит её открытой 5 минут.

User отправляет ссылку боту `@wookiee_recorder_bot` (или INSERT в telemost.meetings через MCP Supabase с `triggered_by=252698672`).

- [ ] **Step 6.2: Watch recorder spawn**

```bash
ssh timeweb 'docker ps --filter ancestor=telemost_recorder:latest --format "{{.ID}} {{.Status}} {{.Names}}"'
```

Expected: новый `telemost_rec_<id>` Up X seconds в течение 60 sec после отправки.

- [ ] **Step 6.3: Verify env in spawned container (sanity)**

```bash
ssh timeweb 'docker inspect <container_id> | jq ".[0].Config.Env" | grep TELEMOST_HEADLESS'
```

Expected: `TELEMOST_HEADLESS=false`.

- [ ] **Step 6.4: Verify chrome (not chrome-headless-shell) в PA логах**

После ~60 sec:
```bash
ssh timeweb 'docker logs <container_id> 2>&1 | grep "PA\[reroute-tick\]" | tail -3'
```

Expected: в `clients:` фигурирует `chrome`, НЕ `chrome-headless-shell`.

- [ ] **Step 6.5: User говорит 90+ сек, потом выходит**

Recorder должен сам обнаружить уход людей (после Task 4 — учитывая и других ботов) и завершиться через ~90 сек grace.

- [ ] **Step 6.6: Verify raw_segments на диске + в БД**

```bash
ssh timeweb 'ls -la /home/danila/projects/wookiee/data/telemost/<id>/ | grep -E "audio.opus|raw_segments|transcript"'
```

Expected: `audio.opus` > 250 КБ + `raw_segments.json` присутствует + `transcript.json` + `transcript.txt`.

```sql
SELECT status, jsonb_array_length(raw_segments) AS segs,
       summary->'topics' AS topics, summary->'tasks' AS tasks,
       notified_at IS NOT NULL AS notified
FROM telemost.meetings WHERE id='<meeting_id>';
```

Expected: `status='done'`, `segs > 0`, `topics` непустое, `notified=true`.

- [ ] **Step 6.7: User получает DM с реальным summary**

User проверяет в Telegram chat с `@wookiee_recorder_bot`: новый DM должен содержать summary с темами, задачами, не «тишина», не «попытка восстановления не удалась».

- [ ] **Step 6.8: Acceptance — все 4 бага закрыты**

Заполнить чек-лист:
- [ ] LLM не упал на длинной встрече (нет `LLMPostprocessError`)
- [ ] notified_at установлен после первого notify, не блокирует если статус снова `postprocessing`
- [ ] Recorder вышел через ≤90 сек после ухода последнего человека (даже если другие боты остались)
- [ ] Если в очереди ≥2 meeting — обе обрабатываются параллельно

Если что-то не закрыто — вернуться к соответствующему Task и доделать.

---

## Self-review notes

**Coverage check:**
- Bug #3 → Task 1 ✅
- Bug #4 → Task 2 ✅
- Recovery `af19b95f` + `36fc0387` → Task 3 ✅ (зависит от Task 1+2)
- Bug #6 → Task 4 ✅
- Bug #5 → Task 5 ✅
- E2E proof → Task 6 ✅

**Ordering rationale:** Task 1 (LLM) и Task 2 (notifier) — prerequisites для Task 3 (recovery) потому что без них recovery не выдаст полезный DM. Task 4 и Task 5 — независимы от 1-3, можно делать в любом порядке после, но Task 4 раньше потому что без него уже идущий `36fc0387` мог бы упереться в hard-limit. Task 6 — последняя.

**Risk callouts:**
- Step 4.6 (изменение `detect_meeting_ended`) меняет user-facing поведение — нужно убедиться что `extract_participants` не вызывается слишком часто (open/close panel создаёт visual flicker в UI; сейчас вызов происходит только когда badge > 1, не каждый tick).
- Step 5.3 (semaphore) — если `process_one()` зависнет (например, ASR залип), весь slot заблокирован до timeout. Существующий `RECORDING_HARD_LIMIT_HOURS` спасает, но для ASR-stage нет hard timeout — это отдельный Phase 2 риск, в этот план не входит.
- Task 3 предполагает что recorder image на сервере уже включает `09f597c` (fix raw_segments.json). Для уже запущенного `36fc0387` это не так — он на старом образе. Recovery скрипт читает `transcript.json` как fallback, так что это закрыто.

**Out of scope (плановых задач):**
- Hard timeout на ASR-stage (отдельный фикс при необходимости).
- Прогрессивные DM-уведомления (`recording started`, `transcribing`, `done`) — UX improvement, не bug.
- Хранение audio.opus в Supabase Storage с TTL — `audio_uploader` уже есть, расширение retention — отдельный story.
