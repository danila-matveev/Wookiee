import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from services.telemost_recorder_api.llm_postprocess import (
    build_prompt,
    postprocess_meeting,
    _call_openrouter,
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


def test_build_prompt_contains_wookiee_glossary():
    """Без глоссария LLM возвращает 'венди'/'мун' кириллицей и теряет привязку к моделям."""
    prompt = build_prompt(
        [{"speaker": "Speaker 0", "start_ms": 0, "end_ms": 1000, "text": "x"}],
        [{"name": "Данила"}],
    )
    for model_name in ("Wendy", "Moon", "Vuki", "Ruby", "Joy"):
        assert model_name in prompt, f"Glossary must mention {model_name}"
    assert "Модели бренда" in prompt or "модел" in prompt.lower()


def test_build_prompt_contains_ecom_marketplace_glossary():
    """E-com термины (СПП, ДРР, выкуп, оборачиваемость) и MP-канал должны быть в промте."""
    prompt = build_prompt(
        [{"speaker": "Speaker 0", "start_ms": 0, "end_ms": 1000, "text": "x"}],
        [{"name": "Данила"}],
    )
    for term in ("СПП", "ДРР", "Wildberries", "FBO", "выкуп", "оборачиваемост"):
        assert term in prompt, f"Glossary must mention {term}"


def test_build_prompt_requires_extended_tasks_schema():
    """Промт должен явно требовать развёрнутые поля context+conditions в tasks."""
    prompt = build_prompt(
        [{"speaker": "Speaker 0", "start_ms": 0, "end_ms": 1000, "text": "x"}],
        [{"name": "Данила"}],
    )
    assert "context" in prompt
    assert "conditions" in prompt


def test_build_prompt_focuses_on_obligations_not_quotas():
    """Главная философия: ловить обещания/обязательства, а не выполнять квоты по темам."""
    prompt = build_prompt(
        [{"speaker": "Speaker 0", "start_ms": 0, "end_ms": 1000, "text": "x"}],
        [{"name": "Данила"}],
    )
    # No hard quota on topic count
    assert "5-15" not in prompt
    # Must mention obligations/promises/forgotten items
    obligation_signals = ("обещан", "обязательств", "забы", "не забы")
    assert any(s in prompt.lower() for s in obligation_signals), (
        "Prompt must instruct LLM to catch promises and prevent forgotten items"
    )
    # Must reference Bitrix downstream so the LLM frames tasks for ticket creation
    assert "Bitrix" in prompt or "bitrix" in prompt.lower()


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
    async def fake_call(prompt, model, timeout_seconds):
        return '```json\n{"paragraphs":[],"speakers_map":{},"tags":[],"summary":{"participants":[],"topics":[],"decisions":[],"tasks":[]}}\n```'

    with patch(
        "services.telemost_recorder_api.llm_postprocess._call_openrouter",
        AsyncMock(side_effect=fake_call),
    ):
        result = await postprocess_meeting([], [])

    assert result["paragraphs"] == []
    assert result["summary"]["participants"] == []


@pytest.mark.asyncio
async def test_call_openrouter_includes_max_tokens_and_json_mode():
    """Body must request response_format=json_object and max_tokens=16000 to prevent truncation."""
    captured = {}

    def _handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.content.decode()
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"ok": true}'}}]},
        )

    transport = httpx.MockTransport(_handler)
    real_async_client = httpx.AsyncClient

    def _client_factory(*args, **kwargs):
        kwargs["transport"] = transport
        return real_async_client(*args, **kwargs)

    with patch(
        "services.telemost_recorder_api.llm_postprocess.httpx.AsyncClient",
        side_effect=_client_factory,
    ):
        await _call_openrouter("test prompt", "google/gemini-3-flash-preview", 30)

    body = json.loads(captured["body"])
    assert body["max_tokens"] == 16000
    assert body["response_format"] == {"type": "json_object"}


@pytest.mark.asyncio
async def test_postprocess_meeting_chunked_for_large_segments():
    """For >150 segments, do two LLM calls and merge results (summary+tags first, paragraphs+speakers_map second)."""
    call_count = {"n": 0}
    summary_response = {
        "tags": ["продажи", "маркетинг"],
        "summary": {
            "participants": ["Данила"],
            "topics": [{"title": "Итоги недели", "anchor": "[00:00]"}],
            "decisions": ["Запустить тест креативов"],
            "tasks": [{"assignee": "Данила", "what": "оптимизировать рекламу", "when": None}],
        },
    }
    paragraphs_response = {
        "paragraphs": [{"speaker": "Speaker 0", "start_ms": 0, "text": "Привет команде"}],
        "speakers_map": {"Speaker 0": "Данила"},
    }

    async def fake_call(prompt, model, timeout_seconds):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return json.dumps(summary_response, ensure_ascii=False)
        return json.dumps(paragraphs_response, ensure_ascii=False)

    segments = [
        {"speaker": "Speaker 0", "start_ms": i * 1000, "end_ms": (i + 1) * 1000, "text": "test"}
        for i in range(160)
    ]
    participants = [{"name": "Данила"}]

    with patch(
        "services.telemost_recorder_api.llm_postprocess._call_openrouter",
        AsyncMock(side_effect=fake_call),
    ):
        result = await postprocess_meeting(segments, participants)

    assert call_count["n"] == 2
    assert "paragraphs" in result and result["paragraphs"][0]["text"] == "Привет команде"
    assert result["speakers_map"] == {"Speaker 0": "Данила"}
    assert result["tags"] == ["продажи", "маркетинг"]
    assert result["summary"]["topics"][0]["title"] == "Итоги недели"


@pytest.mark.asyncio
async def test_postprocess_meeting_chunked_paragraphs_failure_returns_summary_only():
    """If paragraphs chunk fails (e.g. truncated JSON), return summary+tags with empty paragraphs."""
    summary_response = {
        "tags": ["продажи"],
        "summary": {
            "participants": ["Данила"],
            "topics": [{"title": "Итоги", "anchor": "[00:00]"}],
            "decisions": [],
            "tasks": [],
        },
    }

    call_count = {"n": 0}

    async def fake_call(prompt, model, timeout_seconds):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return json.dumps(summary_response, ensure_ascii=False)
        # Mimic truncated paragraphs output (unterminated string)
        return '{"paragraphs": [{"speaker": "Speaker 0", "start_ms": 0, "text": "Hello world... <truncated mid-string'

    segments = [
        {"speaker": "Speaker 0", "start_ms": i * 1000, "end_ms": (i + 1) * 1000, "text": "test"}
        for i in range(160)
    ]
    participants = [{"name": "Данила"}]

    with patch(
        "services.telemost_recorder_api.llm_postprocess._call_openrouter",
        AsyncMock(side_effect=fake_call),
    ):
        result = await postprocess_meeting(segments, participants)

    assert call_count["n"] == 2
    assert result["tags"] == ["продажи"]
    assert result["summary"]["topics"][0]["title"] == "Итоги"
    assert result["paragraphs"] == []  # fallback
    assert result["speakers_map"] == {}  # fallback


@pytest.mark.asyncio
async def test_postprocess_meeting_chunked_paragraphs_http_error_returns_summary_only():
    """If paragraphs chunk raises httpx.HTTPError, fall back to empty paragraphs + keep summary."""
    summary_response = {
        "tags": ["финансы"],
        "summary": {
            "participants": ["Данила"],
            "topics": [{"title": "Бюджет", "anchor": "[00:00]"}],
            "decisions": [],
            "tasks": [],
        },
    }

    call_count = {"n": 0}

    async def fake_call(prompt, model, timeout_seconds):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return json.dumps(summary_response, ensure_ascii=False)
        raise httpx.ReadTimeout("paragraphs call timed out")

    segments = [
        {"speaker": "Speaker 0", "start_ms": i * 1000, "end_ms": (i + 1) * 1000, "text": "test"}
        for i in range(160)
    ]

    with patch(
        "services.telemost_recorder_api.llm_postprocess._call_openrouter",
        AsyncMock(side_effect=fake_call),
    ):
        result = await postprocess_meeting(segments, [{"name": "Данила"}])

    assert call_count["n"] == 2
    assert result["tags"] == ["финансы"]
    assert result["summary"]["topics"][0]["title"] == "Бюджет"
    assert result["paragraphs"] == []
    assert result["speakers_map"] == {}


@pytest.mark.asyncio
async def test_prompt_includes_invitee_names_end_to_end():
    """Bitrix-enriched invitees from meetings.invitees must reach the LLM prompt.

    Pins the Task 3 contract: postprocess_meeting(segments, participants) — where
    `participants` is the JSON-decoded meetings.invitees list — surfaces every
    invitee name into the user-message sent to OpenRouter. Speaker attribution
    in the LLM output depends on this; missing names degrade processed_paragraphs
    back to "Speaker N".
    """
    captured: dict = {}

    async def fake_call(prompt, model, timeout_seconds):
        captured["prompt"] = prompt
        return json.dumps({
            "paragraphs": [],
            "speakers_map": {},
            "tags": [],
            "summary": {
                "participants": [], "topics": [], "decisions": [], "tasks": [],
            },
        })

    segments = [{"speaker": "Speaker 0", "start_ms": 0, "end_ms": 1000, "text": "Привет"}]
    invitees = [
        {"telegram_id": 111, "name": "Иван Иванов", "bitrix_id": "1"},
        {"telegram_id": 222, "name": "Алина А.", "bitrix_id": "42"},
    ]

    with patch(
        "services.telemost_recorder_api.llm_postprocess._call_openrouter",
        AsyncMock(side_effect=fake_call),
    ):
        await postprocess_meeting(segments, invitees)

    prompt = captured["prompt"]
    assert "Иван Иванов" in prompt
    assert "Алина А." in prompt
    assert "Participants:" in prompt
