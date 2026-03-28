# agents/reporter/formatter/telegram.py
"""Render ReportInsights → Telegram HTML summary."""
from __future__ import annotations

from agents.reporter.analyst.schemas import ReportInsights
from agents.reporter.collector.base import CollectedData
from agents.reporter.types import ReportScope

MAX_TELEGRAM_MSG = 4000


def _fmt(num: float) -> str:
    return f"{int(round(num)):,}".replace(",", " ")


def _arrow(current: float, previous: float) -> str:
    if previous == 0:
        return "→"
    change = (current - previous) / abs(previous) * 100
    if change > 1:
        return "▲"
    elif change < -1:
        return "▼"
    return "→"


def _change(current: float, previous: float) -> str:
    if previous == 0:
        return ""
    change = (current - previous) / abs(previous) * 100
    sign = "+" if change > 0 else ""
    return f"({sign}{change:.1f}%)"


def _confidence_emoji(c: float) -> str:
    if c >= 0.8:
        return "🟢"
    elif c >= 0.5:
        return "🟡"
    return "🔴"


def render_telegram(
    insights: ReportInsights,
    data: CollectedData,
    scope: ReportScope,
    notion_url: str | None = None,
    meta: dict | None = None,
) -> str:
    """Render compact Telegram HTML message."""
    type_labels = {
        "financial_daily": "📊 Дневной фин. отчёт",
        "financial_weekly": "📈 Недельный фин. отчёт",
        "financial_monthly": "📅 Месячный фин. отчёт",
        "marketing_weekly": "📢 Маркетинг (неделя)",
        "marketing_monthly": "📢 Маркетинг (месяц)",
        "funnel_weekly": "🔄 Воронка (неделя)",
        "funnel_monthly": "🔄 Воронка (месяц)",
    }
    label = type_labels.get(scope.report_type.value, "📊 Отчёт")

    lines = [
        f"<b>{label}</b>",
        f"<i>{scope.period_str}</i>",
        "",
        insights.executive_summary,
        "",
        "<b>Ключевые метрики:</b>",
        f"  Выручка: {_fmt(data.current.revenue_before_spp)} ₽ "
        f"{_arrow(data.current.revenue_before_spp, data.previous.revenue_before_spp)} "
        f"{_change(data.current.revenue_before_spp, data.previous.revenue_before_spp)}",
        f"  Маржа: {_fmt(data.current.margin)} ₽ ({data.current.margin_pct:.1f}%) "
        f"{_arrow(data.current.margin, data.previous.margin)} "
        f"{_change(data.current.margin, data.previous.margin)}",
        f"  ДРР: {data.current.drr_pct:.1f}% "
        f"{_arrow(data.current.drr_pct, data.previous.drr_pct)}",
        f"  Заказы: {_fmt(data.current.orders_count)} шт "
        f"{_arrow(data.current.orders_count, data.previous.orders_count)} "
        f"{_change(data.current.orders_count, data.previous.orders_count)}",
    ]

    # TOP recommendations (up to 3)
    rec_sections = [s for s in insights.sections if s.section_id == 11]
    if rec_sections and rec_sections[0].root_causes:
        lines.append("")
        lines.append("<b>Рекомендации:</b>")
        for rc in rec_sections[0].root_causes[:3]:
            lines.append(f"  • {rc.recommendation}")

    # Footer
    lines.append("")
    conf = _confidence_emoji(insights.overall_confidence)
    footer = f"{conf} Confidence: {insights.overall_confidence:.0%}"
    if meta:
        tokens = meta.get("input_tokens", 0) + meta.get("output_tokens", 0)
        footer += f" | Tokens: {tokens:,}"
    lines.append(footer)

    if notion_url:
        lines.append(f'\n📄 <a href="{notion_url}">Полный отчёт в Notion</a>')

    text = "\n".join(lines)
    if len(text) > MAX_TELEGRAM_MSG:
        text = text[:MAX_TELEGRAM_MSG - 50] + "\n\n... <i>полный отчёт в Notion</i>"

    return text
