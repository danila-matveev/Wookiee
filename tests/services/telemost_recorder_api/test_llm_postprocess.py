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
    async def fake_call(prompt, model, timeout_seconds):
        return '```json\n{"paragraphs":[],"speakers_map":{},"tags":[],"summary":{"participants":[],"topics":[],"decisions":[],"tasks":[]}}\n```'

    with patch(
        "services.telemost_recorder_api.llm_postprocess._call_openrouter",
        AsyncMock(side_effect=fake_call),
    ):
        result = await postprocess_meeting([], [])

    assert result["paragraphs"] == []
    assert result["summary"]["participants"] == []
