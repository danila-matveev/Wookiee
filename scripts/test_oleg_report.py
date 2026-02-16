"""
Тестовый запуск отчёта через агента Олега (analyze_deep).

Запуск:
    python scripts/test_oleg_report.py --date 2026-02-11
    python scripts/test_oleg_report.py --date 2026-02-15 --mode price_review --channel wb

Режимы (--mode):
- daily: Ежедневная аналитическая сводка (по умолчанию)
- price_review: Полный ценовой анализ (регрессия, ROI, акции)

Делает:
1. Вызывает OlegAgent.analyze_deep() с полным протоколом
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
from datetime import datetime, timedelta
from pathlib import Path

# Project root
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from agents.oleg import config
from shared.clients.openrouter_client import OpenRouterClient
from agents.oleg.services.oleg_agent import OlegAgent

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def _init_learning_store():
    """Initialize LearningStore and register it with price_tools."""
    try:
        from agents.oleg.services.price_analysis.learning_store import LearningStore
        from agents.oleg.services.price_tools import set_learning_store

        store = LearningStore(config.SQLITE_DB_PATH)
        set_learning_store(store)
        logger.info("LearningStore initialized and registered with price_tools")
        return store
    except Exception as e:
        logger.warning(f"Failed to initialize LearningStore: {e}")
        return None


async def run_report(date_str: str, mode: str = "daily", channel: str = None):
    """Generate a deep report for the given date and mode."""

    mode_titles = {
        "daily": "Daily Report",
        "price_review": "Price Review",
    }
    title = mode_titles.get(mode, mode)

    print(f"\n{'='*60}")
    print(f"  Oleg {title} — {date_str}")
    print(f"{'='*60}\n")

    # Init services (OpenRouter as primary provider)
    llm_client = OpenRouterClient(
        api_key=config.OPENROUTER_API_KEY,
        model=config.ANALYTICS_MODEL,
        fallback_model=config.FALLBACK_MODEL,
    )

    oleg = OlegAgent(
        zai_client=llm_client,
        playbook_path=config.PLAYBOOK_PATH,
        model=config.ANALYTICS_MODEL,
    )

    # Init LearningStore for price tools
    _init_learning_store()

    # Health check
    health = await llm_client.health_check()
    if not health:
        print("ERROR: OpenRouter API is not accessible!")
        return
    print(f"OpenRouter API: OK (model: {config.ANALYTICS_MODEL})\n")

    # Build params based on mode
    if mode == "daily":
        user_query = "Ежедневная аналитическая сводка"
        params = {
            "start_date": date_str,
            "end_date": date_str,
            "channels": ["wb", "ozon"],
            "report_type": "daily",
        }
    elif mode == "price_review":
        # For price_review: use maximum period (180 days back from date)
        end_date = date_str
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        start_date = (dt - timedelta(days=180)).strftime("%Y-%m-%d")

        channels = [channel] if channel else ["wb"]

        user_query = (
            "Выполни полный ценовой анализ: "
            "1) Регрессионный анализ эластичности за максимальный период с проверкой гипотез H1-H7. "
            "2) Рекомендации по управлению ценами на ближайшие 1-2 недели с учётом остатков и ROI. "
            "3) Анализ доступных акций и рекомендации по участию/пропуску для каждой модели."
        )
        params = {
            "start_date": start_date,
            "end_date": end_date,
            "channels": channels,
            "report_type": "price_review",
        }
    else:
        print(f"Unknown mode: {mode}")
        return

    # Run deep analysis
    print(f"Running analyze_deep() [mode={mode}]...")
    result = await oleg.analyze_deep(
        user_query=user_query,
        params=params,
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

    suffix = f"{mode}" if mode != "daily" else "daily_analytics"

    # Save detailed report
    report_path = reports_dir / f"{date_str}_{suffix}.md"
    report_path.write_text(detailed, encoding="utf-8")
    print(f"\nDetailed report saved: {report_path}")

    # Save brief summary
    brief_path = reports_dir / f"{date_str}_{suffix}_brief.txt"
    brief_path.write_text(brief, encoding="utf-8")
    print(f"Brief summary saved: {brief_path}")

    # Save full result as JSON
    result_path = reports_dir / f"{date_str}_{suffix}_result.json"
    json_result = {
        "date": date_str,
        "mode": mode,
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
                start_date=params.get("start_date", date_str),
                end_date=date_str,
                report_md=detailed,
                source=f"Oleg Agent ({mode})",
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
    parser.add_argument(
        "--mode",
        default="daily",
        choices=["daily", "price_review"],
        help="Report mode: daily (default) or price_review",
    )
    parser.add_argument(
        "--channel",
        default=None,
        choices=["wb", "ozon"],
        help="Channel for price_review mode (default: wb)",
    )
    args = parser.parse_args()

    # Validate date
    try:
        datetime.strptime(args.date, "%Y-%m-%d")
    except ValueError:
        print(f"Invalid date format: {args.date}. Expected YYYY-MM-DD")
        sys.exit(1)

    asyncio.run(run_report(args.date, args.mode, args.channel))


if __name__ == "__main__":
    main()
