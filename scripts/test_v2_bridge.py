"""Test V2 bridge — generate reports through the new unified system.

Usage:
    python -m scripts.test_v2_bridge daily 2026-03-23
    python -m scripts.test_v2_bridge daily 2026-03-24
    python -m scripts.test_v2_bridge weekly 2026-03-17 2026-03-23
    python -m scripts.test_v2_bridge marketing_weekly 2026-03-17 2026-03-23
    python -m scripts.test_v2_bridge --deliver daily 2026-03-23   # also deliver to Notion+TG
"""
import argparse
import asyncio
import json
import logging
import sys
import time
from datetime import datetime, timedelta

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger("test_v2_bridge")


async def run(args):
    from agents.v3 import orchestrator, config

    report_type = args.type
    date_from = args.date_from
    date_to = args.date_to or date_from

    # Compute comparison period
    d_from = datetime.strptime(date_from, "%Y-%m-%d")
    d_to = datetime.strptime(date_to, "%Y-%m-%d")
    span = (d_to - d_from).days + 1
    comp_to = (d_from - timedelta(days=1)).strftime("%Y-%m-%d")
    comp_from = (d_from - timedelta(days=span)).strftime("%Y-%m-%d")

    logger.info(
        "Generating %s report: %s — %s (comparison: %s — %s)",
        report_type, date_from, date_to, comp_from, comp_to,
    )
    logger.info("Model: %s, light model: %s", config.MODEL_MAIN, config.MODEL_LIGHT)

    start = time.monotonic()

    if report_type == "daily":
        result = await orchestrator.run_daily_report(
            date_from=date_from, date_to=date_to,
            comparison_from=comp_from, comparison_to=comp_to,
            trigger="manual",
        )
    elif report_type == "weekly":
        result = await orchestrator.run_weekly_report(
            date_from=date_from, date_to=date_to,
            comparison_from=comp_from, comparison_to=comp_to,
            trigger="manual",
        )
    elif report_type == "monthly":
        result = await orchestrator.run_monthly_report(
            date_from=date_from, date_to=date_to,
            comparison_from=comp_from, comparison_to=comp_to,
            trigger="manual",
        )
    elif report_type in ("marketing_weekly", "marketing_monthly"):
        period = "weekly" if "weekly" in report_type else "monthly"
        result = await orchestrator.run_marketing_report(
            date_from=date_from, date_to=date_to,
            comparison_from=comp_from, comparison_to=comp_to,
            report_period=period,
            trigger="manual",
        )
    elif report_type == "price_analysis":
        result = await orchestrator.run_price_analysis(
            date_from=date_from, date_to=date_to,
            comparison_from=comp_from, comparison_to=comp_to,
            trigger="manual",
        )
    else:
        logger.error("Unknown report type: %s", report_type)
        sys.exit(1)

    elapsed = time.monotonic() - start

    # Print result summary
    print("\n" + "=" * 60)
    print(f"STATUS: {result['status']}")
    print(f"DURATION: {elapsed:.1f}s ({result['duration_ms']}ms)")
    print(f"AGENTS: {result['agents_called']} called, {result['agents_succeeded']} ok, {result['agents_failed']} failed")
    print(f"CONFIDENCE: {result.get('aggregate_confidence', 'N/A')}")
    print(f"COST: ${result.get('total_cost_usd', 0):.4f}")
    print(f"LIMITATION: {result.get('worst_limitation', 'None')}")
    print("=" * 60)

    report = result.get("report", {})
    detailed = report.get("detailed_report", "")
    tg_summary = report.get("telegram_summary", "")

    print(f"\nDETAILED REPORT LENGTH: {len(detailed)} chars")
    print(f"TELEGRAM SUMMARY LENGTH: {len(tg_summary)} chars")

    # Count sections
    section_count = detailed.count("## ▶")
    print(f"SECTIONS (## ▶): {section_count}")

    print("\n" + "=" * 60)
    print("TELEGRAM SUMMARY:")
    print("=" * 60)
    print(tg_summary[:2000] if tg_summary else "(empty)")

    print("\n" + "=" * 60)
    print("DETAILED REPORT (first 3000 chars):")
    print("=" * 60)
    print(detailed[:3000] if detailed else "(empty)")

    if len(detailed) > 3000:
        print(f"\n... ({len(detailed) - 3000} chars omitted)")

    # Save full report to file
    out_dir = "agents/v3/data/test_reports"
    import os
    os.makedirs(out_dir, exist_ok=True)
    out_file = f"{out_dir}/{report_type}_{date_from}_{date_to}.md"
    with open(out_file, "w") as f:
        f.write(detailed)
    print(f"\nFull report saved: {out_file}")

    # Deliver if requested
    if args.deliver and result["status"] != "failed":
        await _deliver(result, report_type, date_from, date_to)

    return result


async def _deliver(result: dict, report_type: str, date_from: str, date_to: str):
    """Deliver report via V3 delivery router (Notion + Telegram)."""
    from agents.v3 import config
    from agents.v3.delivery.router import deliver

    delivery_result = await deliver(
        report=result,
        report_type=report_type,
        start_date=date_from,
        end_date=date_to,
        config={
            "telegram_bot_token": config.TELEGRAM_BOT_TOKEN,
            "chat_ids": [config.ADMIN_CHAT_ID] if config.ADMIN_CHAT_ID else [],
            "notion_token": config.NOTION_TOKEN,
            "notion_database_id": config.NOTION_DATABASE_ID,
        },
    )
    page_url = delivery_result.get("notion", {}).get("page_url")
    if page_url:
        logger.info("Notion page: %s", page_url)
    tg = delivery_result.get("telegram", {})
    if tg.get("sent"):
        logger.info("Telegram message sent to %d chats", len(tg.get("chat_ids_sent", [])))
    else:
        for err in tg.get("errors", []):
            logger.warning("Telegram: %s", err)


def main():
    parser = argparse.ArgumentParser(description="Test V2 bridge report generation")
    parser.add_argument("type", choices=[
        "daily", "weekly", "monthly",
        "marketing_weekly", "marketing_monthly",
        "price_analysis",
    ])
    parser.add_argument("date_from", help="Start date YYYY-MM-DD")
    parser.add_argument("date_to", nargs="?", help="End date (default = date_from)")
    parser.add_argument("--deliver", action="store_true",
                        help="Deliver to Notion + Telegram")
    args = parser.parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
