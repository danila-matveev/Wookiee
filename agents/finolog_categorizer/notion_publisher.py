"""
Publish categorization results to Notion as a daily report page.

Creates a structured page with tables for:
- Auto-categorized (high confidence)
- Needs confirmation (medium confidence)
- Unknown (no match)
- Overdue planned transactions
- Previous day's feedback summary
"""
from __future__ import annotations

import logging
from datetime import date

from agents.oleg.services.notion_service import NotionService
from .categorizer import Suggestion
from .store import CategorizerStore

logger = logging.getLogger(__name__)


def _fmt_amount(value: float) -> str:
    sign = "+" if value > 0 else ""
    return f"{sign}{value:,.0f} ₽".replace(",", " ")


def _fmt_date(d: str) -> str:
    """Convert YYYY-MM-DD to DD.MM."""
    try:
        parts = d.split("-")
        return f"{parts[2]}.{parts[1]}"
    except (IndexError, AttributeError):
        return d


def _fmt_confidence(c: float) -> str:
    return f"{c:.0%}"


class NotionPublisher:
    """Build and publish daily categorization report to Notion."""

    def __init__(self, notion: NotionService, store: CategorizerStore):
        self.notion = notion
        self.store = store

    async def publish(
        self,
        scan_date: date,
        high_confidence: list[Suggestion],
        medium_confidence: list[Suggestion],
        unknown: list[dict],
        overdue_planned: list[dict],
        feedback_summary: dict | None = None,
        cat_map: dict[int, str] | None = None,
    ) -> str | None:
        """
        Publish categorization report to Notion.

        Returns Notion page URL or None.
        """
        cat_map = cat_map or {}
        date_str = scan_date.isoformat()

        # Build markdown report
        md = self._build_markdown(
            scan_date, high_confidence, medium_confidence,
            unknown, overdue_planned, feedback_summary, cat_map,
        )

        # Sync to Notion
        page_url = await self.notion.sync_report(
            start_date=date_str,
            end_date=date_str,
            report_md=md,
            source="Finolog Categorizer (auto)",
            report_type="finolog_categorization",
        )

        if not page_url:
            return None

        # Extract page_id from URL and save page mappings for feedback
        page_id = self._extract_page_id(page_url)
        if page_id:
            self._save_page_mappings(page_id, medium_confidence, unknown)

        return page_url

    def _build_markdown(
        self,
        scan_date: date,
        high: list[Suggestion],
        medium: list[Suggestion],
        unknown: list[dict],
        overdue: list[dict],
        feedback: dict | None,
        cat_map: dict[int, str],
    ) -> str:
        lines: list[str] = []

        # Summary
        lines.append("## Результат сканирования")
        lines.append(f"- Новых операций: {len(high) + len(medium) + len(unknown)}")
        lines.append(f"- Авто-категоризировано (>85%): {len(high)}")
        lines.append(f"- Нужно подтверждение: {len(medium)}")
        lines.append(f"- Не удалось определить: {len(unknown)}")
        lines.append(f"- Просроченных плановых: {len(overdue)}")
        lines.append("")

        # Feedback summary
        if feedback:
            lines.append("## Обратная связь по вчерашнему отчёту")
            lines.append(f"- Считано комментариев: {feedback.get('total_comments', 0)}")
            lines.append(f"- Применено правил: {feedback.get('rules_applied', 0)}")
            lines.append(f"- Скорректировано: {feedback.get('corrections', 0)}")
            lines.append("")

        # Medium confidence — needs confirmation
        if medium:
            lines.append("## Нужно подтверждение")
            lines.append("")
            lines.append("| # | Дата | Описание | Сумма | Предложенная категория | Уверенность | Правило |")
            lines.append("|---|------|----------|-------|------------------------|-------------|---------|")
            for i, s in enumerate(medium, 1):
                cat_name = cat_map.get(s.category_id, f"#{s.category_id}")
                desc = s.txn_description[:50].replace("|", "/")
                lines.append(
                    f"| {i} | {_fmt_date(s.txn_date)} | {desc} | {_fmt_amount(s.txn_value)} "
                    f"| {cat_name} | {_fmt_confidence(s.confidence)} | {s.rule_name} |"
                )
            lines.append("")

        # Unknown — could not classify
        if unknown:
            start_idx = len(medium) + 1
            lines.append("## Не удалось определить")
            lines.append("")
            lines.append("| # | Дата | Описание | Сумма | Контрагент |")
            lines.append("|---|------|----------|-------|------------|")
            for i, t in enumerate(unknown, start_idx):
                desc = (t.get("description") or "")[:50].replace("|", "/")
                d = (t.get("date") or "")[:10]
                val = t.get("value", 0)
                contractor = t.get("contractor_name", "—")
                lines.append(
                    f"| {i} | {_fmt_date(d)} | {desc} | {_fmt_amount(val)} | {contractor} |"
                )
            lines.append("")

        # Auto-categorized (for reference)
        if high:
            lines.append("## Авто-категоризированные (для справки)")
            lines.append("")
            lines.append("| Дата | Описание | Сумма | Категория | Правило |")
            lines.append("|------|----------|-------|-----------|---------|")
            for s in high:
                cat_name = cat_map.get(s.category_id, f"#{s.category_id}")
                desc = s.txn_description[:50].replace("|", "/")
                lines.append(
                    f"| {_fmt_date(s.txn_date)} | {desc} | {_fmt_amount(s.txn_value)} "
                    f"| {cat_name} | {s.rule_name} |"
                )
            lines.append("")

        # Overdue planned
        if overdue:
            lines.append("## Просроченные плановые")
            lines.append("")
            lines.append("| Дата плана | Описание | Сумма | Просрочка |")
            lines.append("|-----------|----------|-------|-----------|")
            for t in overdue:
                d = (t.get("date") or "")[:10]
                desc = (t.get("description") or "")[:50].replace("|", "/")
                val = t.get("value", 0)
                try:
                    plan_date = __import__("datetime").date.fromisoformat(d)
                    days_overdue = (scan_date - plan_date).days
                    overdue_str = f"{days_overdue} дней"
                except (ValueError, TypeError):
                    overdue_str = "—"
                lines.append(f"| {_fmt_date(d)} | {desc} | {_fmt_amount(val)} | {overdue_str} |")
            lines.append("")

        # Feedback instructions
        lines.append("---")
        lines.append("**Обратная связь:** оставьте комментарий к этой странице.")
        lines.append("Формат: ✅ (всё ок) | ✅ 1 (подтвердить #1) | ❌ 2 → Закупка товара (исправить #2)")

        return "\n".join(lines)

    def _extract_page_id(self, page_url: str) -> str | None:
        """Extract page ID from Notion URL."""
        import re
        m = re.search(r"([a-f0-9]{32})", page_url.replace("-", ""))
        return m.group(1) if m else None

    def _save_page_mappings(
        self,
        page_id: str,
        medium: list[Suggestion],
        unknown: list[dict],
    ):
        """Save page index → suggestion ID mappings for feedback processing."""
        # Medium confidence items get indices 1..len(medium)
        for i, s in enumerate(medium, 1):
            # Find suggestion by txn_id in store
            # We already saved them during scanner.run(), find by txn_id
            conn = self.store._get_conn()
            row = conn.execute(
                "SELECT id FROM finolog_suggestions WHERE txn_id = ? ORDER BY created_at DESC LIMIT 1",
                (s.txn_id,),
            ).fetchone()
            conn.close()
            if row:
                self.store.update_page_mapping(row["id"], page_id, i)

        # Unknown items continue numbering
        # (no suggestions for unknown — they have no category prediction)
