"""
ReportFormatter — formats reports for Telegram and Notion.

Reuses v1 report_formatter logic adapted for v2 chain results.
"""
import html
import logging
import re
from typing import List

logger = logging.getLogger(__name__)

# Max Telegram message length
MAX_TELEGRAM_MSG = 4000


def _bbcode_to_html(text: str) -> str:
    """Convert BBCode [b]...[/b] tags to HTML <b>...</b>."""
    return re.sub(r'\[b\](.*?)\[/b\]', r'<b>\1</b>', text)


def escape_html_safe(text: str) -> str:
    """Escape HTML special chars (&, <, >) in text, preserving allowed TG tags.

    Allowed tags: <b>, <i>, <a href="...">.
    """
    # Extract allowed tags, escape the rest, then restore tags
    _ALLOWED_TAG = re.compile(
        r'(</?(?:b|i|u|s|code|pre|a)(?: [^>]*)?>)', re.IGNORECASE,
    )
    parts = _ALLOWED_TAG.split(text)
    result = []
    for i, part in enumerate(parts):
        if i % 2 == 1:
            # This is an allowed HTML tag — keep as-is
            result.append(part)
        else:
            # Regular text — escape HTML entities
            result.append(html.escape(part, quote=False))
    return "".join(result)


def split_html_message(text: str, max_length: int = MAX_TELEGRAM_MSG) -> List[str]:
    """Split long message into chunks, breaking at paragraph boundaries."""
    text = _bbcode_to_html(text)
    text = escape_html_safe(text)
    if len(text) <= max_length:
        return [text]

    chunks = []
    while text:
        if len(text) <= max_length:
            chunks.append(text)
            break

        # Find a good split point
        split_at = max_length
        for sep in ["\n\n", "\n", ". ", " "]:
            idx = text.rfind(sep, 0, max_length)
            if idx > max_length // 2:
                split_at = idx + len(sep)
                break

        chunks.append(text[:split_at].rstrip())
        text = text[split_at:].lstrip()

    return chunks


def add_caveats_header(text: str, caveats: List[str]) -> str:
    """Add data quality warnings to the beginning of a report."""
    if not caveats:
        return text

    warning_lines = ["⚠️ <b>Предупреждения о качестве данных:</b>"]
    for caveat in caveats:
        warning_lines.append(f"  • {caveat}")
    warning_lines.append("")

    return "\n".join(warning_lines) + text


def format_cost_footer(cost_usd: float, chain_steps: int, duration_ms: int) -> str:
    """Format cost/performance footer for reports."""
    duration_sec = duration_ms / 1000
    return (
        f"\n\n<i>Стоимость: ${cost_usd:.4f} | "
        f"Шагов: {chain_steps} | "
        f"Время: {duration_sec:.1f}с</i>"
    )
