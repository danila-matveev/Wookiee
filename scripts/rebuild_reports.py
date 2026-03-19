"""
Rebuild reports for this week with updated prompts/tools.
Overwrites existing Notion pages, does NOT send Telegram messages.

Usage:
    python -m scripts.rebuild_reports
"""
import asyncio
import logging
import os
import sys

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("rebuild_reports")


async def rebuild():
    from agents.oleg import config
    from agents.oleg.pipeline.report_types import ReportType, ReportRequest
    from agents.oleg.pipeline.report_pipeline import ReportPipeline
    from agents.oleg.pipeline.gate_checker import GateChecker
    from agents.oleg.services.notion_service import NotionService
    from shared.clients.openrouter_client import OpenRouterClient

    # ── LLM client ──────────────────────────────────────────────
    llm_client = OpenRouterClient(
        api_key=config.OPENROUTER_API_KEY,
        model=config.ANALYTICS_MODEL,
        fallback_model=config.FALLBACK_MODEL,
        site_name="Wookiee Oleg v2 (rebuild)",
    )

    # ── Sub-agents ──────────────────────────────────────────────
    from agents.oleg.agents.reporter.agent import ReporterAgent
    reporter = ReporterAgent(
        llm_client=llm_client,
        model=config.ANALYTICS_MODEL,
        pricing=config.PRICING,
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

    # ── Orchestrator ────────────────────────────────────────────
    from agents.oleg.orchestrator.orchestrator import OlegOrchestrator
    orchestrator = OlegOrchestrator(
        llm_client=llm_client,
        model=config.ANALYTICS_MODEL,
        agents={
            "reporter": reporter,
            "researcher": None,
            "quality": None,
            "marketer": marketer,
            "funnel": funnel,
        },
        pricing=config.PRICING,
    )

    # ── Pipeline + Notion ───────────────────────────────────────
    pipeline = ReportPipeline(orchestrator=orchestrator, gate_checker=GateChecker(), skip_gates=True)
    notion = NotionService(
        token=config.NOTION_TOKEN,
        database_id=config.NOTION_DATABASE_ID,
    )

    if not notion.enabled:
        logger.error("Notion not configured (NOTION_TOKEN / NOTION_DATABASE_ID missing)")
        return

    # ── Reports to rebuild ──────────────────────────────────────
    reports = [
        # Daily reports
        ReportRequest(
            report_type=ReportType.DAILY,
            start_date="2026-03-16",
            end_date="2026-03-16",
        ),
        ReportRequest(
            report_type=ReportType.DAILY,
            start_date="2026-03-17",
            end_date="2026-03-17",
        ),
        ReportRequest(
            report_type=ReportType.DAILY,
            start_date="2026-03-18",
            end_date="2026-03-18",
        ),
        # Weekly financial
        ReportRequest(
            report_type=ReportType.WEEKLY,
            start_date="2026-03-10",
            end_date="2026-03-16",
        ),
        # Weekly marketing
        ReportRequest(
            report_type=ReportType.MARKETING_WEEKLY,
            start_date="2026-03-10",
            end_date="2026-03-16",
        ),
    ]

    # ── Funnel WB weekly (requires pre-fetched data) ──────────
    try:
        from agents.oleg.services.funnel_tools import get_all_models_funnel_bundle
        logger.info("Собираю данные для Funnel WB weekly (10-16 марта)...")
        funnel_bundle = await get_all_models_funnel_bundle("2026-03-10", "2026-03-16")
        if funnel_bundle and funnel_bundle.get("models"):
            reports.append(
                ReportRequest(
                    report_type=ReportType.FUNNEL_WEEKLY,
                    start_date="2026-03-10",
                    end_date="2026-03-16",
                    context={"data_bundle": funnel_bundle},
                )
            )
            logger.info(f"Funnel bundle: {len(funnel_bundle['models'])} моделей")
        else:
            logger.warning("Funnel bundle пуст — пропускаю FUNNEL_WEEKLY")
    except Exception as e:
        logger.error(f"Не удалось собрать funnel bundle: {e}", exc_info=True)

    total = len(reports)
    for i, request in enumerate(reports, 1):
        label = f"{request.report_type.value} {request.start_date}—{request.end_date}"
        logger.info(f"[{i}/{total}] Генерирую: {label}")

        try:
            result = await pipeline.generate_report(request)
            if not result:
                logger.warning(f"[{i}/{total}] {label}: gate check failed or no result")
                continue

            logger.info(
                f"[{i}/{total}] {label}: готов "
                f"({result.chain_steps} шагов, ${result.cost_usd:.3f}, {result.duration_ms}ms)"
            )

            # Sync to Notion (upsert — overwrites existing page)
            page_url = await notion.sync_report(
                start_date=request.start_date,
                end_date=request.end_date,
                report_md=result.detailed_report or result.brief_summary,
                report_type=request.report_type.value,
                chain_steps=result.chain_steps,
            )

            if page_url:
                logger.info(f"[{i}/{total}] {label}: Notion обновлён → {page_url}")
            else:
                logger.warning(f"[{i}/{total}] {label}: Notion sync вернул None")

        except Exception as e:
            logger.error(f"[{i}/{total}] {label}: ОШИБКА — {e}", exc_info=True)

    logger.info("Пересборка завершена.")


if __name__ == "__main__":
    asyncio.run(rebuild())
