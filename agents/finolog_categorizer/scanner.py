"""
Daily scanner — orchestrates the full categorization pipeline.

Flow:
1. Process feedback from yesterday's Notion page
2. Load rules (description + regex + terminal + contractor + learned)
3. Fetch transactions (recent + uncategorized + overdue planned)
4. Classify each transaction
5. Publish results to Notion
6. Return summary for Telegram notification
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date

from agents.oleg.services.finolog_service import FinologService
from shared.notion_client import NotionClient as NotionService

from .categorizer import Suggestion, classify
from .config import HIGH_CONFIDENCE_THRESHOLD
from .feedback_reader import FeedbackReader, FeedbackResult
from .notion_publisher import NotionPublisher
from .rules.contractor_rules import load_contractor_rules
from .rules.description_rules import CAT_UNCLASSIFIED_IN, CAT_UNCLASSIFIED_OUT
from .store import CategorizerStore

logger = logging.getLogger(__name__)


@dataclass
class ScanSummary:
    scan_date: date = field(default_factory=date.today)
    total_new: int = 0
    auto_categorized: int = 0
    needs_review: int = 0
    unknown: int = 0
    already_categorized: int = 0
    already_suggested: int = 0
    overdue_planned: int = 0
    feedback: FeedbackResult | None = None
    notion_url: str | None = None


class DailyScanner:
    """Orchestrate the daily categorization pipeline."""

    def __init__(
        self,
        finolog: FinologService,
        notion: NotionService,
        store: CategorizerStore,
    ):
        self.finolog = finolog
        self.notion = notion
        self.store = store
        self.publisher = NotionPublisher(notion, store)

    async def run(self, scan_date: date | None = None) -> ScanSummary:
        """Execute the full daily scan pipeline."""
        if scan_date is None:
            scan_date = date.today()

        summary = ScanSummary(scan_date=scan_date)

        # 1. Process feedback from yesterday's page
        cat_map = await self.finolog._get_categories()
        feedback_reader = FeedbackReader(self.notion, self.store, cat_map)
        try:
            feedback = await feedback_reader.process_previous_day()
            summary.feedback = feedback
        except Exception as e:
            logger.error(f"Feedback processing failed: {e}")
            summary.feedback = FeedbackResult()

        # 2. Load rules + contractor names
        learned_rules = self.store.get_learned_rules()
        contractor_rules = load_contractor_rules()
        contractor_names = await self.finolog.get_contractors()

        # 3. Fetch transactions
        recent = await self.finolog.get_recent_transactions(days=2)
        uncategorized = await self.finolog.get_uncategorized()

        # Merge and deduplicate
        seen_ids: set[int] = set()
        to_process: list[dict] = []
        for txn in recent + uncategorized:
            tid = txn.get("id")
            if tid and tid not in seen_ids:
                seen_ids.add(tid)
                to_process.append(txn)

        logger.info(f"Scanner: {len(to_process)} transactions to process")

        # 4. Classify and bucket
        high_bucket: list[Suggestion] = []
        medium_bucket: list[Suggestion] = []
        unknown_bucket: list[dict] = []

        for txn in to_process:
            cat_id = txn.get("category_id")

            # Skip already categorized (not 3/4)
            if cat_id and cat_id not in (CAT_UNCLASSIFIED_IN, CAT_UNCLASSIFIED_OUT):
                summary.already_categorized += 1
                continue

            # Skip if already suggested
            if self.store.already_suggested(txn.get("id", 0)):
                summary.already_suggested += 1
                continue

            suggestion = classify(txn, learned_rules, contractor_rules)

            if suggestion and suggestion.confidence >= HIGH_CONFIDENCE_THRESHOLD:
                high_bucket.append(suggestion)
                # Save to store
                self.store.save_suggestion(
                    txn_id=suggestion.txn_id,
                    txn_date=suggestion.txn_date,
                    txn_description=suggestion.txn_description,
                    txn_value=suggestion.txn_value,
                    txn_contractor_id=suggestion.txn_contractor_id,
                    suggested_category_id=suggestion.category_id,
                    suggested_report_date=suggestion.report_date,
                    confidence=suggestion.confidence,
                    rule_name=suggestion.rule_name,
                )
            elif suggestion:
                medium_bucket.append(suggestion)
                self.store.save_suggestion(
                    txn_id=suggestion.txn_id,
                    txn_date=suggestion.txn_date,
                    txn_description=suggestion.txn_description,
                    txn_value=suggestion.txn_value,
                    txn_contractor_id=suggestion.txn_contractor_id,
                    suggested_category_id=suggestion.category_id,
                    suggested_report_date=suggestion.report_date,
                    confidence=suggestion.confidence,
                    rule_name=suggestion.rule_name,
                )
            else:
                # Enrich with contractor name for display
                ctr_id = txn.get("contractor_id")
                txn["contractor_name"] = contractor_names.get(ctr_id, "—") if ctr_id else "—"
                unknown_bucket.append(txn)

        summary.auto_categorized = len(high_bucket)
        summary.needs_review = len(medium_bucket)
        summary.unknown = len(unknown_bucket)
        summary.total_new = len(high_bucket) + len(medium_bucket) + len(unknown_bucket)

        # Fetch overdue planned — filter to only date <= today
        overdue: list[dict] = []
        try:
            all_planned = await self.finolog.get_overdue_planned()
            today_str = str(scan_date)
            overdue = [
                t for t in all_planned
                if (t.get("date") or "")[:10] <= today_str
            ]
            summary.overdue_planned = len(overdue)
        except Exception as e:
            logger.warning(f"Overdue planned check failed: {e}")

        # 5. Publish to Notion
        try:
            feedback_dict = summary.feedback.to_dict() if summary.feedback else None
            page_url = await self.publisher.publish(
                scan_date=scan_date,
                high_confidence=high_bucket,
                medium_confidence=medium_bucket,
                unknown=unknown_bucket,
                overdue_planned=overdue,
                feedback_summary=feedback_dict,
                cat_map=cat_map,
            )
            summary.notion_url = page_url
        except Exception as e:
            logger.error(f"Notion publish failed: {e}")

        logger.info(
            f"Scan complete: {summary.auto_categorized} auto, "
            f"{summary.needs_review} review, {summary.unknown} unknown"
        )
        return summary
