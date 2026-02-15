"""
LLM-based Query Understanding Service for Oleg bot.

Replaces regex-based _basic_parse() with intelligent natural language understanding.
Uses cheap glm-4.5-flash model for cost-efficient query parsing (~$0.0001/call).

Three response modes:
- "ready": Query fully understood → structured params + proposed_query
- "needs_clarification": Partially understood → proposed_query draft + smart questions
- "unclear": Cannot understand → targeted questions based on available data
"""
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List

from shared.utils.json_utils import extract_json

logger = logging.getLogger(__name__)

# Known valid values for validation
_VALID_CHANNELS = {"wb", "ozon"}
_VALID_REPORT_TYPES = {"daily", "period", "weekly", "monthly", "comparison"}
_KNOWN_MODELS = [
    "wendy", "ruby", "set_vuki", "joy", "vuki", "moon", "audrey", "bella",
]
_DATA_START_DATE = "2024-01-01"
_MAX_CLARIFICATION_ROUNDS = 3


class QueryUnderstandingService:
    """LLM-based natural language query understanding for Wookiee analytics."""

    PARSE_MODEL = "glm-4.5-flash"
    PARSE_TIMEOUT = 10.0
    PARSE_MAX_TOKENS = 800

    def __init__(self, zai_client):
        self.zai = zai_client

    async def parse(
        self,
        query: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> dict:
        """
        Parse a natural language analytics query into structured parameters.

        Returns dict with:
        - status="ready": full params compatible with oleg_agent.analyze()
        - status="needs_clarification": understood_parts + proposed_query + clarifying_questions
        - status="unclear": only clarifying_questions

        On LLM failure: falls back to regex-based _basic_parse().
        """
        # If too many clarification rounds, force best interpretation
        if conversation_history and len(conversation_history) > _MAX_CLARIFICATION_ROUNDS * 2:
            logger.info("Max clarification rounds reached, forcing best interpretation")
            return await self._force_interpretation(query, conversation_history)

        try:
            system_prompt = self._build_system_prompt()
            user_message = self._build_user_message(query, conversation_history)

            response = await self.zai.complete(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                temperature=0.1,
                max_tokens=self.PARSE_MAX_TOKENS,
                model=self.PARSE_MODEL,
                response_format={"type": "json_object"},
            )

            content = response.get("content")
            if not content:
                logger.warning(f"LLM returned empty response: {response.get('error')}")
                return self._fallback_regex_parse(query)

            parsed = extract_json(content)
            if not parsed or not isinstance(parsed, dict):
                logger.warning(f"Failed to parse LLM JSON: {content[:200]}")
                return self._fallback_regex_parse(query)

            status = parsed.get("status", "unclear")

            if status == "ready":
                return self._validate_and_normalize(parsed, query)
            elif status == "needs_clarification":
                return self._build_clarification_response(parsed)
            else:
                return self._build_unclear_response(parsed)

        except Exception as e:
            logger.error(f"Query understanding LLM failed: {e}", exc_info=True)
            return self._fallback_regex_parse(query)

    def _build_system_prompt(self) -> str:
        today = datetime.now().strftime("%Y-%m-%d")
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        day_before = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")

        return f"""Ты — парсер запросов аналитики бренда Wookiee (одежда, маркетплейсы WB и OZON).

ЗАДАЧА: Понять запрос пользователя, предложить УЛУЧШЕННУЮ формулировку запроса и извлечь параметры.

ДОСТУПНЫЕ ДАННЫЕ:
- Каналы: WB (Wildberries), OZON. По умолчанию — оба.
- Модели товаров: wendy, ruby, set_vuki, joy, vuki, moon, audrey, bella
- Данные с 2024-01-01 по {yesterday}
- Юрлица: ИП Медведева, ООО ВУКИ

МЕТРИКИ:
- Финансы: маржа (₽, %), выручка (до/после СПП), заказы (шт, ₽), продажи
- Расходы: комиссия, логистика, себестоимость, хранение, НДС, штрафы
- Реклама: ДРР%, CTR, CPC, CPO, ROMI, внутр. реклама, внешн. реклама
- Конверсии: просмотры→корзина→заказ→выкуп (WB)
- Декомпозиция маржи по 5 рычагам: цена, СПП%, ДРР%, логистика/шт, себестоимость/шт

СРЕЗЫ (группировки):
- По каналу (WB / OZON / оба)
- По модели товара (wendy, ruby и т.д.)
- По дате (день, неделя, месяц, произвольный период)
- По юрлицу
- По региону (только WB)
- По статусу товара (в продаже / выводим / архив)

ВИДЫ АНАЛИЗА (report_type):
- daily — один день
- period — диапазон дат
- weekly — неделя (7 дней)
- monthly — календарный месяц
- comparison — сравнение двух периодов

ПРАВИЛА ДАТ:
- "вчера" = {yesterday}
- "позавчера" = {day_before}
- "сегодня" — данных нет, используй {yesterday}
- "прошлая неделя" = пн-вс предыдущей недели
- Одна дата (напр. "10 февраля") = daily, start_date = end_date
- Если год не указан — текущий ({datetime.now().year})

ФОРМАТ ОТВЕТА — строго JSON, один из трёх:

1) Запрос полностью понятен:
{{"status": "ready", "report_type": "daily|period|weekly|monthly|comparison", "start_date": "YYYY-MM-DD", "end_date": "YYYY-MM-DD", "channels": ["wb"], "models": [], "metrics_focus": ["маржа", "реклама"], "reformulated_query": "техническая формулировка для аналитика", "proposed_query": "Расширенная формулировка для пользователя: какие метрики, срезы, сравнения будут. Покажи что бот МОЖЕТ проанализировать, предложи дополнительные полезные срезы.", "suggested_directions": ["направление 1", "направление 2", "направление 3"]}}

2) Частично понятен (не хватает периода или уточнения):
{{"status": "needs_clarification", "understood_parts": {{"channels": [], "models": [], "metrics_focus": [], "partial_intent": "что понял"}}, "proposed_query": "Черновик запроса с [плейсхолдерами] для недостающего", "clarifying_questions": ["конкретный вопрос 1"]}}

3) Непонятен:
{{"status": "unclear", "clarifying_questions": ["что проанализировать?", "за какой период?"]}}

КЛЮЧЕВОЕ ПРАВИЛО для proposed_query:
- ВСЕГДА предлагай БОЛЬШЕ чем попросил пользователь: если просят "отчёт" — предложи конкретные метрики
- Покажи какие срезы доступны: "по моделям", "декомпозиция маржи", "сравнение с предыдущим днём"
- Предложи сравнение если его не просили (предыдущий день/неделя)
- Предложи топ-модели по вкладу в маржу
- Формулируй на русском, понятным бизнес-языком

СЕГОДНЯ: {today}"""

    def _build_user_message(
        self,
        query: str,
        conversation_history: Optional[List[Dict[str, str]]],
    ) -> str:
        if not conversation_history:
            return query

        # Include last 4 turns max (to keep tokens low)
        recent = conversation_history[-4:]
        turns = []
        for turn in recent:
            role = "Пользователь" if turn["role"] == "user" else "Бот"
            turns.append(f"{role}: {turn['content']}")

        context = "\n".join(turns)
        return f"ИСТОРИЯ ДИАЛОГА:\n{context}\n\nТЕКУЩИЙ ЗАПРОС:\n{query}"

    def _validate_and_normalize(self, parsed: dict, original_query: str) -> dict:
        """Validate LLM output and normalize to format expected by oleg_agent.analyze()."""
        # Validate dates
        start_date = parsed.get("start_date", "")
        end_date = parsed.get("end_date", "")
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

        try:
            if start_date:
                sd = datetime.strptime(start_date, "%Y-%m-%d")
                if sd > datetime.now():
                    start_date = yesterday
                if sd < datetime(2024, 1, 1):
                    start_date = _DATA_START_DATE
        except ValueError:
            start_date = yesterday

        try:
            if end_date:
                ed = datetime.strptime(end_date, "%Y-%m-%d")
                if ed > datetime.now():
                    end_date = yesterday
                if ed < datetime(2024, 1, 1):
                    end_date = _DATA_START_DATE
        except ValueError:
            end_date = start_date or yesterday

        if not start_date:
            start_date = yesterday
        if not end_date:
            end_date = start_date

        # Validate channels
        channels = parsed.get("channels", ["wb", "ozon"])
        channels = [c.lower() for c in channels if c.lower() in _VALID_CHANNELS]
        if not channels:
            channels = ["wb", "ozon"]

        # Validate models
        models = parsed.get("models", [])
        models = [m.lower() for m in models if m.lower() in _KNOWN_MODELS]

        # Validate report_type
        report_type = parsed.get("report_type", "period")
        if report_type not in _VALID_REPORT_TYPES:
            report_type = "daily" if start_date == end_date else "period"

        return {
            "status": "ready",
            "report_type": report_type,
            "start_date": start_date,
            "end_date": end_date,
            "channels": channels,
            "models": models,
            "question": original_query,
            "reformulated_query": parsed.get("reformulated_query", original_query),
            "proposed_query": parsed.get("proposed_query", ""),
            "suggested_directions": parsed.get("suggested_directions", [])[:3],
        }

    def _build_clarification_response(self, parsed: dict) -> dict:
        """Build response for partially understood query."""
        return {
            "status": "needs_clarification",
            "needs_clarification": True,
            "understood_parts": parsed.get("understood_parts", {}),
            "proposed_query": parsed.get("proposed_query", ""),
            "clarifying_questions": parsed.get("clarifying_questions", [
                "За какой период нужен анализ?",
                "Какие метрики интересуют?",
            ]),
        }

    def _build_unclear_response(self, parsed: dict) -> dict:
        """Build response for completely unclear query."""
        return {
            "status": "unclear",
            "needs_clarification": True,
            "understood_parts": {},
            "proposed_query": "",
            "clarifying_questions": parsed.get("clarifying_questions", [
                "Что именно хотите проанализировать? (маржа, выручка, реклама, конкретная модель)",
                "За какой период? (вчера, конкретная дата, неделя, месяц)",
            ]),
        }

    async def _force_interpretation(
        self, query: str, conversation_history: List[Dict[str, str]]
    ) -> dict:
        """After max rounds of clarification, force best interpretation."""
        try:
            all_text = query
            for turn in conversation_history:
                if turn["role"] == "user":
                    all_text += f". {turn['content']}"

            system_prompt = self._build_system_prompt()
            force_prompt = (
                f"Пользователь уточнял запрос несколько раз. "
                f"Сформируй ЛУЧШУЮ интерпретацию из всего диалога. "
                f"ОБЯЗАТЕЛЬНО верни status=ready с конкретными датами.\n\n"
                f"Весь диалог: {all_text}"
            )

            response = await self.zai.complete(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": force_prompt},
                ],
                temperature=0.1,
                max_tokens=self.PARSE_MAX_TOKENS,
                model=self.PARSE_MODEL,
                response_format={"type": "json_object"},
            )

            content = response.get("content")
            if content:
                parsed = extract_json(content)
                if parsed and isinstance(parsed, dict):
                    return self._validate_and_normalize(parsed, query)

        except Exception as e:
            logger.error(f"Force interpretation failed: {e}")

        return self._fallback_regex_parse(query)

    def _fallback_regex_parse(self, query: str) -> dict:
        """Fallback to the original regex-based parser."""
        from agents.oleg.handlers.custom_queries import _basic_parse
        logger.info("Falling back to regex parser")
        result = _basic_parse(query)
        # Add status field for consistency
        if result.get("needs_clarification"):
            result["status"] = "unclear"
        else:
            result["status"] = "ready"
            result["proposed_query"] = result.get("reformulated_query", "")
        return result
