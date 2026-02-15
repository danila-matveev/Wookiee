"""
Тестовый запуск отчёта через агента Олега (analyze_deep).

Запуск:
    python scripts/test_oleg_report.py --date 2026-02-11

Делает:
1. Вызывает OlegAgent.analyze_deep() с полным протоколом 7 шагов
2. Сохраняет brief_summary и detailed_report в reports/
3. Синхронизирует с Notion
4. Выводит brief_summary в консоль
"""
import asyncio
import argparse
import json
import logging
import sys
import os
from datetime import datetime
from pathlib import Path

# Project root
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from agents.oleg import config
from shared.clients.zai_client import ZAIClient
from agents.oleg.services.oleg_agent import OlegAgent

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


async def run_report(date_str: str):
    """Generate a deep daily report for the given date."""

    print(f"\n{'='*60}")
    print(f"  Oleg Deep Report — {date_str}")
    print(f"{'='*60}\n")

    # Init services
    zai_client = ZAIClient(
        api_key=config.ZAI_API_KEY,
        model=config.ZAI_MODEL,
    )

    oleg = OlegAgent(
        zai_client=zai_client,
        playbook_path=config.PLAYBOOK_PATH,
        model=config.OLEG_MODEL,
    )

    # Health check
    health = await zai_client.health_check()
    if not health:
        print("ERROR: z.ai API is not accessible!")
        return
    print(f"z.ai API: OK (model: {config.OLEG_MODEL})\n")

    # Run deep analysis
    print("Running analyze_deep()...")
    result = await oleg.analyze_deep(
        user_query="Ежедневная аналитическая сводка",
        params={
            "start_date": date_str,
            "end_date": date_str,
            "channels": ["wb", "ozon"],
            "report_type": "daily",
        },
    )

    # Results
    brief = result.get("brief_summary", "")
    detailed = result.get("detailed_report", "")
    steps = result.get("reasoning_steps", [])
    cost = result.get("cost_usd", 0)
    iterations = result.get("iterations", 0)
    duration = result.get("duration_ms", 0)

    print(f"\n{'='*60}")
    print(f"  Results: {iterations} iterations, {len(steps)} tool calls, "
          f"{duration}ms, ~${cost:.4f}")
    print(f"{'='*60}")

    print(f"\nTool calls:")
    for step in steps:
        print(f"  {step}")

    print(f"\n{'='*60}")
    print(f"  BRIEF SUMMARY (BBCode for Telegram)")
    print(f"{'='*60}\n")
    print(brief)

    # Save to files
    reports_dir = PROJECT_ROOT / "reports"
    reports_dir.mkdir(exist_ok=True)

    # Save detailed report
    report_path = reports_dir / f"{date_str}_daily_analytics.md"
    report_path.write_text(detailed, encoding="utf-8")
    print(f"\nDetailed report saved: {report_path}")

    # Save brief summary
    brief_path = reports_dir / f"{date_str}_brief.txt"
    brief_path.write_text(brief, encoding="utf-8")
    print(f"Brief summary saved: {brief_path}")

    # Save full result as JSON
    result_path = reports_dir / f"{date_str}_oleg_result.json"
    json_result = {
        "date": date_str,
        "brief_summary": brief,
        "detailed_report": detailed,
        "reasoning_steps": steps,
        "cost_usd": cost,
        "iterations": iterations,
        "duration_ms": duration,
        "success": result.get("success", False),
    }
    result_path.write_text(
        json.dumps(json_result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Full result saved: {result_path}")

    # Sync to Notion
    if detailed:
        try:
            from scripts.notion_sync import sync_report_to_notion
            print(f"\nSyncing to Notion...")
            notion_url = sync_report_to_notion(
                start_date=date_str,
                end_date=date_str,
                report_md=detailed,
                source="Oleg Agent (test)",
            )
            print(f"Notion URL: {notion_url}")
        except Exception as e:
            print(f"Notion sync failed: {e}")
    else:
        print("\nNo detailed report to sync to Notion.")

    print(f"\n{'='*60}")
    print(f"  Done!")
    print(f"{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(description="Test Oleg agent deep report")
    parser.add_argument("--date", required=True, help="Date YYYY-MM-DD")
    args = parser.parse_args()

    # Validate date
    try:
        datetime.strptime(args.date, "%Y-%m-%d")
    except ValueError:
        print(f"Invalid date format: {args.date}. Expected YYYY-MM-DD")
        sys.exit(1)

    asyncio.run(run_report(args.date))


if __name__ == "__main__":
    main()
