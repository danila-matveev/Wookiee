"""Single-call Gemini Flash postprocessing through OpenRouter."""
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
    """Raised when LLM output cannot be parsed or fails schema validation."""


_PROMPT_TEMPLATE = """Ты — редактор расшифровок встреч бренда Wookiee (нижнее бельё на Wildberries и OZON). На вход — сегменты ASR (Yandex SpeechKit) с диаризацией и список участников. Ты должен выполнить ровно 5 задач и вернуть строго один JSON-объект без любого текста до или после.

1. Склей соседние короткие чанки одного спикера в смысловые абзацы (paragraphs). Сохраняй порядок.
2. Восстанови пунктуацию и регистр на естественном русском языке. Исправляй явные ошибки распознавания (например, "венди" → "Wendy", если по контексту это название модели). Не выдумывай факты.
3. Сопоставь каждого "Speaker N" из ASR с реальным именем участника из списка Participants на основе содержания реплик. Верни маппинг в speakers_map. Если не уверен — оставь "Speaker N" как есть.
4. Подбери теги встречи (tags) ТОЛЬКО из канонического списка: креативы, реклама, маркетинг, продажи, разработка, отчётность, HR, финансы, ассортимент, поставки, логистика, упаковка, бренд, маркетплейс, конкуренты, аналитика, продукт, контент, операции, прочее. От 1 до 6 наиболее релевантных.
5. Сформируй summary: список участников (по именам), темы с якорями вида "[MM:SS]", принятые решения, поставленные задачи (assignee/what/when).

Формат ответа — строго JSON следующей формы (никаких markdown-обёрток, никаких комментариев):

{{
  "paragraphs": [
    {{"speaker": "<имя или Speaker N>", "start_ms": <int>, "text": "<текст абзаца>"}}
  ],
  "speakers_map": {{"Speaker 0": "<имя или Speaker 0>"}},
  "tags": ["<тег>", "..."],
  "summary": {{
    "participants": ["<имя>", "..."],
    "topics": [{{"title": "<тема>", "anchor": "[MM:SS]"}}],
    "decisions": ["<решение>", "..."],
    "tasks": [{{"assignee": "<имя>", "what": "<что сделать>", "when": "<срок или null>"}}]
  }}
}}

Participants:
{participants}

Segments:
{segments}
"""


def build_prompt(segments: list[dict], participants: list[dict]) -> str:
    """Render the LLM prompt for given ASR segments and meeting participants."""
    seg_text = "\n".join(
        f"[{s['start_ms'] // 1000:>4}s {s['speaker']}] {s['text']}" for s in segments
    )
    p_text = "\n".join(f"- {p['name']}" for p in participants) or "(нет данных)"
    return _PROMPT_TEMPLATE.format(participants=p_text, segments=seg_text)


def _strip_markdown_codefence(text: str) -> str:
    """Remove a surrounding ```json ... ``` (or ``` ... ```) fence, if any."""
    stripped = text.strip()
    match = re.match(r"^```(?:json)?\s*(.*?)\s*```$", stripped, re.DOTALL)
    if match:
        return match.group(1)
    return stripped


async def _call_openrouter(prompt: str, model: str, timeout_seconds: int) -> str:
    """POST a single chat completion to OpenRouter and return the assistant content."""
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
        "max_tokens": 16000,
        "response_format": {"type": "json_object"},
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
    """Validate the top-level and summary keys; raise LLMPostprocessError on mismatch."""
    required_top = {"paragraphs", "speakers_map", "tags", "summary"}
    missing_top = required_top - set(data.keys())
    if missing_top:
        raise LLMPostprocessError(f"missing keys: {sorted(missing_top)}")

    summary = data["summary"]
    if not isinstance(summary, dict):
        raise LLMPostprocessError("summary must be an object")
    required_summary = {"participants", "topics", "decisions", "tasks"}
    missing_summary = required_summary - set(summary.keys())
    if missing_summary:
        raise LLMPostprocessError(f"missing summary keys: {sorted(missing_summary)}")


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
