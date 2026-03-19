"""
Report Pipeline — gate check → orchestrator → format → deliver.
"""
import logging
import time
from typing import Optional

from agents.oleg.pipeline.gate_checker import GateChecker, GateCheckResult
from agents.oleg.pipeline.report_types import ReportRequest, ReportResult, ReportType

logger = logging.getLogger(__name__)


class ReportPipeline:
    """
    Pipeline: gate → orchestrator → format → deliver.

    Behavior:
    - Hard passed + soft passed → full report
    - Hard passed + soft failed → report with caveats
    - Hard failed → skip + log for watchdog
    """

    def __init__(self, orchestrator, gate_checker: Optional[GateChecker] = None, skip_gates: bool = False):
        self.orchestrator = orchestrator
        self.gate_checker = gate_checker or GateChecker()
        self.skip_gates = skip_gates

    async def generate_report(self, request: ReportRequest) -> Optional[ReportResult]:
        """
        Generate a report through the full pipeline.

        Returns ReportResult or None if hard gates failed.
        """
        start_time = time.time()

        # Step 1: Gate check (skip for user queries — they bypass gates)
        caveats = []
        if not self.skip_gates and request.report_type in (
            ReportType.DAILY, ReportType.WEEKLY, ReportType.MONTHLY,
            ReportType.MARKETING_DAILY, ReportType.MARKETING_WEEKLY,
            ReportType.MARKETING_MONTHLY,
        ):
            marketplace = request.channel or "wb"
            gate_result = self.gate_checker.check_all(marketplace)

            if not gate_result.can_generate:
                logger.warning(
                    f"Hard gates FAILED for {request.report_type.value}: "
                    f"{[g.detail for g in gate_result.gates if g.is_hard and not g.passed]}"
                )
                return None  # Watchdog will handle alerting

            if gate_result.has_caveats:
                caveats = gate_result.caveats
                logger.info(
                    f"Soft gate warnings: {caveats}"
                )

        # Step 2: Build task description for orchestrator
        task = self._build_task(request)
        task_type = request.report_type.value

        # Step 3: Run orchestrator chain
        chain_result = await self.orchestrator.run_chain(
            task=task,
            task_type=task_type,
            context=request.context or {},
        )

        # Step 4: Build result
        duration_ms = int((time.time() - start_time) * 1000)

        return ReportResult(
            brief_summary=chain_result.summary,
            detailed_report=chain_result.detailed or chain_result.summary,
            report_type=request.report_type,
            telegram_summary=chain_result.telegram_summary,
            chain_steps=chain_result.total_steps,
            cost_usd=chain_result.total_cost,
            duration_ms=duration_ms,
            caveats=caveats,
        )

    def _build_task(self, request: ReportRequest) -> str:
        """Build a task description from a report request."""
        if request.report_type == ReportType.QUERY:
            return request.user_query or "Произвольный запрос без деталей."

        if request.report_type == ReportType.FEEDBACK:
            return f"Обработка feedback: {request.user_query}"

        period = f"за период {request.start_date} — {request.end_date}"

        # Inject team feedback from Notion comments (if available in context)
        feedback_note = ""
        notion_feedback = (request.context or {}).get("notion_feedback")
        if notion_feedback:
            feedback_note = (
                f"\n\nОБРАТНАЯ СВЯЗЬ КОМАНДЫ (из комментариев Notion к предыдущим отчётам):\n"
                f"{notion_feedback}\n"
                f"Учти эту обратную связь при формировании отчёта.\n"
            )

        task = None

        if request.report_type == ReportType.DAILY:
            task = (
                f"Сформируй дневной финансовый отчёт {period}.\n"
                f"ОБЯЗАТЕЛЬНЫЕ СЕКЦИИ (ВСЕ 10, НЕ ПРОПУСКАЙ НИ ОДНУ):\n"
                f"0) Паспорт отчёта (период, сравнение, тип, полнота данных, лаг выкупов, невязка)\n"
                f"1) Топ-выводы и действия (3-5 с ₽ эффектом)\n"
                f"2) План-факт (get_plan_vs_fact — MTD, прогноз, статусы ✅⚠️❌)\n"
                f"3) Ключевые изменения (Бренд) — ПОЛНАЯ таблица 19 строк: "
                f"маржа, маржинальность%, продажи шт/руб, заказы шт/руб, "
                f"реклама внутр/внешн, ДРР от заказов/продаж, ср.чек заказов/продаж, "
                f"оборачиваемость (дни), годовой ROI%, СПП% средневзвеш., "
                f"переходы в карточку, добавления в корзину, CR переход→корзина%, CR корзина→заказ%\n"
                f"4) Ценовая стратегия и динамика СПП — таблица 4а (СПП тек/прош/Δ по каналам) "
                f"+ таблица 4б (цена заказов vs цена продаж + прогноз)\n"
                f"5) Сведение ΔМаржи — waterfall (выручка, себестоимость, комиссия, логистика, "
                f"хранение, внутр.реклама, внешн.реклама, прочие, НДС, невязка)\n"
                f"6) Разрез по маркетплейсам:\n"
                f"  WB: объём/прибыльность + модельная декомпозиция (ВСЕ модели, с остатками МойСклад) "
                f"+ воронка (таблицы объём + эффективность) + структура затрат (доли % от выручки) + реклама\n"
                f"  OZON: аналогично WB\n"
                f"  Юнит-экономика артикулов (Top/Bottom) — для недельных/месячных\n"
                f"7) Драйверы/антидрайверы WB И OZON — расширенные таблицы "
                f"(доля продаж, ΔМаржа, маржинальность, ΔПродажи₽, ΔЗаказы₽, ДРР, реклама)\n"
                f"8) Гипотезы → Действия (10-колоночная таблица, отсортированы по ₽ эффекту)\n"
                f"9) Итог (10-20 строк)\n\n"
                f"Toggle headings (## ▶). Даты — русский формат (17 марта 2026).\n"
                f"ЗАПРЕЩЕНО анализировать выкупы как причину изменений (лаг 3-21 день).\n"
                f"НЕ СОКРАЩАЙ отчёт. Каждая таблица выше ОБЯЗАТЕЛЬНА.\n"
                f"Tools: get_brand_finance, get_channel_finance (wb+ozon), get_plan_vs_fact, "
                f"get_margin_levers, get_model_breakdown, get_advertising_stats, validate_data_quality."
            )

        elif request.report_type == ReportType.WEEKLY:
            task = (
                f"Сформируй еженедельный финансовый отчёт {period}.\n"
                f"ОБЯЗАТЕЛЬНЫЕ СЕКЦИИ (ВСЕ 10, НЕ ПРОПУСКАЙ НИ ОДНУ):\n"
                f"0) Паспорт отчёта (период, сравнение неделя к неделе, полнота данных, лаг выкупов)\n"
                f"1) Топ-выводы и действия (3-5 с ₽ эффектом)\n"
                f"2) План-факт (get_plan_vs_fact — MTD, прогноз, статусы ✅⚠️❌)\n"
                f"3) Ключевые изменения (Бренд) — ПОЛНАЯ таблица 19 строк: "
                f"маржа, маржинальность%, продажи шт/руб, заказы шт/руб, "
                f"реклама внутр/внешн, ДРР от заказов/продаж, ср.чек заказов/продаж, "
                f"оборачиваемость (дни), годовой ROI%, СПП% средневзвеш., "
                f"переходы в карточку, добавления в корзину, CR переход→корзина%, CR корзина→заказ%\n"
                f"4) Ценовая стратегия и динамика СПП — таблица 4а (СПП тек/прош/Δ по каналам) "
                f"+ таблица 4б (цена заказов vs цена продаж + прогноз)\n"
                f"5) Сведение ΔМаржи — waterfall\n"
                f"6) Разрез по маркетплейсам:\n"
                f"  WB: объём/прибыльность + модельная декомпозиция (ВСЕ модели, с остатками МойСклад) "
                f"+ воронка + структура затрат + реклама (итоги + детали)\n"
                f"  OZON: аналогично WB\n"
                f"  Юнит-экономика артикулов (Top/Bottom) — ТОП-3 и BOTTOM-3 по маржинальности\n"
                f"7) Драйверы/антидрайверы WB И OZON — расширенные таблицы\n"
                f"8) Гипотезы → Действия (10-колоночная таблица, отсортированы по ₽ эффекту)\n"
                f"9) Итог (10-20 строк)\n\n"
                f"Toggle headings (## ▶). Даты русский формат.\n"
                f"Выкупы: анализировать с оговоркой о лаге 3-21 день.\n"
                f"НЕ СОКРАЩАЙ отчёт. Каждая таблица выше ОБЯЗАТЕЛЬНА.\n"
                f"Tools: все доступные включая get_plan_vs_fact, advertising_stats, "
                f"daily_trend, get_article_economics."
            )

        elif request.report_type == ReportType.MONTHLY:
            task = (
                f"Сформируй месячный финансовый отчёт {period}.\n"
                f"ОБЯЗАТЕЛЬНЫЕ СЕКЦИИ (ВСЕ 10, НЕ ПРОПУСКАЙ НИ ОДНУ):\n"
                f"0) Паспорт отчёта\n"
                f"1) Топ-выводы и действия (3-5 с ₽ эффектом)\n"
                f"2) План-факт (итоговое выполнение — MTD = весь месяц, прогноз, статусы)\n"
                f"3) Ключевые изменения (Бренд) — ПОЛНАЯ таблица 15 строк\n"
                f"4) Ценовая стратегия и динамика СПП\n"
                f"5) Сведение ΔМаржи — waterfall\n"
                f"6) WB (объём + ВСЕ модели с МойСклад + воронка + структура затрат + реклама) "
                f"+ OZON (аналогично) + Юнит-экономика артикулов (Top/Bottom)\n"
                f"7) Драйверы/антидрайверы WB И OZON\n"
                f"8) Гипотезы → Действия (10-колоночная таблица)\n"
                f"9) Итог\n\n"
                f"Toggle headings (## ▶). Полная оценка выполнения плана. "
                f"Определи лучшую и худшую недели.\n"
                f"НЕ СОКРАЩАЙ отчёт. Каждая таблица ОБЯЗАТЕЛЬНА.\n"
                f"Tools: все включая get_plan_vs_fact, weekly_breakdown, get_article_economics."
            )

        if task is not None:
            return task + feedback_note

        # CUSTOM (financial)
        if request.report_type == ReportType.CUSTOM:
            channel_note = f" Канал: {request.channel}." if request.channel else ""
            return (
                f"Сформируй отчёт {period}.{channel_note} "
                f"{request.user_query or ''}"
            )

        # ── Marketing reports ─────────────────────────────────────
        if request.report_type == ReportType.MARKETING_DAILY:
            return (
                f"Оперативная сводка рекламных метрик {period}. "
                f"Toggle headings (## ▶). Даты русский формат. "
                f"Используй get_marketing_overview, get_funnel_analysis, "
                f"get_external_ad_breakdown (wb + ozon), get_plan_vs_fact. "
                f"Покажи DRR (внутр/внешн), основные аномалии vs предыдущий день. "
                f"Сводка эффективности рекламы + рекомендации обязательны."
            )

        if request.report_type == ReportType.MARKETING_WEEKLY:
            return (
                f"Еженедельный маркетинговый анализ {period}.\n"
                f"ОБЯЗАТЕЛЬНЫЕ СЕКЦИИ (ВСЕ 10, НЕ ПРОПУСКАЙ НИ ОДНУ):\n"
                f"1) Исполнительная сводка — таблица KPI (выручка, маржа, маржинальность, заказы, ср.чек, общий ДРР)\n"
                f"2) Анализ по каналам — WB + OZON таблицы (выручка, маржа, заказы, ср.чек, ДРР общ/внутр/внешн, CPO)\n"
                f"3) Анализ воронки — ASCII-визуализация (органическая WB + рекламная WB + рекламная OZON)\n"
                f"4) Органика vs Платное — 3 таблицы: доли трафика, динамика, конверсии\n"
                f"5) Внешняя реклама — разбивка по каналам (блогеры/VK), ДРР продаж И ДРР заказов\n"
                f"6) Эффективность по моделям — матрица (Growth/Harvest/Optimize/Cut) + детали по топ-моделям WB и OZON\n"
                f"7) Дневная динамика рекламы — таблица по дням (показы, клики, CTR, расход, заказы, CPO) WB и OZON\n"
                f"8) Средний чек и связь с ДРР — таблица по каналам\n"
                f"9) Рекомендации — срочные (до 3 дней) + оптимизация бюджета (неделя) + стратегические (месяц)\n"
                f"10) Прогноз на следующую неделю (тренды, риски, возможности)\n\n"
                f"Toggle headings (## ▶). Даты русский формат.\n"
                f"НЕ СОКРАЩАЙ отчёт. Каждая секция выше ОБЯЗАТЕЛЬНА.\n"
                f"Tools: get_marketing_overview, get_funnel_analysis, get_external_ad_breakdown, "
                f"get_model_ad_efficiency, get_organic_vs_paid (wb), get_ad_daily_trend, "
                f"get_plan_vs_fact, get_search_keywords."
                + feedback_note
            )

        if request.report_type == ReportType.MARKETING_MONTHLY:
            return (
                f"Глубокий маркетинговый анализ {period}. "
                f"Toggle headings (## ▶). Даты русский формат. "
                f"Используй ВСЕ tools: marketing_overview, funnel_analysis, "
                f"external_ad_breakdown, model_ad_efficiency, organic_vs_paid, "
                f"campaign_performance, ad_daily_trend, ad_budget_utilization, "
                f"ad_spend_correlation, channel_finance, margin_levers, get_plan_vs_fact. "
                f"Корреляции расход↔маржа по моделям, ROMI по типам рекламы, "
                f"бюджет vs факт, понедельная динамика. Стратегические рекомендации с расчётом эффекта в ₽."
            )

        # ── Funnel reports (Макар) ─────────────────────────────────
        if request.report_type == ReportType.FUNNEL_WEEKLY:
            import json as _json
            data_bundle = (request.context or {}).get("data_bundle")
            if not data_bundle:
                return None

            models_list = [m["model"] for m in data_bundle.get("models", [])]
            bundle_json = _json.dumps(data_bundle, ensure_ascii=False, default=str)

            date_range = f"{request.start_date} — {request.end_date}"

            task = (
                f"Сводный еженедельный отчёт маркетинговой воронки WB за {date_range}.\n\n"
                f"ДАННЫЕ УЖЕ СОБРАНЫ (НЕ вызывай инструменты, анализируй предоставленные данные):\n"
                f"{bundle_json}\n\n"
                f"МОДЕЛИ В ОТЧЁТЕ: {', '.join(models_list)}\n\n"
                f"СТРУКТУРА ОТЧЁТА (СТРОГО СОБЛЮДАЙ ФОРМАТ):\n"
                f"1. Заголовок: # Воронка WB за {date_range}\n"
                f"2. ОБЩИЙ ОБЗОР БРЕНДА — таблица KPI (переходы, заказы, выкупы, выручка, маржа, ДРР) WoW.\n"
                f"3. По каждой модели — TOGGLE-СЕКЦИЯ. ОБЯЗАТЕЛЬНЫЙ формат заголовка:\n"
                f"   ## ▶ Модель: Wendy — падение заказов -17.8%\n"
                f"   (символ ▶ ОБЯЗАТЕЛЕН в каждом заголовке модели)\n"
                f"   Внутри toggle:\n"
                f"   - Таблица воронки (current vs previous + delta)\n"
                f"   - Экономика: выручка, маржа, ДРР, ROMI, доля органики\n"
                f"   - Таблица significant_articles с флагами\n"
                f"   - Если модель без значимых изменений — одно предложение.\n"
                f"4. ## Выводы и рекомендации — топ-3 действия с расчётом эффекта в ₽.\n\n"
                f"ПРАВИЛА:\n"
                f"- КАЖДЫЙ заголовок модели ОБЯЗАТЕЛЬНО начинай с ## ▶ (символ U+25B6).\n"
                f"- Фокус на ЗНАЧИМЫХ изменениях (>20% трафик, >15% заказы, >2пп CRO).\n"
                f"- CRO (переход→заказ) — ГЛАВНАЯ метрика.\n"
                f"- Все метрики на русском. НЕ выдумывай данные.\n"
                f"- Для каждого значимого изменения — ГИПОТЕЗА.\n"
                f"- Рекомендации — ТОЛЬКО с расчётом эффекта в рублях."
            )
            return task

        # MARKETING_CUSTOM — depth adapts to period length
        from datetime import datetime
        try:
            days = (datetime.strptime(request.end_date, "%Y-%m-%d")
                    - datetime.strptime(request.start_date, "%Y-%m-%d")).days
        except (ValueError, TypeError):
            days = 7

        if days <= 7:
            depth = (
                "Используй get_marketing_overview, get_funnel_analysis, "
                "get_external_ad_breakdown, get_model_ad_efficiency, "
                "get_ad_daily_trend. Воронка, каналы, модели."
            )
        else:
            depth = (
                "Используй ВСЕ tools включая ad_spend_correlation, "
                "ad_budget_utilization, campaign_performance. "
                "Корреляции, ROMI, стратегические рекомендации."
            )

        channel_note = f" Канал: {request.channel}." if request.channel else ""
        return (
            f"Маркетинговый анализ {period}.{channel_note} "
            f"{depth} {request.user_query or ''}"
        )
