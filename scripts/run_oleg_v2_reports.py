"""Run all 4 weekly reports via Oleg v2 orchestrator → Notion.

Usage:
    python scripts/run_oleg_v2_reports.py
"""
from __future__ import annotations

import asyncio
import logging
import sys
from datetime import date, timedelta
from pathlib import Path

# Ensure project root is on sys.path
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Date helpers
# ---------------------------------------------------------------------------

def _last_week_bounds() -> tuple[date, date]:
    """Monday–Sunday of the previous week."""
    today = date.today()
    last_monday = today - timedelta(days=today.weekday() + 7)
    last_sunday = last_monday + timedelta(days=6)
    return last_monday, last_sunday


# ---------------------------------------------------------------------------
# Chain definitions
# ---------------------------------------------------------------------------

def _build_chains(start: str, end: str) -> list[dict]:
    """Build chain definitions with explicit date range in task text."""
    return [
        {
            "task_type": "weekly",
            "task": f"Еженедельный финансовый отчёт за {start} — {end}",
            "notion_report_type": "weekly",
        },
        {
            "task_type": "marketing_weekly",
            "task": f"Еженедельный маркетинговый отчёт за {start} — {end}",
            "notion_report_type": "marketing_weekly",
        },
        {
            "task_type": "funnel_weekly",
            "task": f"Еженедельная воронка WB за {start} — {end}",
            "notion_report_type": "funnel_weekly",
        },
        {
            "task_type": "price_weekly",
            "task": f"Еженедельный ценовой анализ за {start} — {end}",
            "notion_report_type": "price_weekly",
        },
    ]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main():
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

    # --- LLM client ---
    if not OPENROUTER_API_KEY:
        print("ERROR: OPENROUTER_API_KEY not set in .env")
        sys.exit(1)

    llm = OpenRouterClient(api_key=OPENROUTER_API_KEY, model=MODEL_MAIN)
    model = MODEL_MAIN

    # --- Shared agents (not task-type-specific) ---
    funnel = FunnelAgent(llm, model, pricing=PRICING)
    advisor = AdvisorAgent(llm, model, pricing=PRICING)
    validator = ValidatorAgent(llm, model, pricing=PRICING)

    # --- Notion ---
    if not NOTION_TOKEN or not NOTION_DATABASE_ID:
        print("ERROR: NOTION_TOKEN / NOTION_DATABASE_ID not set in .env")
        sys.exit(1)

    notion = NotionClient(token=NOTION_TOKEN, database_id=NOTION_DATABASE_ID)

    # --- Dates ---
    monday, sunday = _last_week_bounds()
    start_str = str(monday)
    end_str = str(sunday)
    logger.info("Period: %s — %s", start_str, end_str)

    # --- Run chains ---
    chains = _build_chains(start_str, end_str)
    notion_urls: list[str] = []

    for chain_def in chains:
        task_type = chain_def["task_type"]
        task = chain_def["task"]
        notion_type = chain_def["notion_report_type"]

        logger.info("=" * 60)
        logger.info("Running chain: %s", task_type)

        # Create task-type-specific agents per chain so they load the correct playbook
        reporter = ReporterAgent(llm, model, pricing=PRICING, task_type=task_type)
        marketer = MarketerAgent(llm, model, pricing=PRICING, task_type=task_type)
        agents = {
            "reporter": reporter,
            "marketer": marketer,
            "funnel": funnel,
            "advisor": advisor,
            "validator": validator,
        }
        orchestrator = OlegOrchestrator(
            llm_client=llm,
            model=model,
            agents=agents,
            pricing=PRICING,
        )

        context = {
            "date_from": start_str,
            "date_to": end_str,
        }

        result = await orchestrator.run_chain(
            task=task,
            task_type=task_type,
            context=context,
        )

        report_md = result.detailed or result.summary
        logger.info(
            "Chain %s done: %d steps, $%.4f, %dms",
            task_type, result.total_steps, result.total_cost, result.total_duration_ms,
        )

        # --- Guard: don't publish empty/timeout reports ---
        _BAD_MARKERS = ["прерван по таймауту", "timeout", "данные могут быть неполными"]
        if not report_md or len(report_md) < 200 or any(m in report_md.lower() for m in _BAD_MARKERS):
            notion_urls.append(f"[{task_type}] — SKIPPED (timeout/empty, {len(report_md or '')} chars)")
            logger.warning("Skipping Notion publish for %s — report too short or timeout", task_type)
            continue

        # --- Publish to Notion ---
        url = await notion.sync_report(
            start_date=start_str,
            end_date=end_str,
            report_md=report_md,
            report_type=notion_type,
            source="Oleg v2 (manual)",
            chain_steps=result.total_steps,
        )

        if url:
            notion_urls.append(url)
            logger.info("Notion: %s → %s", task_type, url)
        else:
            notion_urls.append(f"[{task_type}] — Notion publish failed")
            logger.warning("Notion publish failed for %s", task_type)

    # --- Summary ---
    print("\n" + "=" * 60)
    print("All 4 chains complete. Notion pages:")
    for u in notion_urls:
        print(f"  {u}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
