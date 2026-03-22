"""
Delivery router for Wookiee v3.

Orchestrates report delivery to multiple destinations (Notion, Telegram).
Failures in one channel do not block the others.
"""
from __future__ import annotations
import logging

from .notion import NotionDelivery
from .telegram import send_report as tg_send_report

logger = logging.getLogger(__name__)

DEFAULT_DESTINATIONS = ["notion", "telegram"]


async def deliver(
    report: dict,
    report_type: str,
    start_date: str,
    end_date: str,
    config: dict,
    destinations: list[str] | None = None,
    caveats: list[str] | None = None,
) -> dict:
    """Deliver an orchestrator report to the requested destinations.

    Parameters
    ----------
    report : dict
        Full orchestrator result (with ``report``, ``agents_called``, etc.).
    report_type : str
        E.g. ``"daily"``, ``"marketing_weekly"``, ``"funnel_weekly"``.
    start_date, end_date : str
        ISO date strings (``"YYYY-MM-DD"``).
    config : dict
        Must contain ``telegram_bot_token``, ``chat_ids``,
        ``notion_token``, ``notion_database_id``.
    destinations : list[str] | None
        Subset of ``["notion", "telegram"]``. Defaults to both.
    caveats : list[str] | None
        Data-quality warnings to include in the Telegram message.

    Returns
    -------
    dict
        ``{"notion": {"page_url": ... | None, "error": ...},
          "telegram": {"sent": bool, "chat_ids_sent": [...], "errors": [...]}}``
    """
    if destinations is None:
        destinations = DEFAULT_DESTINATIONS

    result: dict = {
        "notion": {"page_url": None, "error": None},
        "telegram": {"sent": False, "chat_ids_sent": [], "errors": []},
    }

    # `or {}` вместо default: ключ "report" может быть None (не отсутствовать)
    inner = report.get("report") or {}
    detailed_md = inner.get("detailed_report", "")

    # ------------------------------------------------------------------
    # 1. Notion (first, so we get page_url for Telegram)
    # ------------------------------------------------------------------
    page_url: str | None = None
    if "notion" in destinations:
        try:
            notion = NotionDelivery(
                token=config.get("notion_token", ""),
                database_id=config.get("notion_database_id", ""),
            )
            page_url = await notion.sync_report(
                start_date=start_date,
                end_date=end_date,
                report_md=detailed_md,
                report_type=report_type,
                source=config.get("notion_source", "Oleg v3 (auto)"),
                chain_steps=report.get("agents_called", 1),
            )
            result["notion"]["page_url"] = page_url
        except Exception as exc:
            err = f"Notion delivery failed: {exc}"
            logger.error(err)
            result["notion"]["error"] = err

    # ------------------------------------------------------------------
    # 2. Telegram
    # ------------------------------------------------------------------
    if "telegram" in destinations:
        try:
            bot_token = config.get("telegram_bot_token", "")
            chat_ids = config.get("chat_ids", [])
            if bot_token and chat_ids:
                tg_result = await tg_send_report(
                    bot_token=bot_token,
                    chat_ids=chat_ids,
                    report=report,
                    page_url=page_url,
                    caveats=caveats,
                )
                result["telegram"] = tg_result
            else:
                result["telegram"]["errors"].append("bot_token or chat_ids not configured")
        except Exception as exc:
            err = f"Telegram delivery failed: {exc}"
            logger.error(err)
            result["telegram"]["errors"].append(err)

    return result
