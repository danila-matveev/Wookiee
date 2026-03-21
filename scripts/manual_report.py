"""Manual report generator — bypass scheduler, generate and deliver report for any date.

Usage:
    python -m scripts.manual_report 2026-03-19
    python -m scripts.manual_report 2026-03-19 --type weekly --start 2026-03-10 --end 2026-03-16
    python -m scripts.manual_report 2026-03-19 --skip-gates
    python -m scripts.manual_report 2026-03-19 --no-deliver  # generate only, don't send to Notion/TG
"""
import argparse
import asyncio
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger("manual_report")


async def run(args):
    from agents.oleg import config
    from agents.oleg.pipeline.report_types import ReportType, ReportRequest
    from agents.oleg.pipeline.gate_checker import GateChecker
    from agents.oleg.pipeline.report_pipeline import ReportPipeline
    from agents.oleg.orchestrator.orchestrator import OlegOrchestrator
    from shared.clients.openrouter_client import OpenRouterClient

    # ── LLM client ──
    llm_client = OpenRouterClient(
        api_key=config.OPENROUTER_API_KEY,
        model=config.ANALYTICS_MODEL,
        fallback_model=config.FALLBACK_MODEL,
        site_name="Wookiee Manual Report",
    )

    # ── Sub-agents ──
    from agents.oleg.agents.reporter.agent import ReporterAgent
    reporter = ReporterAgent(
        llm_client=llm_client,
        model=config.ANALYTICS_MODEL,
        pricing=config.PRICING,
        max_iterations=config.MAX_ITERATIONS,
        tool_timeout_sec=config.TOOL_TIMEOUT_SEC,
        total_timeout_sec=config.TOTAL_TIMEOUT_SEC,
    )

    from agents.oleg.agents.researcher.agent import ResearcherAgent
    researcher = ResearcherAgent(
        llm_client=llm_client,
        model=config.ANALYTICS_MODEL,
        pricing=config.PRICING,
        max_iterations=config.MAX_ITERATIONS,
    )

    from agents.oleg.agents.quality.agent import QualityAgent
    quality = QualityAgent(
        llm_client=llm_client,
        model=config.ANALYTICS_MODEL,
        pricing=config.PRICING,
        playbook_path=config.PLAYBOOK_PATH,
        state_store=None,
        max_iterations=config.MAX_ITERATIONS,
        tool_timeout_sec=config.TOOL_TIMEOUT_SEC,
        total_timeout_sec=config.TOTAL_TIMEOUT_SEC,
    )

    from agents.oleg.agents.marketer.agent import MarketerAgent
    marketer = MarketerAgent(
        llm_client=llm_client,
        model=config.ANALYTICS_MODEL,
        pricing=config.PRICING,
        playbook_path=config.MARKETING_PLAYBOOK_PATH,
        max_iterations=config.MAX_ITERATIONS,
        tool_timeout_sec=config.TOOL_TIMEOUT_SEC,
        total_timeout_sec=config.TOTAL_TIMEOUT_SEC,
    )

    from agents.oleg.agents.seo.agent import FunnelAgent
    funnel = FunnelAgent(
        llm_client=llm_client,
        model=config.ANALYTICS_MODEL,
        pricing=config.PRICING,
        playbook_path=config.FUNNEL_PLAYBOOK_PATH,
        max_iterations=config.MAX_ITERATIONS,
        tool_timeout_sec=config.TOOL_TIMEOUT_SEC,
        total_timeout_sec=config.TOTAL_TIMEOUT_SEC,
    )

    # Christina (optional — may fail if KB not available)
    christina = None
    try:
        from agents.oleg.agents.christina.agent import ChristinaAgent
        christina = ChristinaAgent(
            llm_client=llm_client,
            model=config.ANALYTICS_MODEL,
            pricing=config.PRICING,
            playbook_path=config.CHRISTINA_PLAYBOOK_PATH,
            max_iterations=config.MAX_ITERATIONS,
            tool_timeout_sec=config.TOOL_TIMEOUT_SEC,
            total_timeout_sec=config.TOTAL_TIMEOUT_SEC,
        )
    except Exception as e:
        logger.warning("Christina agent not available: %s", e)

    # ── Orchestrator ──
    agents = {
        "reporter": reporter,
        "researcher": researcher,
        "quality": quality,
        "marketer": marketer,
        "funnel": funnel,
    }
    if christina:
        agents["christina"] = christina

    orchestrator = OlegOrchestrator(
        llm_client=llm_client,
        model=config.ANALYTICS_MODEL,
        agents=agents,
        pricing=config.PRICING,
        review_model=config.REVIEW_MODEL if config.REVIEW_ENABLED else None,
        review_task_types=config.REVIEW_TASK_TYPES if config.REVIEW_ENABLED else [],
        review_max_tokens=config.REVIEW_MAX_TOKENS,
        review_mode=config.REVIEW_MODE,
    )

    # ── Pipeline ──
    gate_checker = GateChecker()
    pipeline = ReportPipeline(
        orchestrator=orchestrator,
        gate_checker=gate_checker,
        skip_gates=args.skip_gates,
    )

    # ── Build request ──
    report_type = ReportType(args.type)
    start_date = args.start or args.date
    end_date = args.end or args.date

    request = ReportRequest(
        report_type=report_type,
        start_date=start_date,
        end_date=end_date,
        context=None,
    )

    logger.info(
        "Generating %s report: %s — %s (skip_gates=%s, deliver=%s)",
        report_type.value, start_date, end_date, args.skip_gates, not args.no_deliver,
    )

    # ── Generate ──
    result = await pipeline.generate_report(request)

    if not result:
        logger.error("Report generation failed (gates did not pass or orchestrator returned None)")
        sys.exit(1)

    logger.info(
        "Report generated: cost=$%.4f, steps=%d, duration=%dms",
        result.cost_usd, result.chain_steps, result.duration_ms,
    )

    # ── Print summary ──
    print("\n" + "=" * 60)
    print("TELEGRAM SUMMARY:")
    print("=" * 60)
    print(result.telegram_summary or result.brief_summary[:1000])
    print("=" * 60)

    if args.no_deliver:
        print("\n--no-deliver: skipping Notion and Telegram delivery.")
        # Still print full report to stdout
        print("\nDETAILED REPORT:")
        print("=" * 60)
        print(result.detailed_report or result.brief_summary)
        return

    # ── Deliver to Notion ──
    page_url = None
    try:
        from agents.oleg.services.notion_service import NotionService
        notion = NotionService(
            token=config.NOTION_TOKEN,
            database_id=config.NOTION_DATABASE_ID,
        )
        page_url = await notion.sync_report(
            start_date=start_date,
            end_date=end_date,
            report_md=result.detailed_report or result.brief_summary,
            report_type=report_type.value,
            chain_steps=result.chain_steps,
        )
        if page_url:
            logger.info("Notion page: %s", page_url)
        else:
            logger.warning("Notion sync returned no page URL")
    except Exception as e:
        logger.warning("Notion delivery failed: %s", e)

    # ── Deliver to Telegram ──
    try:
        from aiogram import Bot
        bot = Bot(token=config.TELEGRAM_BOT_TOKEN)

        from agents.oleg.bot.formatter import add_caveats_header, format_cost_footer
        MAX_TG_SUMMARY = 1500
        tg_body = result.telegram_summary
        if not tg_body or len(tg_body) > MAX_TG_SUMMARY:
            tg_body = result.brief_summary[:500]
        parts = []
        if page_url:
            parts.append(f'<a href="{page_url}">📊 Подробный отчёт в Notion</a>\n')
        parts.append(tg_body)
        parts.append(format_cost_footer(
            result.cost_usd, result.chain_steps, result.duration_ms,
        ))
        text = "\n".join(parts)

        await bot.send_message(config.ADMIN_CHAT_ID, text)
        logger.info("Telegram message sent to admin")
        await bot.session.close()
    except Exception as e:
        logger.warning("Telegram delivery failed: %s", e)

    logger.info("Done.")


def main():
    parser = argparse.ArgumentParser(description="Manual report generator")
    parser.add_argument("date", help="Target date YYYY-MM-DD")
    parser.add_argument("--type", default="daily",
                        choices=["daily", "weekly", "monthly",
                                 "marketing_daily", "marketing_weekly", "marketing_monthly"],
                        help="Report type (default: daily)")
    parser.add_argument("--start", help="Override start date (for weekly/monthly)")
    parser.add_argument("--end", help="Override end date (for weekly/monthly)")
    parser.add_argument("--skip-gates", action="store_true",
                        help="Skip hard gate checks")
    parser.add_argument("--no-deliver", action="store_true",
                        help="Generate only, don't send to Notion/Telegram")
    args = parser.parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
