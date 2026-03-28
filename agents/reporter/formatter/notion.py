# agents/reporter/formatter/notion.py
"""Render ReportInsights + CollectedData → Notion markdown via Jinja2."""
from __future__ import annotations

import logging
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from agents.reporter.analyst.schemas import ReportInsights
from agents.reporter.collector.base import CollectedData
from agents.reporter.config import TEMPLATES_DIR
from agents.reporter.types import ReportScope

logger = logging.getLogger(__name__)

_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    trim_blocks=True,
    lstrip_blocks=True,
)


def _safe_div(a: float, b: float) -> float:
    return round(a / b * 100, 2) if b else 0.0


def _format_num(num: float, decimals: int = 0) -> str:
    """Format number with space thousands (Russian style)."""
    if decimals == 0:
        formatted = f"{int(round(num)):,}".replace(",", " ")
    else:
        formatted = f"{num:,.{decimals}f}".replace(",", " ")
    return formatted


def _arrow(current: float, previous: float) -> str:
    if previous == 0:
        return "→"
    change = (current - previous) / abs(previous) * 100
    if change > 1:
        return "▲"
    elif change < -1:
        return "▼"
    return "→"


def _change_pct(current: float, previous: float) -> str:
    if previous == 0:
        return "n/a"
    change = (current - previous) / abs(previous) * 100
    sign = "+" if change > 0 else ""
    return f"{sign}{change:.1f}%"


def render_notion(
    insights: ReportInsights,
    data: CollectedData,
    scope: ReportScope,
) -> str:
    """Render full Notion markdown report."""
    template_name = f"{scope.report_type.value}.md.j2"
    try:
        template = _env.get_template(template_name)
    except Exception:
        logger.warning("Template %s not found, using fallback", template_name)
        template = _env.get_template("financial_daily.md.j2")

    return template.render(
        insights=insights,
        data=data,
        scope=scope,
        fmt=_format_num,
        arrow=_arrow,
        change_pct=_change_pct,
        safe_div=_safe_div,
    )
