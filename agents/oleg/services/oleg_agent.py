"""
Oleg Agent — ИИ финансовый и бизнес-аналитик Wookiee.

Агент с tool-use: сам решает какие данные запросить,
итеративно углубляется в проблему (ReAct loop),
проверяет свои расчёты перед ответом.

Ключевые возможности:
- analyze(): стандартный анализ с протоколом 7 шагов
- analyze_deep(): глубокий анализ с пост-проверкой tool calls + retry
- verify_feedback(): перепроверка обратной связи через инструменты
- Обучение на фидбэке: загрузка коррекций в system prompt
"""
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List

from agents.oleg.services.agent_executor import AgentExecutor, AgentResult
from agents.oleg.services.agent_tools import TOOL_DEFINITIONS
from agents.oleg.services.time_utils import get_now_msk
from shared.utils.json_utils import extract_json

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent.parent

# Current report structure version
REPORT_VERSION = "2.0 (Financial Protocol)"

# Minimum required tools for a deep analysis
REQUIRED_TOOLS_DEEP = {
    "get_brand_finance",
    "get_channel_finance",
    "get_model_breakdown",
    "get_margin_levers",
}

# Required tools for price-related queries
REQUIRED_TOOLS_PRICE = {
    "get_price_elasticity",
    "get_price_management_plan",
}

# Keywords that indicate a price-related query
_PRICE_KEYWORDS = (
    "цен", "эластичн", "регрессион", "акци", "промо",
    "roi", "маржа", "маржин", "price", "скидк", "оборачиваем",
    "остатк", "stock", "стоимост",
)


def _is_price_query(user_query: str, params: dict) -> bool:
    """Check if the query is about pricing / price analytics."""
    if params.get("report_type") in ("price_review", "promotion_analysis", "price_scenario"):
        return True
    query_lower = user_query.lower()
    return any(kw in query_lower for kw in _PRICE_KEYWORDS)


class OlegAgent:
    """Олег — ИИ финансовый и бизнес-аналитик Wookiee с tool-use."""

    def __init__(
        self,
        zai_client,
        playbook_path: str = "agents/oleg/playbook.md",
        model: str = "claude-opus-4-6",
    ):
        self.zai = zai_client
        self.model = model
        self.executor = AgentExecutor(
            zai_client=zai_client,
            model=model,
            tool_definitions=TOOL_DEFINITIONS,
        )

        # Load playbook
        playbook_file = PROJECT_ROOT / playbook_path
        if playbook_file.exists():
            self.playbook = playbook_file.read_text(encoding='utf-8')
            logger.info(f"Oleg playbook loaded: {len(self.playbook)} chars from {playbook_file}")
        else:
            self.playbook = ""
            logger.warning(f"Oleg playbook not found: {playbook_file}")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def analyze(self, user_query: str, params: Optional[dict] = None) -> dict:
        """
        Run full analysis with tool-use ReAct loop.

        Args:
            user_query: User's query (already reformulated)
            params: Extracted parameters (dates, channels, models)

        Returns:
            {
                "brief_summary": "...",        # BBCode for Telegram
                "detailed_report": "...",      # Markdown for Notion
                "reasoning_steps": [...],      # Steps for transparency
                "usage": {...},
                "cost_usd": float,
                "iterations": int,
                "duration_ms": int,
                "provider": str,
            }
        """
        params = params or {}

        system_prompt = self._build_system_prompt(params)
        user_message = self._build_user_message(user_query, params)

        logger.info(f"Oleg analyzing: {user_query[:100]}...")

        result = await self.executor.run(
            system_prompt=system_prompt,
            user_message=user_message,
            temperature=0.4,
            max_tokens=16000,
        )

        logger.info(
            f"Oleg finished: {result.iterations} iterations, "
            f"{len(result.steps)} tool calls, "
            f"{result.duration_ms}ms, "
            f"~${result.total_cost:.4f}"
        )

        return self._process_result(result)

    async def analyze_deep(self, user_query: str, params: Optional[dict] = None) -> dict:
        """
        Deep analysis with post-check: ensures minimum tool calls.

        If required tools were missed in the first pass, continues the
        analysis with explicit instructions to call the missing tools.
        """
        params = params or {}

        system_prompt = self._build_system_prompt(params)
        user_message = self._build_user_message(user_query, params)

        logger.info(f"Oleg deep analyzing: {user_query[:100]}...")

        result = await self.executor.run(
            system_prompt=system_prompt,
            user_message=user_message,
            temperature=0.4,
            max_tokens=16000,
        )

        # Post-check: did agent call minimum required tools?
        called_tools = {step.tool_name for step in result.steps}
        required = REQUIRED_TOOLS_DEEP.copy()
        if _is_price_query(user_query, params):
            required |= REQUIRED_TOOLS_PRICE
        missing = required - called_tools

        if missing and result.finish_reason != "error":
            logger.warning(
                f"Oleg missed required tools: {missing}. "
                f"Called: {called_tools}. Continuing analysis."
            )

            missing_names = ", ".join(sorted(missing))
            continuation = await self.executor.continue_run(
                prior_result=result,
                continuation_message=(
                    f"Ты пропустил важные шаги протокола. Пропущенные инструменты: {missing_names}. "
                    f"Вызови их сейчас для полного анализа. "
                    f"Затем дай ПОЛНЫЙ итоговый ответ в формате JSON "
                    f"(brief_summary с BBCode + detailed_report с Markdown)."
                ),
                temperature=0.4,
                max_tokens=16000,
            )

            result = self._merge_results(result, continuation)

            logger.info(
                f"Oleg deep continued: +{continuation.iterations} iterations, "
                f"+{len(continuation.steps)} tool calls"
            )

        logger.info(
            f"Oleg deep finished: {result.iterations} iterations, "
            f"{len(result.steps)} tool calls, "
            f"{result.duration_ms}ms, "
            f"~${result.total_cost:.4f}"
        )

        return self._process_result(result)

    async def verify_feedback(
        self,
        feedback_text: str,
        original_report: str,
        params: Optional[dict] = None,
    ) -> dict:
        """
        Verify user feedback: re-query data and compare.

        Oleg MUST re-query data through tools, not just accept feedback.

        Returns:
            {
                "category": "format|rule|calculation_error",
                "verdict": "accepted|rejected|partially_accepted",
                "explanation": "...",
                "playbook_update": str | None,
                "user_message": "Message for Telegram",
                "usage": {...},
                "cost_usd": float,
            }
        """
        params = params or {}

        system_prompt = f"""Ты — Олег, ИИ финансовый аналитик Wookiee.
Пользователь дал обратную связь на твой отчёт.

{self.playbook}

---

ТВОЙ ОТЧЁТ (фрагмент):
{original_report[:3000]}

ОБРАТНАЯ СВЯЗЬ ПОЛЬЗОВАТЕЛЯ:
{feedback_text}

ЗАДАЧА:
1. Определи тип feedback:
   - "format" — стиль, форматирование, длина, порядок секций
   - "rule" — новое бизнес-правило или изменение подхода к анализу
   - "calculation_error" — ошибка в расчётах или формулах

2. Если calculation_error — ОБЯЗАТЕЛЬНО запроси данные через инструменты и перепроверь.
   Сравни свой расчёт с замечанием пользователя.

3. Дай вердикт:
   - "accepted" — пользователь прав, ты ошибся
   - "rejected" — ты прав, объясни почему с данными
   - "partially_accepted" — частично прав: в чём именно

ФОРМАТ ОТВЕТА — строго JSON:
{{
  "category": "format|rule|calculation_error",
  "verdict": "accepted|rejected|partially_accepted",
  "explanation": "Объяснение на бизнес-языке с конкретными цифрами из инструментов",
  "playbook_update": "текст правила для добавления в playbook (если accepted/partially_accepted, иначе null)",
  "user_message": "Сообщение пользователю в Telegram (2-5 предложений)"
}}

ВАЖНО:
- НЕ СОГЛАШАЙСЯ автоматически. Ты ОБЯЗАН проверить данные.
- Если ты прав: "Я перепроверил данные. [Формула + цифры]. Мой расчёт верный."
- Если пользователь прав: "Вы правы, я не учёл X. Обновляю правила."
- КОНКРЕТНЫЕ цифры из инструментов, не абстрактные утверждения.
"""

        result = await self.executor.run(
            system_prompt=system_prompt,
            user_message=feedback_text,
            temperature=0.3,
            max_tokens=8000,
        )

        parsed = extract_json(result.content)
        if parsed and isinstance(parsed, dict):
            parsed["usage"] = result.total_usage
            parsed["cost_usd"] = result.total_cost
            parsed["reasoning_steps"] = [
                f"[{s.tool_name}] {json.dumps(s.tool_args, ensure_ascii=False)}"
                for s in result.steps
            ]
            return parsed

        # Fallback
        return {
            "category": "format",
            "verdict": "accepted",
            "explanation": feedback_text,
            "playbook_update": None,
            "user_message": "Обратная связь принята. Спасибо!",
            "usage": result.total_usage,
            "cost_usd": result.total_cost,
        }

    # ------------------------------------------------------------------
    # Result processing
    # ------------------------------------------------------------------

    def _process_result(self, result: AgentResult) -> dict:
        """Parse agent result into structured response dict."""
        parsed = extract_json(result.content)
        reasoning_steps = [
            f"[{s.tool_name}] {json.dumps(s.tool_args, ensure_ascii=False)}"
            for s in result.steps
        ]

        if parsed and isinstance(parsed, dict):
            brief = self._safe_brief(parsed)
            return {
                "brief_summary": brief,
                "detailed_report": parsed.get("detailed_report", ""),
                "reasoning_steps": reasoning_steps,
                "usage": result.total_usage,
                "cost_usd": result.total_cost,
                "iterations": result.iterations,
                "duration_ms": result.duration_ms,
                "provider": result.finish_reason != "error" and self.model or "error",
                "success": True,
            }
        else:
            # Fallback: use raw content with safety
            logger.warning("Oleg returned non-JSON response, using raw content")
            is_error = result.finish_reason in ("error", "max_iterations")
            brief, detailed = self._parse_freeform(result.content)
            return {
                "brief_summary": brief if not is_error else "",
                "detailed_report": detailed if not is_error else "",
                "reasoning_steps": reasoning_steps,
                "usage": result.total_usage,
                "cost_usd": result.total_cost,
                "iterations": result.iterations,
                "duration_ms": result.duration_ms,
                "provider": self.model,
                "success": not is_error and bool(brief or detailed),
                "error": result.content if is_error else None,
            }

    def _safe_brief(self, parsed: dict) -> str:
        """Ensure brief_summary is valid BBCode, not raw JSON."""
        brief = parsed.get("brief_summary", "")

        if not brief:
            logger.warning("Empty brief_summary, using emergency format")
            return self._emergency_format(parsed)

        # Detect raw JSON leaked into brief_summary
        stripped = brief.strip()
        if (
            stripped.startswith('{') or
            stripped.startswith('```') or
            '"brief_summary"' in brief or
            '"detailed_report"' in brief
        ):
            logger.error("LLM returned raw JSON as brief_summary, emergency formatting")
            return self._emergency_format(parsed)

        return brief

    def _emergency_format(self, parsed: dict) -> str:
        """Emergency formatting when LLM returns raw JSON instead of BBCode."""
        lines = ["[b]Аналитический отчёт[/b]\n"]

        detailed = parsed.get("detailed_report", "")
        if detailed:
            text = detailed[:3000]
            # **bold** → [b]bold[/b]
            text = re.sub(r'\*\*(.+?)\*\*', r'[b]\1[/b]', text)
            # ### Header → [b]Header[/b]
            text = re.sub(r'^#{1,4}\s+(.+)$', r'[b]\1[/b]', text, flags=re.MULTILINE)
            # Remove markdown table separators (|---|)
            text = re.sub(r'^\|[-:| ]+\|$', '', text, flags=re.MULTILINE)
            lines.append(text)
        else:
            # Try to extract any useful text from other fields
            for key in ("summary", "analysis", "conclusion", "brief"):
                val = parsed.get(key, "")
                if val and isinstance(val, str):
                    lines.append(val[:2000])
                    break

        return "\n".join(lines)

    def _merge_results(self, first: AgentResult, second: AgentResult) -> AgentResult:
        """Merge two sequential AgentResults (first run + continuation)."""
        return AgentResult(
            content=second.content,  # Use the final content from continuation
            steps=first.steps + second.steps,
            total_usage={
                "input_tokens": (
                    first.total_usage.get("input_tokens", 0) +
                    second.total_usage.get("input_tokens", 0)
                ),
                "output_tokens": (
                    first.total_usage.get("output_tokens", 0) +
                    second.total_usage.get("output_tokens", 0)
                ),
            },
            total_cost=first.total_cost + second.total_cost,
            iterations=first.iterations + second.iterations,
            duration_ms=first.duration_ms + second.duration_ms,
            finish_reason=second.finish_reason,
            _messages=second._messages,
        )

    # ------------------------------------------------------------------
    # Prompt building
    # ------------------------------------------------------------------

    def _build_system_prompt(self, params: dict) -> str:
        """Build system prompt with strict analysis protocol + playbook + feedback lessons."""
        report_type = params.get("report_type", "period")
        format_instructions = self._get_format_instructions(report_type)
        feedback_lessons = self._load_feedback_lessons()

        return f"""{self.playbook}

---

ТЕКУЩИЕ МЕТАДАННЫЕ:
- Текущее время (MSK): {get_now_msk()}
- Версия отчёта: {REPORT_VERSION}

---

{feedback_lessons}ПРОТОКОЛ АНАЛИЗА (ВЫПОЛНЯЙ СТРОГО В ЭТОМ ПОРЯДКЕ):

Шаг 1: ОБЩАЯ КАРТИНА
→ Вызови get_brand_finance(start_date, end_date)
→ Зафиксируй: маржа ₽/%, выручка, заказы, продажи, реклама
→ Определи главную аномалию (что изменилось больше всего?)

Шаг 2: КАНАЛЫ
→ Вызови get_channel_finance("wb", ...) и get_channel_finance("ozon", ...)
→ Какой канал вызвал главную аномалию?
→ Разбей рекламу: внутренняя vs внешняя

Шаг 3: РЫЧАГИ МАРЖИ + ЦЕНОВАЯ СТРАТЕГИЯ + СТРУКТУРА ЗАТРАТ
→ Вызови get_margin_levers("wb", ...) и get_margin_levers("ozon", ...)
→ Какой рычаг сработал: цена? СПП? ДРР? логистика? себестоимость?
→ Контрфактуал: «если убрать X → маржа была бы Y»

→ ЦЕНОВАЯ СТРАТЕГИЯ:
   - СПП — это скидка за счёт маркетплейса. Она НЕ снижает нашу выручку на единицу.
   - Рост СПП = снижение цены для покупателя → рост спроса (заказов). Снижение СПП = рост цены для покупателя → снижение спроса.
   - СПП изменился > 2 п.п.? → указать влияние на конверсию и объём заказов
   - Если СПП вырос → рекомендация: рассмотреть повышение базовой цены (цены до СПП), чтобы увеличить маржинальность, не теряя спроса
   - Если СПП снизился → рекомендация: рассмотреть снижение базовой цены (цены до СПП), чтобы удержать цену для клиента
   - Средняя цена/ед: revenue_before_spp / sales_count — текущая vs предыдущая
   - Прогноз: цена заказов (orders_rub / orders_count) vs цена продаж — разница > 5% = прогноз изменения выручки

→ СТРУКТУРА ЗАТРАТ (доли от выручки):
   - Рассчитать доли: commission%, logistics%, storage%, other% (от revenue_before_spp)
   - Если маржинальность упала > 2 п.п. → какая доля выросла больше всего?
   - Логистика доля +1 п.п. → «Проверить локализацию WB / срок доставки OZON (агент Vasily)»
   - Хранение доля +0.5 п.п. → «Проверить замороженные остатки, неликвид»

Шаг 3.5: ЦЕНОВАЯ АНАЛИТИКА И ОПТИМИЗАЦИЯ (если weekly/monthly отчёт ИЛИ запрос о ценах)
→ get_model_roi_dashboard(channel) — ROI по моделям (маржа% × 365/оборачиваемость)
→ get_stock_price_matrix(channel) — матрица остатки × ценовое действие
→ get_price_management_plan(channel) — полный ценовой план с приоритизацией
→ Вызови get_price_elasticity(model, channel) для топ-3 моделей по марже
→ Вызови get_price_margin_correlation(channel, start_date, end_date) для общей картины
→ Если эластичность значима (is_significant=true) → get_price_recommendation(model, channel)
→ Если есть доступные акции → get_promotion_plan(channel)
→ get_price_trend(model, channel) для топ-3 моделей — растёт/падает/стабильна?
→ Если weekly/monthly → test_price_hypothesis(channel) — проверка гипотез H1-H7

Шаг 4: МОДЕЛИ — Драйверы и Анти-драйверы (drill-down)
→ Вызови get_model_breakdown("wb", ...) и get_model_breakdown("ozon", ...)
→ ОБЯЗАТЕЛЬНО: Применить маппинг артикулов → model_osnova:
   - vuki/vuki2/vukin/vukiw/vukip/компбел-ж-бесшов → Vuki
   - moon/moon2/moonw → Moon; ruby/rubyw/rubyp → Ruby
   - set vuki/set vukip/set wookiee → Set Vuki
   (полный маппинг — в playbook раздел «Иерархия продуктов»)
→ Используй model_osnova (Vuki, Moon) для общих выводов и сводок.
→ В разделах "Драйверы и Анти-драйверы" (в т.ч. в таблицах) используй конкретную МОДЕЛЬ (префикс: VukiW, RubyP).
→ Определи ДРАЙВЕРЫ прибыли: топ-3 МОДЕЛИ по РОСТУ маржи в ₽
→ Определи АНТИ-ДРАЙВЕРЫ: МОДЕЛИ с ДРР > 30% ИЛИ маржа < 0 ИЛИ маржа упала > 30%
→ Drill-down: если model_osnova аномальна → указать какие модели/артикулы внутри
→ В финальном отчёте: «Драйверы: Wendy (+46 тыс), RubyP (+25 тыс). Анти-драйверы: JoyW WB (убыток -5.9 тыс, ДРР 41%)»

Шаг 5: МАРКЕТИНГ И ТРАФИК
→ Вызови get_advertising_stats("wb", ...)
→ ОБЯЗАТЕЛЬНО проверь: переходы (card_opens), корзины (add_to_cart). Показы (ad_views) доступны только для рекламного блока.
→ Посчитай среднюю цену/ед: выручка_до_СПП / продажи_шт

→ ПРОИЗВОДНЫЕ МАРКЕТИНГОВЫЕ МЕТРИКИ (автоматически в get_advertising_stats и get_model_advertising):
  - CPM (стоимость 1000 показов), CPL (стоимость корзины), CPO (стоимость заказа)
  - Конверсии: клик→корзина (cart_conversion_pct), корзина→заказ (order_from_cart_pct), клик→заказ (cr_full_pct)
  - Бенчмарки: CTR < 1% нецелевой, 2-3% средний, 5%+ целевой; CPM < 100₽ хорошо, > 500₽ дорого
  - CPO vs маржа/ед:
    → Если CPO > маржа/ед И ДРР заказов тоже высокий → реклама убыточна, резать бюджет
    → Если CPO > маржа/ед НО ДРР заказов в норме → это ИНВЕСТИЦИЯ (заказы выкупятся и покроют расход). НЕ отключать рекламу.
  - Вызови get_model_advertising() → CPO по моделям + сравни с ДРР заказов для каждой модели
  - Органическая воронка WB: card_opens → cart → order → buyout с конверсиями на каждом шаге
  - КАЧЕСТВО ТРАФИКА: если корзины (add_to_cart) растут, а заказы (orders) не растут или растут медленнее → Трафик эффективен (интерес есть), но есть барьер (Цена/Отзывы). Это сигнал проверить цену, а не отключать рекламу.

→ ВНЕШНЯЯ РЕКЛАМА:
   - Определи ТИП: блогеры (несистемный) или VK/Яндекс (системный)?
   - Если блогер (всплеск adv_external): НЕ считать ДРР сегодня, «эффект отложенный 3-7 дней»
   - Если системные каналы: можно анализировать ДРР день-к-дню
   - ЗАПРЕТ: «внешняя реклама остановлена/прекращена» — блогеры несистемны

→ ПАТТЕРНЫ (проверять при каждом анализе):
   - card_opens↓ > 10% + ДРР↓ одновременно = ПОТЕРЯ ЭФФЕКТИВНОГО ТРАФИКА (НЕ оптимизация)
     → «Срочно вернуть рекламу на модели с просевшими переходами»
   - Реклама↓ → Показы↓ → Переходы↓ → Заказы↓ = TRADE-OFF (маржа/ед↑, объём↓)
   - НЕЛЬЗЯ рекомендовать «сокращать рекламу ещё» если трафик уже падает

Шаг 6: КАЧЕСТВО ДАННЫХ
→ Вызови validate_data_quality(date)
→ retention == deduction? → предупреждение

Шаг 7: СИНТЕЗ
→ Формат: «Что произошло / Почему / Какие модели / Что делать»
→ Что произошло: 1 предложение с главным фактом + trade-off
→ Почему: причинно-следственная цепочка (НЕ перечисление фактов)
→ Какие модели: Драйверы + Анти-драйверы с конкретными ₽
→ Что делать: 2-3 действия. Если трафик падает — ДОБАВИТЬ точечную рекламу на прибыльные модели

НЕ ПРОПУСКАЙ ШАГИ. Минимум 6 вызовов инструментов.

{format_instructions}

ФОРМАТ ОТВЕТА — строго JSON:
{{
  "brief_summary": "краткая сводка с [b]...[/b] BBCode. ТОЛЬКО текст. НИКОГДА НЕ вставляй JSON или markdown-блоки.",
  "detailed_report": "подробный Markdown отчёт с причинно-следственными цепочками"
}}

СТРУКТУРА brief_summary (адаптивная, НЕ фиксированный шаблон):

Сводка строится от ДАННЫХ: показывай то, что существенно изменилось (> 5% или > 2 п.п.),
привязывай к целям бизнеса, давай основу для быстрых решений.

[b]Сводка за [дата]:[/b]

[b]Что произошло:[/b]
• Маржа: X тыс ₽ (±Y%)
• Маржинальность: X% (±Y п.п.) [если < 20% — указать «ниже целевого уровня»]
• [Другие метрики, которые существенно изменились — каждая отдельной строкой с •]
• [Trade-off если есть: одно растёт, другое падает]

[b]По каналам:[/b]
[b]WB:[/b] маржа X тыс (±Y%), маржинальность Z%
[b]OZON:[/b] маржа A тыс (±B%), маржинальность C%
[Комментарий: какой канал драйвер/проблемный]

[b]Почему:[/b]
• Причина 1: что изменилось → почему → эффект ±X тыс ₽
• Причина 2: аналогично
• [Каждая причина — отдельный буллет, НЕ сплошной текст]

[b]Драйверы прибыли:[/b]
• Model1 WB: +X тыс маржи [причина]
• Model2 OZON: +Y тыс маржи

[b]Анти-драйверы:[/b]
• Model3 WB: убыток -X тыс, ДРР Y%
• Model4 OZON: маржа -Z%

[b]Что делать:[/b]
1. Конкретное действие с указанием модели и канала.
2. Конкретное действие.
3. Конкретное действие (при необходимости).

ВИЗУАЛЬНЫЕ ПРАВИЛА:
- [b]...[/b] для заголовков, буллеты (•) для списков — НЕ сплошной текст
- Числа отдельными строками с •, НЕ внутри длинных предложений
- Пустая строка между разделами
- Для каждой модели указывать канал (WB/OZON)
- **Общие выводы / Сводка:** называть по model_osnova (Vuki, Moon, Ruby).
- **Детальные таблицы / Драйверы:** называть по конкретной МОДЕЛИ (VukiW, RubyP), НЕ по артикулам.
- Максимум 45 строк

КРИТИЧЕСКИЕ ПРАВИЛА:
- brief_summary ОБЯЗАН быть чистым текстом с [b]...[/b] BBCode. НЕ JSON, НЕ markdown-блок.
- Причинно-следственные цепочки, НЕ перечисление фактов
- Бизнес-язык. Без "confidence", "триангуляция", "Red Team", "evidence"
- СРЕДНЯЯ ЦЕНА/ЕД: revenue_before_spp / sales_count. Анализируй текущую vs предыдущую.
- ЗАПРЕЩЕНО: ссылаться на "правила аналитики", "плейбук", "инструкции" или файлы (включая playbook.md). Пользователь не должен видеть, на основе каких документов сделан вывод.
- ИЗБЕГАЙ ОБЪЕВИДНЫХ ПОЯСНЕНИЙ: не пиши вещи вроде "снижение выручки — следствие низких заказов в прошлом периоде". Делай выводы только о том, ЧТО изменилось и ПОЧЕМУ это важно для прибыли.
- МНОГОФАКТОРНОСТЬ: не делай безальтернативных утверждений о причинах, если возможны другие трактовки. Если на падение заказов могли повлиять и цена, и отзывы, и показы — перечисляй все факторы.
- Рекомендации: если трафик падает — ДОБАВИТЬ рекламу на прибыльные модели, НЕ «сокращать ещё»
- Контрфактуал обязателен: «если убрать X → маржа была бы Y руб (Z%)»
- Внешняя реклама: НЕ писать «остановлена/прекращена» (блогеры — несистемные)
"""

    def _build_user_message(self, user_query: str, params: dict) -> str:
        """Build user message with query and parameters context."""
        parts = [f"Запрос: {user_query}"]

        if params.get("start_date") and params.get("end_date"):
            parts.append(f"Период: {params['start_date']} — {params['end_date']}")

        channels = params.get("channels", [])
        if channels:
            parts.append(f"Каналы: {', '.join(c.upper() for c in channels)}")

        models = params.get("models", [])
        if models:
            parts.append(f"Модели: {', '.join(models)}")

        directions = params.get("suggested_directions", [])
        if directions:
            parts.append("Направления анализа: " + "; ".join(directions[:3]))

        if params.get("data_availability_note"):
            parts.append(f"\n⚠️ {params['data_availability_note']}")

        return "\n".join(parts)

    def _get_format_instructions(self, report_type: str) -> str:
        """Return format instructions based on report type."""
        if report_type == "daily":
            return """ФОРМАТ:
А. Краткая сводка: «Сводка за [дата]:», макс 45 строк, [b]...[/b] BBCode
Б. Подробный отчёт: причинно-следственные цепочки, модели, 7-дневный контекст"""

        elif report_type == "weekly":
            return """ФОРМАТ:
А. Краткая сводка: «Сводка за неделю [дата—дата]:», макс 45 строк, [b]...[/b]
Б. Подробный отчёт: дневная динамика внутри недели, связка реклама→заказы"""

        elif report_type == "monthly":
            return """ФОРМАТ:
А. Краткая сводка: «Сводка за [месяц год]:», макс 45 строк, [b]...[/b]
   Включить: статус vs бизнес-целей, ключевые победы/проблемы
Б. Подробный отчёт: executive summary, понедельная динамика, vs целей"""

        elif report_type == "price_review":
            return """ФОРМАТ:
А. Краткая сводка: «Ценовой обзор за [период]:», макс 45 строк, [b]...[/b]
   Включить: эластичность по моделям, ценовые рекомендации, акции МП
Б. Подробный отчёт:
   - Эластичность по моделям (значение, интерпретация, значимость)
   - Ценовые рекомендации с прогнозом финансового эффекта
   - Корреляционная матрица цена ↔ маржа/объём/ДРР
   - Ценовые тренды (растёт/падает/стабильна)
   - Акции МП: рекомендация участвовать/пропустить с расчётом
   - ROI дашборд: маржа% × оборачиваемость по моделям
   - Матрица остатки × цена: stock constraints
   - Гипотезы H1-H7 (если weekly/monthly)
   - Сценарии: "что если цену изменить на ±5%, ±10%"
   - История прошлых рекомендаций и их точность"""

        else:  # period
            return """ФОРМАТ:
А. Краткая сводка: «Сводка за [период]:», макс 45 строк, [b]...[/b]
   Адаптируй формат под длину периода
Б. Подробный отчёт: причинно-следственные цепочки, модели"""

    # ------------------------------------------------------------------
    # Feedback learning
    # ------------------------------------------------------------------

    def _load_feedback_lessons(self) -> str:
        """Load recent feedback corrections to include in system prompt."""
        try:
            from agents.oleg import config
            feedback_path = Path(config.FEEDBACK_LOG_PATH)
            if not feedback_path.exists():
                return ""

            content = feedback_path.read_text(encoding="utf-8")
            if not content.strip() or "### " not in content:
                return ""

            # Extract correction entries (split by ### headers)
            entries = content.split("### ")
            # Take last 5 entries (most recent feedback)
            recent = entries[-5:] if len(entries) > 5 else entries[1:]  # skip file header

            if not recent:
                return ""

            lessons = []
            for entry in recent:
                lines = entry.strip().split("\n")
                if not lines:
                    continue
                date_line = lines[0].strip()
                description = ""
                verdict = ""
                for line in lines:
                    if line.startswith("**Описание/обновление:**"):
                        description = line.replace("**Описание/обновление:**", "").strip()
                    if line.startswith("**Вердикт:**"):
                        verdict = line.replace("**Вердикт:**", "").strip()
                if description and verdict in ("accepted", "partially_accepted"):
                    date_part = date_line.split(" —")[0] if " —" in date_line else date_line[:10]
                    lessons.append(f"- [{date_part}] {description}")

            if not lessons:
                return ""

            return (
                "УРОКИ ИЗ ОБРАТНОЙ СВЯЗИ (обязательно учитывай):\n"
                + "\n".join(lessons)
                + "\n\n---\n\n"
            )
        except Exception as e:
            logger.warning(f"Failed to load feedback lessons: {e}")
            return ""

    # ------------------------------------------------------------------
    # Fallback parsing
    # ------------------------------------------------------------------

    def _parse_freeform(self, content: str) -> tuple:
        """Fallback parser when Oleg doesn't return JSON."""
        if not content:
            return "[b]Ошибка: пустой ответ агента[/b]", ""

        # Try to split by known headers
        if "## Краткая сводка" in content and "## Подробный отчёт" in content:
            parts = content.split("## Подробный отчёт")
            brief = parts[0].replace("## Краткая сводка", "").strip()
            detailed = parts[1].strip() if len(parts) > 1 else ""
            return brief, detailed

        # Always try extract_json — content may have text preamble before JSON
        parsed = extract_json(content)
        if parsed and isinstance(parsed, dict):
            brief = self._safe_brief(parsed)
            detailed = parsed.get("detailed_report", content)
            return brief, detailed

        # Regex fallback: extract brief_summary from partial/truncated JSON
        brief_match = re.search(
            r'"brief_summary"\s*:\s*"((?:[^"\\]|\\.)*)"',
            content, re.DOTALL,
        )
        if brief_match:
            raw_brief = brief_match.group(1)
            # Unescape JSON string escapes
            brief = raw_brief.replace('\\n', '\n').replace('\\"', '"').replace('\\\\', '\\')
            logger.info("Extracted brief_summary via regex fallback")

            # Try to get detailed_report too
            detail_match = re.search(
                r'"detailed_report"\s*:\s*"((?:[^"\\]|\\.)*)"',
                content, re.DOTALL,
            )
            if detail_match:
                detailed = detail_match.group(1).replace('\\n', '\n').replace('\\"', '"').replace('\\\\', '\\')
            else:
                detailed = ""
            return brief, detailed

        # Last resort: strip markdown fences and convert
        text = re.sub(r'```(?:json)?\s*\n?', '', content)
        text = text.replace('```', '')
        text = re.sub(r'\*\*(.+?)\*\*', r'[b]\1[/b]', text)
        text = re.sub(r'^#{1,4}\s+(.+)$', r'[b]\1[/b]', text, flags=re.MULTILINE)
        # Remove raw JSON artifacts
        text = re.sub(r'\{[^}]*"brief_summary"[^}]*\}?', '', text, flags=re.DOTALL)
        return text[:3000], content
