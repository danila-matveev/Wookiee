"""
OlegApp — unified application: bot + scheduler + watchdog + orchestrator.

Single Docker container, single process.
"""
import asyncio
import logging
import signal
from typing import Optional

from agents.oleg_v2 import config

logger = logging.getLogger(__name__)


class OlegApp:
    """
    Main application class for Oleg v2.

    Brings together:
    - Telegram bot (aiogram Dispatcher)
    - APScheduler (cron jobs for reports)
    - Watchdog (health monitoring)
    - Orchestrator + 3 sub-agents (in memory)
    """

    def __init__(self):
        self.bot = None
        self.scheduler = None
        self.orchestrator = None
        self.pipeline = None
        self.watchdog = None
        self.state_store = None
        self._running = False

    async def setup(self) -> None:
        """Initialize all components."""
        self._setup_logging()
        logger.info("Oleg v2 starting up...")

        # Storage (SQLite for local state, reports, feedback)
        from agents.oleg_v2.storage.state_store import StateStore
        self.state_store = StateStore(config.SQLITE_DB_PATH)
        self.state_store.init_db()

        # LLM client (shared by all agents)
        from shared.clients.openrouter_client import OpenRouterClient
        llm_client = OpenRouterClient(
            api_key=config.OPENROUTER_API_KEY,
            model=config.ANALYTICS_MODEL,
            fallback_model=config.FALLBACK_MODEL,
            site_name="Wookiee Oleg v2",
        )

        # ── Sub-agents ──────────────────────────────────────────────

        from agents.oleg_v2.agents.reporter.agent import ReporterAgent
        reporter = ReporterAgent(
            llm_client=llm_client,
            model=config.ANALYTICS_MODEL,
            pricing=config.PRICING,
            max_iterations=config.MAX_ITERATIONS,
            tool_timeout_sec=config.TOOL_TIMEOUT_SEC,
            total_timeout_sec=config.TOTAL_TIMEOUT_SEC,
        )

        from agents.oleg_v2.agents.researcher.agent import ResearcherAgent
        researcher = ResearcherAgent(
            llm_client=llm_client,
            model=config.ANALYTICS_MODEL,
            pricing=config.PRICING,
            max_iterations=config.MAX_ITERATIONS,
            tool_timeout_sec=config.TOOL_TIMEOUT_SEC,
            total_timeout_sec=config.TOTAL_TIMEOUT_SEC,
        )

        from agents.oleg_v2.agents.quality.agent import QualityAgent
        quality = QualityAgent(
            llm_client=llm_client,
            model=config.ANALYTICS_MODEL,
            pricing=config.PRICING,
            playbook_path=config.PLAYBOOK_PATH,
            state_store=self.state_store,
            max_iterations=config.MAX_ITERATIONS,
            tool_timeout_sec=config.TOOL_TIMEOUT_SEC,
            total_timeout_sec=config.TOTAL_TIMEOUT_SEC,
        )

        # ── Orchestrator ────────────────────────────────────────────

        from agents.oleg_v2.orchestrator.orchestrator import OlegOrchestrator
        self.orchestrator = OlegOrchestrator(
            llm_client=llm_client,
            model=config.ANALYTICS_MODEL,
            agents={
                "reporter": reporter,
                "researcher": researcher,
                "quality": quality,
            },
            pricing=config.PRICING,
        )

        # ── Pipeline ───────────────────────────────────────────────

        from agents.oleg_v2.pipeline.gate_checker import GateChecker
        from agents.oleg_v2.pipeline.report_pipeline import ReportPipeline
        gate_checker = GateChecker()
        self.pipeline = ReportPipeline(
            orchestrator=self.orchestrator,
            gate_checker=gate_checker,
        )

        # ── Watchdog ───────────────────────────────────────────────

        from agents.oleg_v2.watchdog.watchdog import Watchdog
        from agents.oleg_v2.watchdog.alerter import Alerter
        alerter = Alerter(bot=None)  # set bot reference after bot init
        self.watchdog = Watchdog(
            gate_checker=gate_checker,
            state_store=self.state_store,
            llm_client=llm_client,
            alerter=alerter,
            heartbeat_interval_hours=config.WATCHDOG_HEARTBEAT_INTERVAL_HOURS,
        )

        # ── Telegram Bot ───────────────────────────────────────────

        from agents.oleg_v2.bot.telegram_bot import OlegTelegramBot
        self.bot = OlegTelegramBot(
            orchestrator=self.orchestrator,
            pipeline=self.pipeline,
            watchdog=self.watchdog,
            state_store=self.state_store,
        )
        await self.bot.setup()

        # Wire bot reference to alerter for watchdog alerts
        if self.bot.bot:
            alerter.bot = self.bot.bot
            alerter.admin_chat_id = config.ADMIN_CHAT_ID

        # ── Scheduler ──────────────────────────────────────────────

        self._setup_scheduler()

        logger.info("Oleg v2 components initialized")

    def _setup_scheduler(self) -> None:
        """Configure APScheduler for cron-based reports."""
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        from apscheduler.triggers.cron import CronTrigger
        import pytz

        tz = pytz.timezone(config.TIMEZONE)
        self.scheduler = AsyncIOScheduler(timezone=tz)

        # Parse time strings "HH:MM"
        daily_h, daily_m = (int(x) for x in config.DAILY_REPORT_TIME.split(":"))
        weekly_h, weekly_m = (int(x) for x in config.WEEKLY_REPORT_TIME.split(":"))

        # Daily report (Mon-Sat)
        self.scheduler.add_job(
            self._run_daily_report,
            CronTrigger(day_of_week="mon-sat", hour=daily_h, minute=daily_m, timezone=tz),
            id="daily_report",
            name=f"Daily Report ({daily_h:02d}:{daily_m:02d} MSK)",
            replace_existing=True,
        )

        # Weekly report (Monday)
        self.scheduler.add_job(
            self._run_weekly_report,
            CronTrigger(day_of_week="mon", hour=weekly_h, minute=weekly_m, timezone=tz),
            id="weekly_report",
            name=f"Weekly Report (Mon {weekly_h:02d}:{weekly_m:02d} MSK)",
            replace_existing=True,
        )

        # Watchdog heartbeat (every 6 hours)
        self.scheduler.add_job(
            self.watchdog.heartbeat,
            CronTrigger(hour="*/6", minute=0, timezone=tz),
            id="watchdog_heartbeat",
            name="Watchdog Heartbeat",
            replace_existing=True,
        )

        logger.info(
            f"Scheduler configured: daily={daily_h:02d}:{daily_m:02d}, "
            f"weekly=Mon {weekly_h:02d}:{weekly_m:02d}"
        )

    async def _run_daily_report(self) -> None:
        """Scheduled daily report callback."""
        from agents.oleg_v2.pipeline.report_types import ReportType, ReportRequest
        from agents.oleg_v2.services.time_utils import get_yesterday_msk, get_today_msk

        yesterday = get_yesterday_msk()
        today = get_today_msk()

        request = ReportRequest(
            report_type=ReportType.DAILY,
            start_date=str(yesterday),
            end_date=str(yesterday),
        )

        try:
            result = await self.pipeline.generate_report(request)
            if result:
                await self._deliver_report(result)
                await self.watchdog.on_report_success("daily", result.cost_usd)
            else:
                await self.watchdog.on_report_failure("daily", marketplace="wb")
        except Exception as e:
            logger.error(f"Daily report failed: {e}", exc_info=True)
            await self.watchdog.on_report_failure("daily", marketplace="wb")

    async def _run_weekly_report(self) -> None:
        """Scheduled weekly report callback."""
        from agents.oleg_v2.pipeline.report_types import ReportType, ReportRequest
        from agents.oleg_v2.services.time_utils import get_last_week_bounds_msk

        monday, sunday = get_last_week_bounds_msk()

        request = ReportRequest(
            report_type=ReportType.WEEKLY,
            start_date=str(monday),
            end_date=str(sunday),
        )

        try:
            result = await self.pipeline.generate_report(request)
            if result:
                await self._deliver_report(result)
                await self.watchdog.on_report_success("weekly", result.cost_usd)
            else:
                await self.watchdog.on_report_failure("weekly", marketplace="wb")
        except Exception as e:
            logger.error(f"Weekly report failed: {e}", exc_info=True)
            await self.watchdog.on_report_failure("weekly", marketplace="wb")

    async def _deliver_report(self, result) -> None:
        """Deliver a report via Telegram + Notion."""
        from agents.oleg_v2.bot.formatter import (
            add_caveats_header, format_cost_footer,
        )

        text = result.brief_summary
        if result.caveats:
            text = add_caveats_header(text, result.caveats)
        text += format_cost_footer(
            result.cost_usd, result.chain_steps, result.duration_ms,
        )

        # Send to admin chat
        if self.bot and config.ADMIN_CHAT_ID:
            await self.bot.send_message(config.ADMIN_CHAT_ID, text)

        # Save to Notion
        try:
            from agents.oleg_v2.services.notion_service import NotionService
            notion = NotionService()
            await notion.save_report(
                report_text=result.detailed_report or result.brief_summary,
                report_type=result.report_type.value,
                chain_steps=result.chain_steps,
                cost_usd=result.cost_usd,
            )
        except Exception as e:
            logger.warning(f"Notion save failed (non-critical): {e}")

    async def run(self) -> None:
        """Run the application."""
        await self.setup()
        self._running = True

        # Register signal handlers
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, lambda: asyncio.create_task(self.shutdown()))

        # Start scheduler
        if self.scheduler:
            self.scheduler.start()
            logger.info("Scheduler started")

        logger.info("Oleg v2 is running")

        # Start bot polling (blocking)
        if self.bot and self.bot.dp:
            await self.bot.start_polling()
        else:
            # No bot — keep alive for scheduler
            while self._running:
                await asyncio.sleep(1)

    async def shutdown(self) -> None:
        """Graceful shutdown."""
        logger.info("Oleg v2 shutting down...")
        self._running = False

        if self.scheduler:
            self.scheduler.shutdown(wait=False)

        if self.bot:
            await self.bot.stop()

        logger.info("Oleg v2 stopped")

    def _setup_logging(self) -> None:
        """Configure logging."""
        logging.basicConfig(
            level=getattr(logging, config.LOG_LEVEL, logging.INFO),
            format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        # File handler
        try:
            from pathlib import Path
            log_path = Path(config.LOG_FILE)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            fh = logging.FileHandler(str(log_path), encoding="utf-8")
            fh.setFormatter(logging.Formatter(
                "%(asctime)s [%(name)s] %(levelname)s: %(message)s"
            ))
            logging.getLogger().addHandler(fh)
        except Exception as e:
            logger.warning(f"Could not set up file logging: {e}")
