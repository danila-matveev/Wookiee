#!/usr/bin/env python3
"""Reporter V4 Shadow Test — runs pipeline on real data, saves output locally.

Usage:
    python3 scripts/shadow_test_reporter.py                    # financial_daily
    python3 scripts/shadow_test_reporter.py financial_weekly   # specific type
    python3 scripts/shadow_test_reporter.py all                # all 4 types

Skips Telegram delivery. Writes Notion markdown to output/ dir.
Notion upsert is real (shadow DB if configured, or production).
"""
import asyncio
import json
import logging
import sys
import os
from datetime import date, timedelta
from pathlib import Path

# Ensure project root is on path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

from agents.reporter.config import SUPABASE_URL, SUPABASE_SERVICE_KEY
from agents.reporter.types import ReportType, ReportScope, compute_scope
from agents.reporter.collector.financial import FinancialCollector
from agents.reporter.collector.marketing import MarketingCollector
from agents.reporter.collector.funnel import FunnelCollector
from agents.reporter.analyst.analyst import analyze
from agents.reporter.formatter.notion import render_notion
from agents.reporter.formatter.telegram import render_telegram
from agents.reporter.playbook.loader import load_rules_from_state
from agents.reporter.validator import validate
from agents.reporter.state import ReporterState

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("shadow_test")

OUTPUT_DIR = PROJECT_ROOT / "agents" / "reporter" / "output"

_COLLECTORS = {
    "financial": FinancialCollector,
    "marketing": MarketingCollector,
    "funnel": FunnelCollector,
}


def _create_state() -> ReporterState:
    from supabase import create_client
    client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    return ReporterState(client=client)


async def shadow_run(report_type: ReportType, today: date) -> dict:
    """Run one report type through the full pipeline (no Telegram)."""
    logger.info("=" * 60)
    logger.info("SHADOW RUN: %s for %s", report_type.value, today)
    logger.info("=" * 60)

    scope = compute_scope(report_type, today)
    logger.info("Scope: %s → %s (vs %s → %s)",
                scope.period_from, scope.period_to,
                scope.comparison_from, scope.comparison_to)

    state = _create_state()
    result = {"report_type": report_type.value, "scope": scope.to_dict()}

    # 1. Collect
    logger.info("[1/5] Collecting data...")
    collector_cls = _COLLECTORS[report_type.collector_kind]
    collector = collector_cls()
    try:
        data = await collector.collect(scope)
        result["collect"] = "OK"
        logger.info("  Revenue current: %s, previous: %s",
                     data.current.revenue_before_spp,
                     data.previous.revenue_before_spp)
    except Exception as e:
        logger.error("  COLLECT FAILED: %s", e)
        result["collect"] = f"FAIL: {e}"
        return result

    # 2. Load rules
    logger.info("[2/5] Loading playbook rules...")
    rules = load_rules_from_state(state, report_type.value)
    result["rules_count"] = len(rules)
    logger.info("  Loaded %d rules", len(rules))

    # 3. Analyze (LLM call)
    logger.info("[3/5] LLM analysis...")
    try:
        insights, meta = await analyze(data, scope, rules)
        result["analyze"] = "OK"
        result["model"] = meta.get("model")
        result["tokens_in"] = meta.get("input_tokens")
        result["tokens_out"] = meta.get("output_tokens")
        result["confidence"] = insights.overall_confidence
        result["sections_count"] = len(insights.sections)
        result["patterns_discovered"] = len(insights.discovered_patterns)
        logger.info("  Model: %s, Confidence: %.2f, Sections: %d",
                     meta.get("model"), insights.overall_confidence, len(insights.sections))
    except Exception as e:
        logger.error("  ANALYZE FAILED: %s", e)
        result["analyze"] = f"FAIL: {e}"
        return result

    # 4. Format
    logger.info("[4/5] Formatting...")
    notion_md = render_notion(insights, data, scope)
    telegram_html = render_telegram(insights, data, scope, meta=meta)
    result["notion_md_length"] = len(notion_md)
    result["telegram_html_length"] = len(telegram_html)
    logger.info("  Notion MD: %d chars, Telegram HTML: %d chars", len(notion_md), len(telegram_html))

    # 5. Validate
    logger.info("[5/5] Validating...")
    validation = validate(notion_md, insights)
    result["verdict"] = validation.verdict
    result["issues"] = validation.issues
    logger.info("  Verdict: %s, Issues: %s", validation.verdict, validation.issues or "none")

    # Save outputs
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    prefix = f"{today.isoformat()}_{report_type.value}"

    notion_path = OUTPUT_DIR / f"{prefix}_notion.md"
    notion_path.write_text(notion_md, encoding="utf-8")
    logger.info("  Saved: %s", notion_path.relative_to(PROJECT_ROOT))

    tg_path = OUTPUT_DIR / f"{prefix}_telegram.html"
    tg_path.write_text(telegram_html, encoding="utf-8")
    logger.info("  Saved: %s", tg_path.relative_to(PROJECT_ROOT))

    data_path = OUTPUT_DIR / f"{prefix}_data.json"
    data_path.write_text(data.model_dump_json(indent=2), encoding="utf-8")

    # Record run in Supabase state
    try:
        state.create_run(scope)
        state.update_run(
            scope,
            status="shadow_success" if validation.verdict == "PASS" else "shadow_retry",
            confidence=insights.overall_confidence,
            llm_model=meta.get("model"),
            llm_tokens_in=meta.get("input_tokens"),
            llm_tokens_out=meta.get("output_tokens"),
        )
        logger.info("  State recorded in Supabase")
    except Exception as e:
        logger.warning("  State recording failed: %s", e)

    logger.info("RESULT: %s → %s (confidence %.2f)",
                report_type.value, validation.verdict, insights.overall_confidence)
    return result


async def main():
    today = date.today()
    arg = sys.argv[1] if len(sys.argv) > 1 else "financial_daily"

    if arg == "all":
        types = [
            ReportType.FINANCIAL_DAILY,
            ReportType.FINANCIAL_WEEKLY,
            ReportType.MARKETING_WEEKLY,
            ReportType.FUNNEL_WEEKLY,
        ]
    else:
        types = [ReportType(arg)]

    results = []
    for rt in types:
        r = await shadow_run(rt, today)
        results.append(r)
        print()

    # Summary
    print("\n" + "=" * 60)
    print("SHADOW TEST SUMMARY")
    print("=" * 60)
    for r in results:
        status = "✅" if r.get("verdict") == "PASS" else "❌"
        conf = r.get("confidence", 0)
        model = r.get("model", "?")
        print(f"  {status} {r['report_type']:25s} verdict={r.get('verdict', 'N/A'):5s}  "
              f"confidence={conf:.2f}  model={model}")

    # Save summary
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    summary_path = OUTPUT_DIR / f"{today.isoformat()}_summary.json"
    summary_path.write_text(json.dumps(results, indent=2, ensure_ascii=False, default=str))
    print(f"\nDetailed summary: {summary_path.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    asyncio.run(main())
