"""
Deterministic report formatter for V3 orchestrator.

Converts structured JSON artifacts from report-compiler into human-readable
Russian markdown for Notion and BBCode summaries for Telegram.

Design: template-based formatting (scripts), NOT LLM-generated each time.
This ensures consistent output quality regardless of compiler model behavior.
"""
from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


# ── Russian field labels ──────────────────────────────────────────────────────

_FIELD_RU: dict[str, str] = {
    # Financial
    "revenue_rub": "Выручка ₽", "margin_rub": "Маржинальная прибыль ₽",
    "margin_pct": "Маржинальность %", "sales_count": "Продажи (шт)",
    "sales_rub": "Продажи ₽", "orders_count": "Заказы (шт)",
    "orders_rub": "Заказы ₽", "adv_internal_rub": "Реклама внутр. ₽",
    "adv_external_rub": "Реклама внешн. ₽", "drr_orders_pct": "ДРР от заказов %",
    "drr_sales_pct": "ДРР от продаж %", "avg_check_orders": "Ср. чек заказов ₽",
    "avg_check_sales": "Ср. чек продаж ₽", "turnover_days": "Оборачиваемость (дни)",
    "roi_annual_pct": "Годовой ROI %", "spp_weighted_pct": "СПП средневзв. %",
    # Funnel
    "card_opens": "Переходы в карточку", "add_to_cart": "В корзину",
    "cr_open_to_cart_pct": "CR переход→корзина %",
    "cr_cart_to_order_pct": "CR корзина→заказ %",
    # Deltas
    "delta_abs": "Δ абс.", "delta_pct": "Δ %", "change_pct": "Δ %",
    "margin_change_rub": "ΔМаржа ₽", "margin_change_pct": "ΔМаржа %",
    "revenue_change_pct": "ΔВыручка %",
    # Ad metrics
    "impressions": "Показы", "clicks": "Клики", "ctr": "CTR %",
    "cpc": "CPC ₽", "cpm": "CPM ₽", "cpo": "CPO ₽", "spend": "Расход ₽",
    # Stock
    "fbo_stock": "Остаток FBO", "own_stock": "Свой склад",
    "total_stock": "Итого остаток",
    # Identifiers
    "overall_status": "Общий статус", "model_osnova": "Модель",
    "model": "Модель", "channel": "Канал", "comment": "Комментарий",
    "headline": "Заголовок", "interpretation": "Интерпретация",
    "confidence": "Достоверность", "data_coverage": "Покрытие данных",
    "period": "Период", "current": "Текущий", "previous": "Прошлый",
    # Cost structure
    "cost_per_unit": "Себестоимость/ед", "logistics_per_unit": "Логистика/ед",
    "storage_per_unit": "Хранение/ед", "nds": "НДС", "residual": "Невязка",
    # Section-level keys → Russian titles
    "brand_performance": "Показатели бренда", "wb_performance": "Wildberries",
    "ozon_performance": "OZON", "brand_metrics": "Ключевые метрики бренда",
    "channel_breakdown": "По каналам", "models": "По моделям",
    "funnel": "Воронка", "margin_waterfall": "Каскад маржинальности",
    "cost_structure": "Структура затрат", "ad_stats": "Статистика рекламы",
    "recommendations": "Рекомендации", "hypotheses": "Гипотезы",
    "action_plan": "План действий", "drivers": "Драйверы",
    "anti_drivers": "Антидрайверы", "conclusions": "Выводы",
    "summary": "Итог", "executive_summary": "Ключевые выводы",
    "plan_fact": "План-Факт", "plan_vs_fact": "План-Факт",
    "pricing_strategy": "Ценовая стратегия и СПП",
    "key_changes": "Ключевые изменения", "financial_performance": "Финансовые показатели",
    "channel_analysis": "Анализ по каналам", "channels": "Каналы",
    "product_analysis": "Анализ по моделям",
    "drivers_antidrivers": "Драйверы и антидрайверы",
    "advertising_efficiency": "Эффективность рекламы",
    "ad_efficiency": "Эффективность рекламы",
    "operational_metrics": "Операционные метрики",
    "campaign_data": "Рекламные кампании", "campaign_analysis": "Рекламные кампании",
    "organic_vs_paid": "Органика vs Реклама",
    "organic_paid_split": "Органика vs Реклама",
    "funnel_analysis": "Воронка маркетинга",
    "model_efficiency": "Эффективность по моделям",
    "channel_mix": "Канальный микс",
    "price_matrix": "Ценовая матрица", "price_trends": "Тренды цен",
    "sales_trends": "Тренды продаж", "stock_price_matrix": "Матрица остатки-цена",
    "marketing_impact": "Влияние на маркетинг",
    "hypothesis_results": "Проверка гипотез",
    "bottleneck": "Узкие места", "bottlenecks": "Узкие места",
    "keyword_portfolio": "Ключевые слова", "keyword_analysis": "Анализ ключевых слов",
    "conversion_analysis": "Анализ конверсий",
    "brand_funnel": "Воронка бренда", "model_funnels": "Воронки по моделям",
    "revenue_and_orders_analysis": "Выручка и заказы",
    "margin_cascade": "Каскад маржинальности",
    "margin_analysis": "Каскад маржинальности",
    "channels_overview": "Площадки",
    "advisor_recommendations": "Рекомендации Advisor",
    "limitations": "Ограничения данных",
}


def _fl(key: str) -> str:
    """English key → Russian label."""
    if key in _FIELD_RU:
        return _FIELD_RU[key]
    label = key.replace("_", " ")
    for en, ru in [("rub", "₽"), ("pct", "%"), ("usd", "$")]:
        label = label.replace(f" {en}", f" {ru}")
    return label.capitalize()


def _fmt(v: Any) -> str:
    """Format a value for display in tables."""
    if v is None:
        return "—"
    if isinstance(v, bool):
        return "Да" if v else "Нет"
    if isinstance(v, float):
        if abs(v) >= 1000:
            return f"{v:,.0f}".replace(",", " ")
        if v == int(v) and abs(v) < 100:
            return str(int(v))
        return f"{v:.1f}"
    if isinstance(v, int):
        if abs(v) >= 1000:
            return f"{v:,}".replace(",", " ")
        return str(v)
    if isinstance(v, list):
        return ", ".join(str(x) for x in v[:5])
    if isinstance(v, dict):
        return "(см. ниже)"
    return str(v)


def _md_table(headers: list[str], rows: list[list]) -> str:
    """Build a Markdown table."""
    lines = ["| " + " | ".join(str(h) for h in headers) + " |"]
    lines.append("|" + "|".join(["---"] * len(headers)) + "|")
    for row in rows:
        cells = [_fmt(c) if not isinstance(c, str) else c for c in row]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def _list_to_table(items: list[dict]) -> str:
    """Render a list of uniform dicts as a table."""
    if not items:
        return ""
    keys: list[str] = []
    for item in items:
        for k in item:
            if k not in keys and not str(k).startswith("_"):
                keys.append(k)
    if not keys:
        return ""
    headers = [_fl(k) for k in keys]
    rows = [[item.get(k, "") for k in keys] for item in items]
    return _md_table(headers, rows)


def _append_data(lines: list[str], data: Any) -> None:
    """Recursively render data as markdown lines."""
    if isinstance(data, str):
        lines.append(data)
    elif isinstance(data, (int, float)):
        lines.append(_fmt(data))
    elif isinstance(data, list):
        if data and isinstance(data[0], dict):
            lines.append(_list_to_table(data))
        else:
            for item in data:
                lines.append(f"- {_fmt(item)}")
    elif isinstance(data, dict):
        simple: dict[str, Any] = {}
        complex_fields: list[tuple[str, Any]] = []
        for k, v in data.items():
            if str(k).startswith("_"):
                continue
            if isinstance(v, (dict, list)) and v:
                complex_fields.append((k, v))
            elif v is not None:
                simple[k] = v

        if simple:
            rows = [[_fl(k), _fmt(v)] for k, v in simple.items()]
            lines.append(_md_table(["Метрика", "Значение"], rows))

        for k, v in complex_fields:
            lines.append(f"\n### {_fl(k)}")
            _append_data(lines, v)

        interp = data.get("_interpretation") or data.get("interpretation")
        if interp and isinstance(interp, str) and "interpretation" not in simple:
            lines.append(f"\n**Интерпретация:** {interp}")


# ── Section rendering map ─────────────────────────────────────────────────────

_SECTION_MAP: list[tuple[str, str, int]] = [
    # Financial reports
    ("plan_fact", "План-Факт", 2), ("plan_vs_fact", "План-Факт", 2),
    ("financial_performance", "Ключевые изменения (Бренд)", 3),
    ("key_changes", "Ключевые изменения (Бренд)", 3),
    ("brand_metrics", "Ключевые изменения (Бренд)", 3),
    ("revenue_and_orders_analysis", "Выручка и заказы", 3),
    ("metrics", "Ключевые метрики", 3),
    ("pricing_strategy", "Цены, ценовая стратегия и динамика СПП", 4),
    ("margin_waterfall", "Сведение ΔМаржи (Reconciliation)", 5),
    ("margin_cascade", "Каскад маржинальности", 5),
    ("margin_analysis", "Каскад маржинальности", 5),
    ("cost_structure", "Структура затрат", 5),
    ("channel_analysis", "По каналам", 6), ("channels", "По каналам", 6),
    ("channels_overview", "Площадки", 6),
    ("wb_performance", "Wildberries", 6), ("ozon_performance", "OZON", 6),
    ("channel_breakdown", "Площадки", 6),
    ("model_performance", "По моделям", 7), ("models", "По моделям", 7),
    ("product_analysis", "Модели", 7),
    ("drivers", "Драйверы прибыли", 7), ("anti_drivers", "Антидрайверы", 7),
    ("drivers_antidrivers", "Драйверы и антидрайверы", 7),
    ("advertising_efficiency", "Эффективность рекламы", 8),
    ("ad_efficiency", "Эффективность рекламы", 8),
    ("ad_stats", "Статистика рекламы", 8),
    ("funnel", "Воронка продаж", 8), ("funnel_analysis", "Воронка", 8),
    ("brand_funnel", "Воронка бренда", 8),
    ("hypotheses", "Гипотезы → Действия → Метрики контроля", 9),
    ("hypothesis_results", "Проверка гипотез", 9),
    ("recommendations", "Рекомендации", 9), ("action_plan", "План действий", 9),
    ("advisor_recommendations", "Рекомендации Advisor", 9),
    ("summary", "Итог", 10), ("conclusions", "Выводы", 10),
    # Marketing
    ("campaign_data", "Рекламные кампании", 2),
    ("campaign_analysis", "Рекламные кампании", 2),
    ("organic_vs_paid", "Органика vs Реклама", 3),
    ("organic_paid_split", "Органика vs Реклама", 3),
    ("model_efficiency", "Эффективность по моделям", 5),
    ("channel_mix", "Канальный микс", 6),
    # Funnel
    ("model_funnels", "Воронки по моделям", 3),
    ("bottleneck", "Узкие места", 4), ("bottlenecks", "Узкие места", 4),
    ("keyword_portfolio", "Ключевые слова", 5),
    ("keyword_analysis", "Анализ ключевых слов", 5),
    ("conversion_analysis", "Анализ конверсий", 3),
    # Price
    ("price_matrix", "Ценовая матрица", 2), ("price_trends", "Тренды цен", 3),
    ("sales_trends", "Тренды продаж", 3),
    ("stock_price_matrix", "Матрица остатки-цена", 4),
    ("marketing_impact", "Влияние на маркетинг", 5),
]

_SKIP_KEYS = frozenset({
    "detailed_report", "telegram_summary", "meta", "executive_summary",
    "report_type", "period", "comparison_period", "channel", "task_type",
    "sections_included", "sections_skipped", "warnings", "_meta",
})


# ── Main entry points ─────────────────────────────────────────────────────────

def ensure_report_fields(report: dict) -> dict:
    """Convert structured JSON artifact to detailed_report + telegram_summary.

    Deterministic template-based conversion — produces consistent output
    regardless of LLM model behavior.
    """
    if not report or not isinstance(report, dict):
        return report

    existing = report.get("detailed_report", "")
    if isinstance(existing, str) and len(existing) >= 3000:
        # Check quality: must have toggle headers (## ▶) and Russian text
        has_toggles = "## ▶" in existing
        has_russian = bool(re.search(r'[а-яА-ЯёЁ]', existing))
        if has_toggles and has_russian:
            return report
        logger.warning(
            "detailed_report exists (%d chars) but quality check failed "
            "(toggles=%s, russian=%s) — rebuilding from JSON",
            len(existing), has_toggles, has_russian,
        )
    elif existing and not isinstance(existing, str):
        # Compiler returned a dict/list instead of string — force rebuild
        logger.warning("detailed_report is %s, not string — rebuilding", type(existing).__name__)
        existing = ""

    # Flatten nested report wrapper keys
    _WRAPPER_KEYS = {
        "daily_report", "weekly_report", "monthly_report",
        "marketing_weekly", "marketing_monthly", "marketing_daily",
        "funnel_weekly", "price_analysis", "finolog_weekly",
    }
    for rk in _WRAPPER_KEYS:
        nested = report.get(rk)
        if isinstance(nested, dict):
            for k, v in nested.items():
                if k not in report or not report[k]:
                    report[k] = v
            break

    lines: list[str] = []

    # ── Section 0: Passport ──
    meta = report.get("meta") or {}
    if meta and isinstance(meta, dict):
        lines.append("## ▶ 0. Паспорт отчёта")
        passport_rows: list[list[str]] = []
        period = meta.get("period")
        if period:
            if isinstance(period, dict):
                passport_rows.append(["Период", str(period.get("current", ""))])
                if period.get("previous"):
                    passport_rows.append(["Сравнение", str(period["previous"])])
            else:
                passport_rows.append(["Период", str(period)])
        channels = meta.get("channels")
        if channels:
            passport_rows.append([
                "Каналы",
                ", ".join(channels) if isinstance(channels, list) else str(channels),
            ])
        conf = meta.get("confidence")
        if conf is not None:
            marker = "🟢" if conf >= 0.75 else ("🟡" if conf >= 0.45 else "🔴")
            passport_rows.append(["Достоверность", f"{marker} {conf}"])
        if passport_rows:
            lines.append(_md_table(["Параметр", "Значение"], passport_rows))
        lims = meta.get("limitations")
        if lims and isinstance(lims, list):
            lines.append("\n**Ограничения:**")
            for lim in lims:
                lines.append(f"- {lim}")
        lines.append("")

    # ── Section 1: Executive summary ──
    es = report.get("executive_summary") or {}
    if isinstance(es, dict) and (es.get("headline") or es.get("key_insights")):
        lines.append("## ▶ 1. Ключевые выводы")
        if es.get("headline"):
            lines.append(f"**{es['headline']}**\n")
        for insight in (es.get("key_insights") or []):
            lines.append(f"- {insight}")
        lines.append("")

    # ── Render mapped sections ──
    rendered_keys: set[str] = set(_SKIP_KEYS)
    rendered_nums: set[int] = set()

    for key, title, num in _SECTION_MAP:
        if key not in report or key in rendered_keys:
            continue
        data = report[key]
        if not data:
            continue
        if num in rendered_nums:
            rendered_keys.add(key)
            continue

        lines.append(f"## ▶ {num}. {title}")
        _append_data(lines, data)
        lines.append("")
        rendered_keys.add(key)
        rendered_nums.add(num)

    # ── Catch-all: remaining structured data ──
    next_num = max(rendered_nums, default=10) + 1
    for key, value in report.items():
        if key in rendered_keys or str(key).startswith("_") or not value:
            continue
        title = _fl(key)
        lines.append(f"## ▶ {next_num}. {title}")
        _append_data(lines, value)
        lines.append("")
        rendered_keys.add(key)
        next_num += 1

    detailed = "\n".join(lines)

    # ── Build telegram summary from executive_summary ──
    tg_lines: list[str] = []
    if isinstance(es, dict):
        if es.get("headline"):
            tg_lines.append(f"[b]{es['headline']}[/b]")
        for insight in (es.get("key_insights") or [])[:5]:
            tg_lines.append(f"• {insight}")

    report["detailed_report"] = detailed
    report["telegram_summary"] = "\n".join(tg_lines) if tg_lines else ""

    logger.info(
        "Fallback formatter: JSON → markdown (%d chars) + telegram (%d chars)",
        len(detailed), len(report["telegram_summary"]),
    )
    return report


def fill_telegram_summary(report: dict) -> None:
    """Generate telegram_summary from report data if missing.

    Uses structured fields first, then extracts from detailed_report markdown.
    Deterministic — no LLM dependency.
    """
    if not report or not isinstance(report, dict):
        return
    if (report.get("telegram_summary") or "").strip():
        return

    lines: list[str] = []

    # Strategy 1: structured data (executive_summary)
    es = report.get("executive_summary") or {}
    if isinstance(es, dict):
        if es.get("headline"):
            lines.append(f"[b]{es['headline']}[/b]")
        for insight in (es.get("key_insights") or [])[:5]:
            lines.append(f"• {insight}")

    # Strategy 2: meta for period
    if not lines:
        meta = report.get("meta") or {}
        if isinstance(meta, dict) and meta.get("period"):
            period = meta["period"]
            if isinstance(period, dict):
                lines.append(f"[b]Отчёт за {period.get('current', '')}[/b]")
            else:
                lines.append(f"[b]Отчёт за {period}[/b]")

    # Strategy 3: extract from detailed_report markdown
    if not lines:
        detailed = (report.get("detailed_report") or "").strip()
        if not detailed:
            return

        # Title
        heading = re.search(r'^#\s+(.+)', detailed, re.MULTILINE)
        if heading:
            lines.append(f"[b]{heading.group(1)}[/b]")

        # Interpretation paragraphs (best insights)
        interps = re.findall(r'\*\*Интерпретация:\*\*\s*(.+)', detailed)
        for interp in interps[:3]:
            first_sentence = interp.split('.')[0].strip()
            if first_sentence and len(first_sentence) < 200:
                lines.append(f"• {first_sentence}")

        # Bullet points
        if len(lines) < 3:
            bullets = re.findall(r'^[-•]\s+(.+)', detailed, re.MULTILINE)
            for b in bullets[:5]:
                if sum(len(ln) for ln in lines) > 600:
                    break
                lines.append(f"• {b}")

    summary = "\n".join(lines)
    if summary:
        report["telegram_summary"] = summary
        logger.info("Fallback: telegram_summary generated (%d chars)", len(summary))


# ── Compiler format enforcement prompt ────────────────────────────────────────

COMPILER_FORMAT_INSTRUCTIONS = (
    "\n\nФОРМАТ ОТВЕТА (СТРОГО):\n"
    "JSON с полями:\n"
    '- "detailed_report": СТРОКА Markdown (## ▶ заголовки, | таблицы |, '
    "**интерпретации** после таблиц). НЕ вложенный JSON-объект, а СТРОКА.\n"
    '- "telegram_summary": СТРОКА BBCode (5-8 строк KPI).\n'
    '- "sections_included": [int]\n'
    '- "sections_skipped": [{section, reason}]\n'
    '- "warnings": [string]\n'
    "\n"
    "КРИТИЧЕСКИ ВАЖНО: detailed_report ОБЯЗАН содержать ВСЕ 12 секций (0-11).\n"
    "Пропуск любой секции = ПРОВАЛ. Ниже — полный скелет, каждая секция ОБЯЗАТЕЛЬНА:\n"
    "\n"
    "## ▶ 0. Паспорт отчёта\n"
    "Таблица: Параметр | Значение (период, сравнение, полнота данных, лаг, невязка)\n\n"
    "## ▶ 1. Топ-выводы и действия\n"
    "Таблица: ₽ эффект | Что → Гипотеза → Действие (3-5 строк)\n\n"
    "## ▶ 2. План-факт (Месяц)\n"
    "Таблица: Метрика | План | Факт MTD | План MTD | Выполнение % | Прогноз | Статус\n"
    "По каналам: WB/OZON (выполнение маржи)\n\n"
    "## ▶ 3. Ключевые изменения (Бренд)\n"
    "ПОЛНАЯ таблица 19 строк + текстовая интерпретация (4-5 пунктов)\n\n"
    "## ▶ 4. Цены, ценовая стратегия и динамика СПП\n"
    "Таблица 4а — СПП по каналам + Таблица 4б — средние цены + прогноз\n\n"
    "## ▶ 5. Сведение ΔМаржи (Reconciliation)\n"
    "Таблица РОВНО 10 строк: Выручка, Себестоимость/ед, Комиссия до СПП, Логистика/ед, "
    "Хранение/ед, Внутр.реклама, Внешн.реклама, Прочие, НДС, Невязка + Итого ΔМаржи\n\n"
    "## ▶ 6. Wildberries\n"
    "6.1.1 Объём и прибыльность WB — таблица метрик канала\n"
    "6.1.2 Модельная декомпозиция WB — ВСЕ модели (НЕ топ-3!): "
    "Model | Маржа₽ | ΔМаржа% | Маржинальность% | Остаток FBO | Свой склад | Итого | "
    "Оборач.дн | ROI% | ДРР% | Комментарий\n"
    "6.1.2.1 Анализ по статусам WB — группировка: Продаётся/Запуск/Выводим\n"
    "6.1.3 Воронка WB — объёмы + эффективность (CTR, CR→корзина, CR→заказ)\n"
    "6.1.4 Структура затрат WB — доли от выручки\n"
    "6.1.5 Реклама WB — итоги + детальная таблица\n"
    "Текстовая интерпретация WB\n\n"
    "## ▶ 7. OZON\n"
    "(аналогично WB: объём, ВСЕ модели, статусы, затраты, реклама)\n\n"
    "## ▶ 8. Модели — драйверы/антидрайверы\n"
    "Драйверы WB, Антидрайверы WB, Драйверы/Антидрайверы OZON — расширенные таблицы\n\n"
    "## ▶ 9. Гипотезы → действия → метрики контроля\n"
    "Таблица 10 колонок: Приоритет | Объект | Гипотеза | Действие | "
    "Метрика контроля | База | Цель | Ожидаемый эффект | Окно проверки | Риски\n\n"
    "## ▶ 10. Рекомендации Advisor\n"
    "🔴 Критичные (делай сегодня) → 🟡 Внимание → 🟢 Позитивные сигналы\n\n"
    "## ▶ 11. Итог\n"
    "10-20 строк: что изменилось, почему, что повлияло сильнее всего, что делать первым\n"
    "\nПример telegram_summary (только формат):\n"
    '"[b]Сводка за 19 марта 2026:[/b]\\n'
    "• Маржа: 255.2 тыс (-8.8% к вчера)\\n"
    "• Заказы: 1 164 шт (+9.9%)\\n"
    "• WB: маржа 210.0 тыс (-14.1%)\\n"
    "• OZON: маржа 45.2 тыс (+28.3%)\\n"
    '• 📊 План MTD: маржа 89% | прогноз 7.6M vs план 8.5M"\n'
)
