"""
Notion Service — sync reports to Notion database.

Reuses v1 notion_service.py with chain metadata support.
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class NotionService:
    """Sync reports to Notion database with chain metadata."""

    def __init__(self, token: str, database_id: str):
        self.token = token
        self.database_id = database_id
        self._v1_service = None

    def _get_v1_service(self):
        """Lazy-load v1 NotionService for backward compatibility."""
        if self._v1_service is None:
            try:
                from agents.oleg.services.notion_service import NotionService as V1NotionService
                self._v1_service = V1NotionService(
                    token=self.token,
                    database_id=self.database_id,
                )
            except ImportError:
                logger.warning("v1 NotionService not available")
        return self._v1_service

    async def sync_report(
        self,
        start_date: str,
        end_date: str,
        report_md: str,
        source: str = "Reporter (auto)",
        report_type: str = "Ежедневный фин анализ",
        chain_steps: int = 1,
    ) -> Optional[str]:
        """
        Sync a report to Notion (upsert).

        Returns Notion page URL or None on failure.
        """
        v1 = self._get_v1_service()
        if not v1:
            logger.warning("Notion sync skipped: service not available")
            return None

        try:
            result = v1.sync_report(
                start_date=start_date,
                end_date=end_date,
                report_md=report_md,
                source=source,
            )
            logger.info(f"Report synced to Notion: {start_date} — {end_date}")
            return result
        except Exception as e:
            logger.error(f"Notion sync failed: {e}")
            return None
