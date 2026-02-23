"""
Report Formatter — форматирование отчётов для Telegram.

BBCode→HTML, Notion ссылка, стоимость токенов, клавиатура.
"""
import logging
import re
from typing import Optional, Dict, Any

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


class ReportFormatter:
    """Форматирование отчётов для Telegram"""

    @staticmethod
    def sanitize_report_md(result: dict) -> str:
        """
        Ensure detailed_report is safe Markdown (not raw JSON) and keep it in result.
        """
        report_md = (result or {}).get("detailed_report", "") or ""

        if '"brief_summary"' in report_md or '"detailed_report"' in report_md:
            logging.getLogger(__name__).warning(
                "Sanitizing detailed_report: detected raw JSON, falling back to brief_summary"
            )
            report_md = (result or {}).get("brief_summary", "") or ""

        if result is not None:
            result["detailed_report"] = report_md

        return report_md

    @staticmethod
    def split_html_message(text: str, limit: int = 4000) -> list[str]:
        """
        Split long HTML text into chunks without breaking paragraphs.

        Strategy:
        - Prefer splitting on double newlines within limit.
        - If a single paragraph is too long, fallback to single newline.
        - If still too long, hard-cut at limit.
        """
        if len(text) <= limit:
            return [text]

        def _split_by_delimiter(s: str, delim: str) -> list[str]:
            chunks = []
            current = ""
            parts = s.split(delim)
            for p in parts:
                segment = p if current == "" else current + delim + p
                if len(segment) > limit:
                    if current:
                        chunks.append(current)
                        current = p
                    else:
                        # hard cut
                        chunks.extend([p[i:i + limit] for i in range(0, len(p), limit)])
                        current = ""
                else:
                    current = segment
            if current:
                chunks.append(current)
            return chunks

        # Try double newline first
        chunks = _split_by_delimiter(text, "\n\n")
        if all(len(c) <= limit for c in chunks):
            return chunks

        # Fallback: single newline
        chunks = _split_by_delimiter(text, "\n")
        if all(len(c) <= limit for c in chunks):
            return chunks

        # Last resort: hard cuts already applied inside helper
        return chunks

    @staticmethod
    def format_for_telegram(
        brief_summary: str,
        notion_url: Optional[str] = None,
        cost_info: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Форматирует отчёт для отправки в Telegram.

        Args:
            brief_summary: Краткая сводка (BBCode)
            notion_url: Ссылка на страницу Notion
            cost_info: Информация о токенах и стоимости

        Returns:
            HTML-текст для Telegram
        """
        # Convert BBCode to HTML
        html = ReportFormatter.bbcode_to_html(brief_summary)

        # Add Notion link
        if notion_url:
            html += f'\n\n<a href="{notion_url}">Подробный отчёт в Notion</a>'

        # Add cost line
        if cost_info:
            if isinstance(cost_info, str):
                cost_line = cost_info
            else:
                cost_line = ReportFormatter.format_cost_line(cost_info)
            html += f"\n\n{cost_line}"

        return html

    @staticmethod
    def bbcode_to_html(text: str) -> str:
        """
        Конвертирует BBCode в HTML для Telegram.

        [b]...[/b] → <b>...</b>
        """
        if not text:
            return ""

        # BBCode bold → HTML bold
        text = re.sub(r'\[b\](.*?)\[/b\]', r'<b>\1</b>', text, flags=re.DOTALL)

        # Escape HTML special chars (except our tags)
        # First, protect our tags
        text = text.replace('<b>', '\x00B\x00')
        text = text.replace('</b>', '\x00/B\x00')
        text = text.replace('<a ', '\x00A \x00')
        text = text.replace('</a>', '\x00/A\x00')

        # Escape
        text = text.replace('&', '&amp;')
        text = text.replace('<', '&lt;')
        text = text.replace('>', '&gt;')

        # Restore our tags
        text = text.replace('\x00B\x00', '<b>')
        text = text.replace('\x00/B\x00', '</b>')
        text = text.replace('\x00A \x00', '<a ')
        text = text.replace('\x00/A\x00', '</a>')

        return text

    @staticmethod
    def format_cost_line(cost_info: dict) -> str:
        """
        Форматирует строку стоимости токенов.

        Args:
            cost_info: {
                "usage": {"input_tokens": N, "output_tokens": N},
                "cost_usd": 0.05,
                "provider": "claude-opus-4-6"
            }

        Returns:
            Строка вида: "2 847 in + 1 523 out | ~$0.05 (Claude Opus)"
        """
        usage = cost_info.get("usage", {})
        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)
        cost = cost_info.get("cost_usd", 0)
        provider = cost_info.get("provider", "")

        # Format provider name
        provider_name = {
            "claude-opus-4-6": "Claude Opus",
            "claude-sonnet-4-5-20250929": "Claude Sonnet",
            "moonshotai/kimi-k2.5": "Kimi K2.5",
            "glm-4-plus": "z.ai GLM Plus",
            "glm-4.5-flash": "z.ai GLM Flash",
        }.get(provider, provider)

        in_str = f"{input_tokens:,}".replace(",", " ")
        out_str = f"{output_tokens:,}".replace(",", " ")

        return f"{in_str} in + {out_str} out | ~${cost:.2f} ({provider_name})"

    @staticmethod
    def create_report_keyboard(
        report_type: str = "daily",
        has_notion: bool = True,
    ) -> InlineKeyboardMarkup:
        """
        Создаёт клавиатуру для отчёта.

        Кнопки: [Дать обратную связь] [Ещё отчёт] [Главное меню]
        """
        buttons = []

        # Feedback button
        buttons.append([
            InlineKeyboardButton(
                text="Дать обратную связь",
                callback_data=f"feedback_start:{report_type}"
            )
        ])

        # Navigation
        buttons.append([
            InlineKeyboardButton(text="Ещё отчёт", callback_data="menu_reports"),
            InlineKeyboardButton(text="Главное меню", callback_data="menu_main"),
        ])

        return InlineKeyboardMarkup(inline_keyboard=buttons)

    @staticmethod
    def create_feedback_keyboard() -> InlineKeyboardMarkup:
        """Клавиатура после отправки feedback."""
        return InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="Ещё отчёт", callback_data="menu_reports"),
                InlineKeyboardButton(text="Главное меню", callback_data="menu_main"),
            ]
        ])
