"""Gemini Flash postprocessing through OpenRouter (single-call or chunked for long meetings)."""
from __future__ import annotations

import asyncio
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


# ============================================================================
# Глоссарии — нормализуют написание моделей и e-com/marketplace терминов.
# Русский SpeechKit транскрибирует латинские названия кириллицей ("венди",
# "мун", "вуки") и коверкает узкоспециальные термины ("оборачиваемость",
# "выкупаемость"). LLM получает эти словари и возвращает каноничное написание.
# ============================================================================

_WOOKIEE_MODELS = (
    "Alice", "Angelina", "Ashley", "Aspen", "Audrey", "Bella", "Berlin",
    "Bille", "Carol", "Charlotte", "Diana", "Duo", "Emma", "Eva", "Evelyn",
    "Jackie", "Jane", "Jess", "Joy", "Kat", "Kerry", "Kira", "Kylie", "Lana",
    "Linda", "Luna", "Margo", "Meg", "Mia", "Miafull", "Miami", "Moon",
    "Nancy", "Nicole", "Nora", "Oslo", "Paris", "Polly", "Rio", "Rose",
    "Ruby", "Sabrina", "Sally", "Sky", "Space", "Tina", "Valery", "Viola",
    "Vita", "Vuki", "Wendy",
)


_GLOSSARY_BLOCK = """ГЛОССАРИИ — нормализуй написание по этим словарям.

1) Модели бренда Wookiee (нижнее бельё, на латинице):
{models}.
Если в речи звучит женское имя, фонетически похожее на модель ("венди" → Wendy, "мун" → Moon, "руби" → Ruby, "вуки" → Vuki, "джой" → Joy, "белла" → Bella, "мия" → Mia, "ева" → Eva, "люна" → Luna, "айви" → Joy/Vuki по контексту), и контекст про товар/коллекцию/артикул/съёмку/карточку — это название модели, верни на латинице. Если контекст про человека (задача / роль / ответственный) — это участник встречи, бери имя из Participants.

2) Маркетплейсы и каналы:
- WB = Wildberries (Вайлдберриз, ВБ, Вайлдберис → WB). OZON = Ozon (Озон). YM = Яндекс Маркет.
- FBO / FBS / DBS / realFBS — модели работы со складом маркетплейса.
- MP / маркетплейс — обобщённо.

3) Продажи и юнит-экономика:
- СПП — скидка постоянного покупателя (часто звучит как "эс-пэ-пэ", "спп", "процент спп").
- ДРР — доля рекламных расходов (внутр. ДРР = WB-реклама, внешний ДРР = блогеры/ВК).
- ДДС — движение денежных средств.
- Выкуп / выкупаемость / процент выкупа — доля заказов, доехавших до клиента.
- Возврат / возвратность — обратная метрика.
- Оборачиваемость (часто "оборачка") — скорость продажи остатка.
- Маржа / маржинальность / валовая прибыль / чистая прибыль.
- AOV (Average Order Value), GMV, LTV — стандартные финансовые метрики.
- ABC-анализ, ABC-аудит, артикулы группы A/B/C.
- Каннибализация — когда модели "съедают" продажи друг друга.

4) Карточка и ассортимент:
- Карточка (товара) / nm-id / SKU / артикул / артикул модели — НЕ путать с задачей "написать карточку".
- Слипы, лиф, бандо, рашгард, бесшовка, лонгслив, выстиранки, принты, набор (комплект) — типы изделий.
- Размерная сетка / российский размер / международный размер.

5) Реклама и трафик:
- CTR (Click-Through Rate), CPM (Cost Per Mille), CPC (Cost Per Click), CR (Conversion Rate).
- Воронка — путь от показа до выкупа.
- Ранжирование / поисковая выдача / позиции / топ выдачи.
- Семантика / запросы / ключевые слова / частотность.
- Креативы / связки / гипотезы — рекламные единицы.
- Промокоды / акции / распродажи / промокарта.

6) Контент:
- Reels / рилсы, Stories / сторис, Shorts, видосы, тиктоки, монтаж, нарезка.
- Блогеры / интеграции / бартер / ТЗ блогеру / медиаплан.
- Съёмка / съёмочный день / референсы / лукбук.

7) Операции и поставки:
- Поставка / отгрузка / приёмка / коробки / упаковка / маркировка / КИЗ.
- Остатки / неликвид / overstock / out-of-stock / OOS.
- Швейка / производство / фабрика / тираж / партия.

ВАЖНО: если ASR произнёс термин искажённо ("сипипи" → СПП, "дэирэр" → ДРР, "оборотка" → оборачиваемость, "вайлдбериз" → WB), восстанавливай в каноничном виде. Имена УЧАСТНИКОВ встречи бери ТОЛЬКО из списка Participants — не путай их с моделями.
""".format(models=", ".join(_WOOKIEE_MODELS))


_QUALITY_STANDARDS = """КАК ТЫ РАБОТАЕШЬ — философия:

Ты — не стенографист и не SEO-копирайтер. Ты — внимательный коллега, который сидел рядом всю встречу. Твоя цель: чтобы после прочтения summary никто из команды не сказал "а мы же говорили про X, а тут этого нет" или "забыл, что я обещал Y сделать". Конкретные задачи, которые прозвучали — твоя главная находка, они потом пойдут в Bitrix24 как карточки задач.

ПРОПОРЦИОНАЛЬНОСТЬ ДЛИНЕ ВСТРЕЧИ. Это критично. Смотри на длительность транскрипта и количество сегментов:
— Если запись короткая (≤ 5 минут или ≤ 20 сегментов): summary должен быть пропорционально коротким. 1-2 темы максимум. Решения — только если реально прозвучало "решили X". Задачи — только если реально кто-то сказал "я сделаю Y". context/conditions — почти всегда null на короткой встрече, потому что просто не было времени их обсудить.
— Если в записи мало содержания и много "проверки связи" / тестового / болтовни — summary должен это отражать. Не натягивай встречу на сетку "1-2 часа бизнес-встречи".
— Если встреча длинная и насыщенная — детализируй сколько нужно.

ОТЛИЧАЙ SUITT TALK ОТ СУТИ. "Я сегодня плохо спал из-за ночной няни", "Как погода?", "Как выходные?", анекдоты, истории про детей/пробки/еду — это разогрев, НЕ тема встречи. Не превращай их в topics, не делай из них задачи. Тема встречи — это бизнес-вопрос с явным предметом обсуждения. Если вся "встреча" — это smalltalk без бизнеса, верни одну тему типа "Smalltalk / разогрев перед основной встречей" и оставь decisions/tasks пустыми.

НЕ ВЫДУМЫВАЙ. Если context (зачем задача) не звучал в речи — ставь null. Если conditions (от чего зависит) не звучали — null. Лучше задача с null-полями чем выдуманный бизнес-эффект, которого никто не озвучивал. То же про participants — если в речи человек не назван по имени и его невозможно связать с Participants, оставь "Speaker N".

Не подгоняй под шаблон. Если встреча была короткая и по одной теме — пусть будет одна тема. Если на длинной встрече реально обсуждали 12 вопросов — фиксируй 12. Количество — следствие содержания, а не норма.

Что обязательно вылавливай:

— ОБЕЩАНИЯ И ОБЯЗАТЕЛЬСТВА. Любое "я сделаю", "я возьмусь", "я подумаю", "я договорюсь", "я отправлю" — это задача, даже если без срока. Особенно ловишь моменты типа "ой, точно, надо ещё...", "забыли про...", "напомните мне про...". Это первые кандидаты в задачи, потому что именно их и забывают.

— ЦИФРЫ И ПАРАМЕТРЫ. Любые конкретные цифры (цены, проценты, бюджеты, СПП, ДРР, объёмы партий, сроки, размеры, ставки блогерам, нормативы) — фиксируй дословно с пояснением что это за число. "Решили СПП 35%" — слабо. "Решили поднять СПП на модели Wendy с 25% до 35% с понедельника 19.05, чтобы выровнять позицию против конкурента Lounge" — нормально.

— ИМЕНА МОДЕЛЕЙ. Любая модель, которая прозвучала (по глоссарию ниже), должна попасть в summary либо в topics либо в задачах. Это ключевые объекты бизнеса — терять их нельзя.

— РИСКИ И УСЛОВНОСТИ. "Только если...", "при условии что...", "если не успеем...", "может не получиться потому что..." — это conditions у задач или отдельный декорум в decisions. Их теряют чаще всего.

— ОТЛОЖЕННЫЕ ВОПРОСЫ. "Давай вернёмся к этому в следующий раз", "это надо обсудить с Z отдельно", "это не сегодня" — фиксируй как отдельную задачу с when=null и context="отложили".

ПОЛЯ SUMMARY:

— participants: реальные имена из Participants/speakers_map, без "Speaker N".

— topics: ёмкие фразы по сути, каждая со своим anchor "[MM:SS]". НЕ "обсуждение продаж", НЕ "вопросы команды". Если темы повторно всплывают — объединяй в одну с самым ранним anchor.

— decisions: только то, что было РЕАЛЬНО решено — не предложено, не обсуждено. Формулировка как для протокола: "решили X", "отказались от Y потому что Z", "согласовали бюджет N на M". Если ни одного решения не приняли — пустой массив (бывает).

— tasks: КАЖДОЕ обязательство, прозвучавшее в речи, отдельной карточкой. Формат рассчитан на автоматическую заливку в Bitrix24:
  * assignee — имя ответственного из Participants. Если не назначили явно — поставь "—" или того, кто высказал "я сделаю".
  * what — формулировка в повелительном наклонении ("подготовить ТЗ", "созвониться с подрядчиком", "проверить остатки"), затем точные параметры и контекст. Так чтобы исполнитель открыл задачу в Bitrix и сразу понял что делать без переспрашивания. Если в речи звучали цифры/ссылки/референсы — впихивай.
  * when — срок если прозвучал явно ("до 20.05", "к пятнице", "после съёмки 18-го") или null. Не выдумывай.
  * context — 1 предложение "зачем", если из речи понятно. Бизнес-эффект, проблема, гипотеза. null если в речи мотивации не было.
  * conditions — то, без чего задачу нельзя начинать или что её блокирует ("после согласования бюджета", "если ткань придёт", "при условии что блогер согласится"). null если безусловная.
"""


_TAG_CATALOG = (
    "креативы, реклама, маркетинг, продажи, разработка, отчётность, HR, финансы, "
    "ассортимент, поставки, логистика, упаковка, бренд, маркетплейс, конкуренты, "
    "аналитика, продукт, контент, операции, прочее"
)


_PROMPT_TEMPLATE = """Ты — помощник на бизнес-встрече бренда Wookiee (нижнее бельё на Wildberries и OZON). Представь, что ты внимательный коллега, который весь созвон сидел и слушал, а теперь должен передать команде главное, чтобы никто ничего не забыл. Особенно — кто что обещал сделать. На вход — сегменты ASR (Yandex SpeechKit) с диаризацией и список участников. Верни строго один JSON-объект, без любого текста до или после.

ЧТО ТЫ ДОЛЖЕН СДЕЛАТЬ:

1) Paragraphs — склей соседние короткие чанки одного спикера в смысловые абзацы, сохраняй порядок. Восстанови пунктуацию и регистр на естественном русском. Исправляй явные ошибки распознавания по глоссариям ниже. Не выдумывай факты, которых нет в записи.

2) Speakers map — сопоставь каждого "Speaker N" с реальным именем участника из Participants по содержанию реплик (кто что говорит, к кому обращается, на чьи задачи ссылается). Если в встрече реально один спикер из списка — смело назначай его всем "Speaker N". Если по конкретному "Speaker N" не уверен — оставь как есть.

3) Tags — 1-6 наиболее релевантных тематических из канонического списка: {tags}.

4) Summary — главный артефакт встречи, на нём команда живёт после созвона.

{quality}

{glossary}

ФОРМАТ ОТВЕТА — строго JSON следующей формы (никаких markdown-обёрток, никаких комментариев):

{{
  "paragraphs": [
    {{"speaker": "<имя или Speaker N>", "start_ms": <int>, "text": "<текст абзаца>"}}
  ],
  "speakers_map": {{"Speaker 0": "<имя или Speaker 0>"}},
  "tags": ["<тег>", "..."],
  "summary": {{
    "title": "<короткое название встречи 3-7 слов из сути обсуждения, без даты и без кавычек>",
    "participants": ["<имя>", "..."],
    "topics": [{{"title": "<тема>", "anchor": "[MM:SS]"}}],
    "decisions": ["<решение>", "..."],
    "tasks": [
      {{
        "assignee": "<имя>",
        "what": "<развёрнутое описание задачи>",
        "when": "<срок или null>",
        "context": "<зачем эта задача или null>",
        "conditions": "<условности или null>"
      }}
    ]
  }}
}}

Participants:
{participants}

Segments:
{segments}
""".replace("{tags}", _TAG_CATALOG).replace("{quality}", _QUALITY_STANDARDS).replace("{glossary}", _GLOSSARY_BLOCK)


def _render_inputs(segments: list[dict], participants: list[dict]) -> tuple[str, str]:
    """Render segments and participants into the prompt-ready text blocks."""
    seg_text = "\n".join(
        f"[{s['start_ms'] // 1000:>4}s {s['speaker']}] {s['text']}" for s in segments
    )
    p_text = "\n".join(f"- {p['name']}" for p in participants) or "(нет данных)"
    return seg_text, p_text


def build_prompt(segments: list[dict], participants: list[dict]) -> str:
    """Render the LLM prompt for given ASR segments and meeting participants."""
    seg_text, p_text = _render_inputs(segments, participants)
    return _PROMPT_TEMPLATE.format(participants=p_text, segments=seg_text)


def _strip_markdown_codefence(text: str) -> str:
    """Remove a surrounding ```json ... ``` (or ``` ... ```) fence, if any."""
    stripped = text.strip()
    match = re.match(r"^```(?:json)?\s*(.*?)\s*```$", stripped, re.DOTALL)
    if match:
        return match.group(1)
    return stripped


_OPENROUTER_RETRIES = 3
_OPENROUTER_BACKOFF_BASE = 2.0


async def _call_openrouter(prompt: str, model: str, timeout_seconds: int) -> str:
    """POST a single chat completion to OpenRouter and return the assistant content.

    Retries on 429 / 5xx / network errors with exponential backoff so transient
    rate-limit blips don't fail an entire meeting post-process.
    """
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
    last_error: Exception | None = None
    for attempt in range(_OPENROUTER_RETRIES):
        try:
            async with httpx.AsyncClient(timeout=timeout_seconds) as client:
                resp = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers=headers,
                    json=body,
                )
            if resp.status_code == 429 or resp.status_code >= 500:
                last_error = httpx.HTTPStatusError(
                    f"OpenRouter {resp.status_code}: {resp.text[:200]}",
                    request=resp.request,
                    response=resp,
                )
                logger.warning(
                    "OpenRouter %s on attempt %d/%d, will retry",
                    resp.status_code, attempt + 1, _OPENROUTER_RETRIES,
                )
            else:
                resp.raise_for_status()
                data = resp.json()
                return data["choices"][0]["message"]["content"]
        except httpx.HTTPError as e:
            last_error = e
            logger.warning(
                "OpenRouter network error on attempt %d/%d: %s",
                attempt + 1, _OPENROUTER_RETRIES, e,
            )
        if attempt < _OPENROUTER_RETRIES - 1:
            await asyncio.sleep(_OPENROUTER_BACKOFF_BASE * (2 ** attempt))
    assert last_error is not None
    raise LLMPostprocessError(f"OpenRouter unavailable after retries: {last_error}")


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


# Empirical: OpenRouter output truncated at ~230 segments / 30K chars on meeting af19b95f.
# Halved with safety margin so a typical 1h meeting at ~150 segments stays on the
# single-call fast path while longer meetings auto-split.
_CHUNK_THRESHOLD = 150


_PROMPT_SUMMARY_ONLY = """Ты — помощник на бизнес-встрече бренда Wookiee (нижнее бельё на Wildberries и OZON). Внимательный коллега, который слушал весь созвон и теперь передаёт команде главное, чтобы никто ничего не забыл — особенно кто что обещал сделать. На вход — сегменты ASR с диаризацией и список участников. Это chunked-режим: тебе НЕ нужно собирать paragraphs (это отдельный вызов). Верни СТРОГО один JSON следующей формы (никаких markdown, никаких комментариев):

{{
  "tags": ["<тег>", "..."],
  "summary": {{
    "title": "<короткое название встречи 3-7 слов из сути обсуждения, без даты и без кавычек>",
    "participants": ["<имя>", "..."],
    "topics": [{{"title": "<тема>", "anchor": "[MM:SS]"}}],
    "decisions": ["<решение>", "..."],
    "tasks": [
      {{
        "assignee": "<имя>",
        "what": "<развёрнутое описание задачи>",
        "when": "<срок или null>",
        "context": "<зачем эта задача или null>",
        "conditions": "<условности или null>"
      }}
    ]
  }}
}}

Tags — ТОЛЬКО из канонического списка: {tags}. От 1 до 6 наиболее релевантных.

{quality}

{glossary}

Participants:
{participants}

Segments:
{segments}
""".replace("{tags}", _TAG_CATALOG).replace("{quality}", _QUALITY_STANDARDS).replace("{glossary}", _GLOSSARY_BLOCK)


_PROMPT_PARAGRAPHS_ONLY = """Ты — редактор расшифровок встреч бренда Wookiee. На вход — сегменты ASR. Склей соседние короткие чанки одного спикера в смысловые абзацы, восстанови пунктуацию и регистр, сопоставь каждого "Speaker N" с реальным именем участника на основе содержания реплик. Используй глоссарии ниже для нормализации названий моделей и e-com терминов. Верни СТРОГО один JSON:

{{
  "paragraphs": [
    {{"speaker": "<имя или Speaker N>", "start_ms": <int>, "text": "<текст абзаца>"}}
  ],
  "speakers_map": {{"Speaker 0": "<имя или Speaker 0>"}}
}}

{glossary}

Participants:
{participants}

Segments:
{segments}
""".replace("{glossary}", _GLOSSARY_BLOCK)


def _build_summary_prompt(segments: list[dict], participants: list[dict]) -> str:
    seg_text, p_text = _render_inputs(segments, participants)
    return _PROMPT_SUMMARY_ONLY.format(participants=p_text, segments=seg_text)


def _build_paragraphs_prompt(segments: list[dict], participants: list[dict]) -> str:
    seg_text, p_text = _render_inputs(segments, participants)
    return _PROMPT_PARAGRAPHS_ONLY.format(participants=p_text, segments=seg_text)


async def postprocess_meeting(
    segments: list[dict],
    participants: list[dict],
    *,
    model: Optional[str] = None,
) -> dict:
    """Run LLM postprocessing.

    For >_CHUNK_THRESHOLD segments, split into two calls (summary+tags first,
    paragraphs+speakers_map second). The summary chunk is the most valuable
    artifact (topics, decisions, tasks); if the paragraphs chunk fails
    (truncation, JSON error, HTTP error), fall back to empty paragraphs
    rather than losing the summary the user already paid for.

    Single-call path keeps strict behaviour: any JSON error raises
    LLMPostprocessError.
    """
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

    paragraphs_data: dict
    paragraphs_failed = False
    try:
        paragraphs_prompt = _build_paragraphs_prompt(segments, participants)
        paragraphs_raw = await _call_openrouter(
            paragraphs_prompt, use_model, LLM_POSTPROCESS_TIMEOUT_SECONDS
        )
        paragraphs_data = json.loads(_strip_markdown_codefence(paragraphs_raw))
    except (json.JSONDecodeError, httpx.HTTPError) as e:
        logger.warning(
            "LLM (paragraphs chunk) failed, falling back to empty paragraphs: %s", e
        )
        paragraphs_data = {"paragraphs": [], "speakers_map": {}}
        paragraphs_failed = True

    summary_block = summary_data.get("summary", {}) or {}
    if paragraphs_failed:
        # Помечаем summary как partial, чтобы UI-слой (notifier) показал юзеру
        # warning «транскрипт не собрался» — иначе он молча получит short
        # message без объяснения почему нет transcript.txt.
        summary_block = {**summary_block, "partial": True}

    merged = {
        "paragraphs": paragraphs_data.get("paragraphs", []),
        "speakers_map": paragraphs_data.get("speakers_map", {}),
        "tags": summary_data.get("tags", []),
        "summary": summary_block,
    }
    _validate_shape(merged)
    return merged
