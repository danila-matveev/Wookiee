"""
Telegram delivery adapter for Wookiee v3.

Formats orchestrator report dicts into Telegram HTML messages
and sends them via aiogram Bot.
"""
from __future__ import annotations
import html
import logging
import re

from aiogram import Bot

logger = logging.getLogger(__name__)

MAX_TELEGRAM_MSG = 4000
# Максимальная длина telegram_summary — если compiler вывалил весь отчёт,
# обрезаем до разумного размера и ссылаем на Notion.
MAX_SUMMARY_LEN = 1500


# ---------------------------------------------------------------------------
# Formatting helpers (ported from agents/oleg/bot/formatter.py)
# ---------------------------------------------------------------------------

def _bbcode_to_html(text: str) -> str:
    """Convert [b]...[/b] BBCode tags to <b>...</b> HTML."""
    return re.sub(r'\[b\](.*?)\[/b\]', r'<b>\1</b>', text)


def escape_html_safe(text: str) -> str:
    """Escape HTML but preserve allowed Telegram tags (b, i, u, s, code, pre, a)."""
    _ALLOWED_TAG = re.compile(
        r'(</?(?:b|i|u|s|code|pre|a)(?: [^>]*)?>)', re.IGNORECASE,
    )
    parts = _ALLOWED_TAG.split(text)
    result = []
    for i, part in enumerate(parts):
        if i % 2 == 1:
            result.append(part)
        else:
            result.append(html.escape(part, quote=False))
    return "".join(result)


def split_html_message(text: str, max_length: int = MAX_TELEGRAM_MSG) -> list[str]:
    """Split a potentially long HTML message into Telegram-safe chunks."""
    text = _bbcode_to_html(text)
    text = escape_html_safe(text)
    if len(text) <= max_length:
        return [text]
    chunks: list[str] = []
    while text:
        if len(text) <= max_length:
            chunks.append(text)
            break
        split_at = max_length
        for sep in ["\n\n", "\n", ". ", " "]:
            idx = text.rfind(sep, 0, max_length)
            if idx > max_length // 2:
                split_at = idx + len(sep)
                break
        chunks.append(text[:split_at].rstrip())
        text = text[split_at:].lstrip()
    return chunks


def add_caveats_header(text: str, caveats: list[str]) -> str:
    """Prepend data-quality warnings to the message."""
    if not caveats:
        return text
    warning_lines = ["\u26a0\ufe0f <b>Предупреждения о качестве данных:</b>"]
    for caveat in caveats:
        warning_lines.append(f"  \u2022 {caveat}")
    warning_lines.append("")
    return "\n".join(warning_lines) + text


def format_cost_footer(
    cost_usd: float | None = None,
    chain_steps: int | None = None,
    duration_ms: int | None = None,
) -> str:
    """Build an italic footer with cost / steps / duration info."""
    parts: list[str] = []
    if cost_usd is not None:
        parts.append(f"${cost_usd:.4f}")
    if chain_steps is not None:
        parts.append(f"Шагов: {chain_steps}")
    if duration_ms is not None:
        duration_sec = duration_ms / 1000
        parts.append(f"Время: {duration_sec:.1f}с")
    if not parts:
        return ""
    return f"\n\n<i>Стоимость: {' | '.join(parts)}</i>"


# ---------------------------------------------------------------------------
# High-level API
# ---------------------------------------------------------------------------

def format_report_message(
    report: dict,
    page_url: str | None = None,
    caveats: list[str] | None = None,
) -> str:
    """Assemble the full Telegram message from an orchestrator result dict.

    ``report`` is the orchestrator output containing at least:
      - report.report.telegram_summary
      - report.agents_called / agents_succeeded / agents_failed
      - report.duration_ms
    """
    inner = report.get("report", {})
    body = inner.get("telegram_summary") or ""

    # Обрезаем слишком длинный summary (compiler иногда вываливает весь отчёт)
    if len(body) > MAX_SUMMARY_LEN:
        # Обрезаем по последнему полному абзацу до лимита
        cut = body[:MAX_SUMMARY_LEN].rfind("\n\n")
        if cut < MAX_SUMMARY_LEN // 2:
            cut = body[:MAX_SUMMARY_LEN].rfind("\n")
        if cut < MAX_SUMMARY_LEN // 3:
            cut = MAX_SUMMARY_LEN
        body = body[:cut].rstrip()
        body += "\n\n<i>... полный отчёт ниже по ссылке</i>"

    if caveats:
        body = add_caveats_header(body, caveats)

    if page_url:
        body += f'\n\n<a href="{page_url}">📋 Полный отчёт в Notion</a>'

    agents_called = report.get("agents_called", 0) or 0
    agents_succeeded = report.get("agents_succeeded", 0) or 0
    agents_failed = report.get("agents_failed", 0)
    duration_ms = report.get("duration_ms", 0) or 0

    # Trust Envelope + Cost in footer
    agg_confidence = report.get("aggregate_confidence")
    worst_lim = report.get("worst_limitation")
    total_cost = report.get("total_cost_usd", 0.0)

    # Confidence marker
    if agg_confidence is not None:
        if agg_confidence >= 0.75:
            conf_marker = f"🟢 {agg_confidence}"
        elif agg_confidence >= 0.45:
            conf_marker = f"🟡 {agg_confidence}"
        else:
            conf_marker = f"🔴 {agg_confidence}"
    else:
        conf_marker = None

    # Build footer parts
    footer_parts = []
    if conf_marker:
        footer_parts.append(conf_marker)
    if total_cost > 0:
        footer_parts.append(f"${total_cost:.4f}")
    footer_parts.append(f"Агентов: {agents_succeeded}/{agents_called}")
    footer_parts.append(f"{duration_ms / 1000:.1f}с")

    body += f"\n\n<i>{' | '.join(footer_parts)}</i>"

    # Worst limitation line (if yellow/red)
    if worst_lim and agg_confidence is not None and agg_confidence < 0.75:
        body += f"\n<i>⚠️ {worst_lim}</i>"

    return body


async def send_report(
    bot_token: str,
    chat_ids: list[int],
    report: dict,
    page_url: str | None = None,
    caveats: list[str] | None = None,
) -> dict:
    """Send a formatted report to all specified Telegram chats.

    Returns ``{"sent": bool, "chat_ids_sent": [...], "errors": [...]}``.
    """
    message = format_report_message(report, page_url=page_url, caveats=caveats)
    chunks = split_html_message(message)

    bot = Bot(token=bot_token)
    chat_ids_sent: list[int] = []
    errors: list[str] = []

    try:
        for chat_id in chat_ids:
            try:
                for chunk in chunks:
                    await bot.send_message(
                        chat_id=chat_id,
                        text=chunk,
                        parse_mode="HTML",
                        disable_web_page_preview=True,
                    )
                chat_ids_sent.append(chat_id)
            except Exception as exc:
                err_msg = f"chat_id={chat_id}: {exc}"
                logger.error(f"Telegram send failed — {err_msg}")
                errors.append(err_msg)
    finally:
        await bot.session.close()

    return {
        "sent": len(chat_ids_sent) > 0,
        "chat_ids_sent": chat_ids_sent,
        "errors": errors,
    }
