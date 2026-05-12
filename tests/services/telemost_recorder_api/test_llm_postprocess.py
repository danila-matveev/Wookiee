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
