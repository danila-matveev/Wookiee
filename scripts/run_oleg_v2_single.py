"""Run a single Oleg v2 chain → Notion.

Usage:
    python scripts/run_oleg_v2_single.py weekly
    python scripts/run_oleg_v2_single.py marketing_weekly
"""
from __future__ import annotations

import asyncio
import logging
import sys
from datetime import date, timedelta
from pathlib import Path

_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)


def _last_week_bounds() -> tuple[date, date]:
    today = date.today()
    last_monday = today - timedelta(days=today.weekday() + 7)
    last_sunday = last_monday + timedelta(days=6)
    return last_monday, last_sunday


CHAIN_TEMPLATES = {
    "weekly": ("weekly", "Еженедельный финансовый отчёт", "weekly"),
    "marketing_weekly": ("marketing_weekly", "Еженедельный маркетинговый отчёт", "marketing_weekly"),
    "funnel_weekly": ("funnel_weekly", "Еженедельная воронка WB", "funnel_weekly"),
    "price_weekly": ("price_weekly", "Еженедельный ценовой анализ", "price_weekly"),
}


async def main():
    if len(sys.argv) < 2 or sys.argv[1] not in CHAIN_TEMPLATES:
        print(f"Usage: python scripts/run_oleg_v2_single.py <{'|'.join(CHAIN_TEMPLATES)}>")
        sys.exit(1)

    chain_key = sys.argv[1]
    task_type, task_label, notion_type = CHAIN_TEMPLATES[chain_key]

    from shared.config import (
        OPENROUTER_API_KEY, MODEL_MAIN, PRICING,
        NOTION_TOKEN, NOTION_DATABASE_ID,
    )
    from shared.clients.openrouter_client import OpenRouterClient
    from shared.notion_client import NotionClient
    from agents.oleg.orchestrator.orchestrator import OlegOrchestrator
    from agents.oleg.agents.reporter.agent import ReporterAgent
    from agents.oleg.agents.marketer.agent import MarketerAgent
    from agents.oleg.agents.funnel.agent import FunnelAgent
    from agents.oleg.agents.advisor.agent import AdvisorAgent
    from agents.oleg.agents.validator.agent import ValidatorAgent

    if not OPENROUTER_API_KEY:
        print("ERROR: OPENROUTER_API_KEY not set"); sys.exit(1)

    llm = OpenRouterClient(api_key=OPENROUTER_API_KEY, model=MODEL_MAIN)
    model = MODEL_MAIN

    reporter = ReporterAgent(llm, model, pricing=PRICING, task_type=task_type)
    marketer = MarketerAgent(llm, model, pricing=PRICING, task_type=task_type)
    funnel = FunnelAgent(llm, model, pricing=PRICING)
    advisor = AdvisorAgent(llm, model, pricing=PRICING)
    validator = ValidatorAgent(llm, model, pricing=PRICING)

    agents = {
        "reporter": reporter, "marketer": marketer,
        "funnel": funnel, "advisor": advisor, "validator": validator,
    }

    orchestrator = OlegOrchestrator(llm_client=llm, model=model, agents=agents, pricing=PRICING)

    if not NOTION_TOKEN or not NOTION_DATABASE_ID:
        print("ERROR: NOTION_TOKEN / NOTION_DATABASE_ID not set"); sys.exit(1)

    notion = NotionClient(token=NOTION_TOKEN, database_id=NOTION_DATABASE_ID)

    monday, sunday = _last_week_bounds()
    start_str, end_str = str(monday), str(sunday)
    task = f"{task_label} за {start_str} — {end_str}"

    logger.info("Running chain: %s | %s", task_type, task)

    context = {"date_from": start_str, "date_to": end_str}
    result = await orchestrator.run_chain(task=task, task_type=task_type, context=context)

    report_md = result.detailed or result.summary
    logger.info("Chain done: %d steps, $%.4f, %dms", result.total_steps, result.total_cost, result.total_duration_ms)

    # Guard: don't publish empty/timeout reports to Notion
    _BAD_MARKERS = ["прерван по таймауту", "timeout", "данные могут быть неполными"]
    if not report_md or len(report_md) < 200 or any(m in report_md.lower() for m in _BAD_MARKERS):
        print(f"\nERROR: Report too short or contains timeout marker ({len(report_md or '')} chars). NOT publishing to Notion.")
        print("--- REPORT PREVIEW ---")
        print((report_md or "")[:500])
        sys.exit(1)

    url = await notion.sync_report(
        start_date=start_str, end_date=end_str, report_md=report_md,
        report_type=notion_type, source="Oleg v2 (manual)", chain_steps=result.total_steps,
    )

    if url:
        print(f"\nNotion: {url}")
    else:
        print("\nNotion publish failed")


if __name__ == "__main__":
    asyncio.run(main())
