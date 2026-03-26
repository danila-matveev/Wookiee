"""
Read Notion comments from yesterday's categorization page and process feedback.

Feedback format:
- ✅ or ок       → approve all pending
- ✅ N           → approve suggestion #N
- ❌ N → Категория  → reject #N, set correct category
- ❌ N           → reject #N (no correction)
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import date, timedelta

from shared.notion_client import NotionClient as NotionService
from .store import CategorizerStore

logger = logging.getLogger(__name__)


@dataclass
class FeedbackResult:
    page_id: str | None = None
    total_comments: int = 0
    approvals: int = 0
    rejections: int = 0
    corrections: int = 0
    rules_applied: int = 0
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "total_comments": self.total_comments,
            "approvals": self.approvals,
            "rejections": self.rejections,
            "corrections": self.corrections,
            "rules_applied": self.rules_applied,
        }


class FeedbackReader:
    """Read and process Notion comments from previous day's categorization report."""

    def __init__(
        self,
        notion: NotionService,
        store: CategorizerStore,
        cat_map: dict[int, str] | None = None,
    ):
        self.notion = notion
        self.store = store
        # Reverse map: category name → category ID for fuzzy matching
        self._cat_name_to_id: dict[str, int] = {}
        if cat_map:
            for cid, cname in cat_map.items():
                self._cat_name_to_id[cname.lower().strip()] = cid

    async def process_previous_day(self, target_date: date | None = None) -> FeedbackResult:
        """
        Find yesterday's categorization page, read comments, process feedback.

        Returns FeedbackResult with counts.
        """
        result = FeedbackResult()

        if target_date is None:
            target_date = date.today() - timedelta(days=1)

        date_str = target_date.isoformat()

        # Find yesterday's page
        page = await self.notion._find_existing_page(
            date_str, date_str, "Категоризация операций"
        )
        if not page:
            logger.info(f"No categorization page found for {date_str}")
            return result

        page_id = page["id"]
        result.page_id = page_id

        # Read comments
        comments = await self.notion.get_comments(page_id)
        result.total_comments = len(comments)

        if not comments:
            logger.info(f"No comments on page {page_id}")
            return result

        # Process each comment
        for comment in comments:
            text = comment.get("text", "").strip()
            if not text:
                continue

            # Parse each line in the comment
            for line in text.split("\n"):
                line = line.strip()
                if not line:
                    continue
                self._process_line(line, page_id, result)

        logger.info(
            f"Feedback processed: {result.approvals} approved, "
            f"{result.rejections} rejected, {result.corrections} corrected"
        )
        return result

    def _process_line(self, line: str, page_id: str, result: FeedbackResult):
        """Process a single feedback line."""

        # ✅ (approve all) or "ок" / "ok"
        if line in ("✅", "ок", "ok", "ОК", "OK"):
            self._approve_all(page_id, result)
            return

        # ✅ N (approve specific)
        m = re.match(r"✅\s*(\d+)", line)
        if m:
            idx = int(m.group(1))
            self._approve_one(page_id, idx, result)
            return

        # ❌ N → Category (reject with correction)
        m = re.match(r"❌\s*(\d+)\s*(?:→|->|=>)+\s*(.+)", line)
        if m:
            idx = int(m.group(1))
            cat_name = m.group(2).strip()
            self._reject_with_correction(page_id, idx, cat_name, result)
            return

        # ❌ N (reject without correction)
        m = re.match(r"❌\s*(\d+)", line)
        if m:
            idx = int(m.group(1))
            self._reject_one(page_id, idx, result)
            return

        # Unknown format — log as note
        logger.debug(f"Unrecognized feedback line: {line}")

    def _approve_all(self, page_id: str, result: FeedbackResult):
        """Approve all pending suggestions for this page."""
        suggestions = self.store.get_suggestions_for_page(page_id)
        for s in suggestions:
            if s["status"] == "pending":
                self.store.approve(s["id"])
                result.approvals += 1
                result.rules_applied += 1

    def _approve_one(self, page_id: str, index: int, result: FeedbackResult):
        """Approve a specific suggestion by page index."""
        suggestion = self.store.get_by_page_index(page_id, index)
        if not suggestion:
            result.errors.append(f"Suggestion #{index} not found")
            return
        if suggestion["status"] != "pending":
            return
        self.store.approve(suggestion["id"])
        result.approvals += 1
        result.rules_applied += 1

    def _reject_one(self, page_id: str, index: int, result: FeedbackResult):
        """Reject a specific suggestion."""
        suggestion = self.store.get_by_page_index(page_id, index)
        if not suggestion:
            result.errors.append(f"Suggestion #{index} not found")
            return
        self.store.reject(suggestion["id"])
        result.rejections += 1

    def _reject_with_correction(
        self, page_id: str, index: int, cat_name: str, result: FeedbackResult,
    ):
        """Reject a suggestion and record the correct category."""
        suggestion = self.store.get_by_page_index(page_id, index)
        if not suggestion:
            result.errors.append(f"Suggestion #{index} not found")
            return

        # Fuzzy match category name
        cat_id = self._fuzzy_match_category(cat_name)
        if not cat_id:
            result.errors.append(f"Category '{cat_name}' not recognized")
            # Still reject, just without correction
            self.store.reject(suggestion["id"])
            result.rejections += 1
            return

        self.store.reject(suggestion["id"], correct_category_id=cat_id)
        result.rejections += 1
        result.corrections += 1
        result.rules_applied += 1

    def _fuzzy_match_category(self, name: str) -> int | None:
        """Match a category name (case-insensitive, substring)."""
        name_lower = name.lower().strip()

        # Exact match first
        if name_lower in self._cat_name_to_id:
            return self._cat_name_to_id[name_lower]

        # Substring match
        for cat_name, cat_id in self._cat_name_to_id.items():
            if name_lower in cat_name or cat_name in name_lower:
                return cat_id

        return None
