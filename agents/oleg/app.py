"""
OlegApp — unified application: bot + scheduler + watchdog + orchestrator.

Single Docker container, single process.
"""
import asyncio
import logging
import signal
from typing import Optional

from agents.oleg import config

logger = logging.getLogger(__name__)


class OlegApp:
    """
    Main application class for Oleg v2.

    Brings together:
    - Telegram bot (aiogram Dispatcher)
    - APScheduler (cron jobs for reports)
    - Watchdog (health monitoring)
    - Orchestrator + 4 sub-agents (in memory)
    """

    def __init__(self):
        self.bot = None
        self.scheduler = None
        self.orchestrator = None
        self.pipeline = None
        self.watchdog = None
        self.state_store = None
        self._running = False
        self._sent_msg_hashes: dict = {}  # message dedup: hash -> timestamp
        self._daily_report_lock = asyncio.Lock()

    async def setup(self) -> None:
        """Initialize all components."""
        self._setup_logging()
        logger.info("Oleg v2 starting up...")

        # Storage (SQLite for local state, reports, feedback)
        from agents.oleg.storage.state_store import StateStore
        self.state_store = StateStore(config.SQLITE_DB_PATH)
        self.state_store.init_db()

        # LearningStore (price analysis caching and learning)
        from agents.oleg.services.price_analysis.learning_store import LearningStore
        from agents.oleg.services.price_tools import set_learning_store
        self.learning_store = LearningStore()
        set_learning_store(self.learning_store)
        logger.info("LearningStore initialized at %s", self.learning_store.db_path)

        # LLM client (shared by all agents)
        from shared.clients.openrouter_client import OpenRouterClient
        llm_client = OpenRouterClient(
            api_key=config.OPENROUTER_API_KEY,
            model=config.ANALYTICS_MODEL,
            fallback_model=config.FALLBACK_MODEL,
            site_name="Wookiee Oleg v2",
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

        from agents.oleg.agents.researcher.agent import ResearcherAgent
        researcher = ResearcherAgent(
            llm_client=llm_client,
            model=config.ANALYTICS_MODEL,
            pricing=config.PRICING,
            max_iterations=config.MAX_ITERATIONS,
            tool_timeout_sec=config.TOOL_TIMEOUT_SEC,
            total_timeout_sec=config.TOTAL_TIMEOUT_SEC,
        )

        from agents.oleg.agents.quality.agent import QualityAgent
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

        # ── Orchestrator ────────────────────────────────────────────

        from agents.oleg.orchestrator.orchestrator import OlegOrchestrator
        self.orchestrator = OlegOrchestrator(
            llm_client=llm_client,
            model=config.ANALYTICS_MODEL,
            agents={
                "reporter": reporter,
                "researcher": researcher,
                "quality": quality,
                "marketer": marketer,
            },
            pricing=config.PRICING,
            review_model=config.REVIEW_MODEL if config.REVIEW_ENABLED else None,
            review_task_types=config.REVIEW_TASK_TYPES if config.REVIEW_ENABLED else [],
            review_max_tokens=config.REVIEW_MAX_TOKENS,
            review_mode=config.REVIEW_MODE,
        )

        # ── Pipeline ───────────────────────────────────────────────

        from agents.oleg.pipeline.gate_checker import GateChecker
        from agents.oleg.pipeline.report_pipeline import ReportPipeline
        gate_checker = GateChecker()
        self.pipeline = ReportPipeline(
            orchestrator=self.orchestrator,
            gate_checker=gate_checker,
        )

        # ── Watchdog ───────────────────────────────────────────────

        from agents.oleg.watchdog.watchdog import Watchdog
        from agents.oleg.watchdog.alerter import Alerter
        alerter = Alerter(bot=None)  # set bot reference after bot init
        self.watchdog = Watchdog(
            gate_checker=gate_checker,
            state_store=self.state_store,
            llm_client=llm_client,
            alerter=alerter,
            heartbeat_interval_hours=config.WATCHDOG_HEARTBEAT_INTERVAL_HOURS,
        )

        # ── Anomaly Monitor ────────────────────────────────────────

        self.anomaly_monitor = None
        if config.ANOMALY_MONITOR_ENABLED:
            from agents.oleg.anomaly.anomaly_monitor import AnomalyMonitor
            self.anomaly_monitor = AnomalyMonitor(
                state_store=self.state_store,
                alerter=alerter,
                llm_client=llm_client,
                classify_model=config.CLASSIFY_MODEL,
                thresholds={
                    "revenue": {"threshold": config.ANOMALY_REVENUE_THRESHOLD, "direction": "both"},
                    "margin_pct": {"threshold": config.ANOMALY_MARGIN_PCT_THRESHOLD, "direction": "both"},
                    "drr_pct": {"threshold": config.ANOMALY_DRR_THRESHOLD_MONITOR, "direction": "up"},
                    "orders_count": {"threshold": config.ANOMALY_ORDERS_THRESHOLD, "direction": "down"},
                },
                weekend_multiplier=config.ANOMALY_WEEKEND_MULTIPLIER,
                gate_checker=gate_checker,
            )

        # ── Auth (auto-registers users for notifications) ─────────

        from agents.oleg.bot.handlers.auth import AuthService
        self.auth_service = AuthService()

        # ── Telegram Bot ───────────────────────────────────────────

        from agents.oleg.bot.telegram_bot import OlegTelegramBot
        self.bot = OlegTelegramBot(
            orchestrator=self.orchestrator,
            pipeline=self.pipeline,
            watchdog=self.watchdog,
            state_store=self.state_store,
            auth_service=self.auth_service,
        )
        await self.bot.setup()

        # Wire bot reference and auth_service to alerter for watchdog alerts
        if self.bot.bot:
            alerter.bot = self.bot.bot
            alerter.admin_chat_id = config.ADMIN_CHAT_ID
            alerter.auth_service = self.auth_service

        # ── Scheduler ──────────────────────────────────────────────

        self._setup_scheduler()

        logger.info("Oleg v2 components initialized")

    def _setup_scheduler(self) -> None:
        """Configure APScheduler for cron-based reports."""
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        from apscheduler.triggers.cron import CronTrigger
        import pytz

        tz = pytz.timezone(config.TIMEZONE)
        self.scheduler = AsyncIOScheduler(
            timezone=tz,
            job_defaults={
                "misfire_grace_time": 3600,  # allow up to 1h late execution
                "coalesce": True,            # merge multiple misfired triggers
                "max_instances": 1,
            },
        )

        # Parse time strings "HH:MM"
        daily_h, daily_m = (int(x) for x in config.DAILY_REPORT_TIME.split(":"))
        weekly_h, weekly_m = (int(x) for x in config.WEEKLY_REPORT_TIME.split(":"))

        # Daily report (every day, including weekends)
        self.scheduler.add_job(
            self._run_daily_report,
            CronTrigger(hour=daily_h, minute=daily_m, timezone=tz),
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

        # Monthly report (first Monday of month)
        monthly_h, monthly_m = (int(x) for x in config.MONTHLY_REPORT_TIME.split(":"))
        self.scheduler.add_job(
            self._run_monthly_report,
            CronTrigger(day="1-7", day_of_week="mon", hour=monthly_h, minute=monthly_m, timezone=tz),
            id="monthly_report",
            name=f"Monthly Report (1st Mon {monthly_h:02d}:{monthly_m:02d} MSK)",
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

        # Data-ready check (hourly, every day, window extends past retry period)
        data_check_end_hour = min(daily_h + 3, 23)
        self.scheduler.add_job(
            self._check_data_ready,
            CronTrigger(hour=f"6-{data_check_end_hour}", minute=0, timezone=tz),
            id="data_ready_check",
            name=f"Data Ready Check (hourly 06-{data_check_end_hour} MSK)",
            replace_existing=True,
        )

        # Marketing weekly report (Monday)
        mkt_weekly_h, mkt_weekly_m = (int(x) for x in config.MARKETING_WEEKLY_REPORT_TIME.split(":"))
        self.scheduler.add_job(
            self._run_marketing_weekly_report,
            CronTrigger(day_of_week="mon", hour=mkt_weekly_h, minute=mkt_weekly_m, timezone=tz),
            id="marketing_weekly_report",
            name=f"Marketing Weekly Report (Mon {mkt_weekly_h:02d}:{mkt_weekly_m:02d} MSK)",
            replace_existing=True,
        )

        # Marketing monthly report (first Monday of month)
        mkt_monthly_h, mkt_monthly_m = (int(x) for x in config.MARKETING_MONTHLY_REPORT_TIME.split(":"))
        self.scheduler.add_job(
            self._run_marketing_monthly_report,
            CronTrigger(day="1-7", day_of_week="mon", hour=mkt_monthly_h, minute=mkt_monthly_m, timezone=tz),
            id="marketing_monthly_report",
            name=f"Marketing Monthly Report (1st Mon {mkt_monthly_h:02d}:{mkt_monthly_m:02d} MSK)",
            replace_existing=True,
        )

        # Anomaly monitor (every N hours, offset at :30 to avoid collision)
        if self.anomaly_monitor:
            self.scheduler.add_job(
                self.anomaly_monitor.check_and_alert,
                CronTrigger(
                    hour=f"*/{config.ANOMALY_MONITOR_INTERVAL_HOURS}",
                    minute=30,
                    timezone=tz,
                ),
                id="anomaly_monitor",
                name=f"Anomaly Monitor (every {config.ANOMALY_MONITOR_INTERVAL_HOURS}h)",
                replace_existing=True,
            )

        # Weekly price review (Monday, after weekly report)
        price_h, price_m = (int(x) for x in config.WEEKLY_PRICE_REVIEW_TIME.split(":"))
        self.scheduler.add_job(
            self._run_weekly_price_review,
            CronTrigger(day_of_week="mon", hour=price_h, minute=price_m, timezone=tz),
            id="weekly_price_review",
            name=f"Weekly Price Review (Mon {price_h:02d}:{price_m:02d} MSK)",
            replace_existing=True,
        )

        # Monthly price review (1st Monday of month, after weekly)
        mprice_h, mprice_m = (int(x) for x in config.MONTHLY_PRICE_REVIEW_TIME.split(":"))
        self.scheduler.add_job(
            self._run_monthly_price_review,
            CronTrigger(day="1-7", day_of_week="mon", hour=mprice_h, minute=mprice_m, timezone=tz),
            id="monthly_price_review",
            name=f"Monthly Price Review (1st Mon {mprice_h:02d}:{mprice_m:02d} MSK)",
            replace_existing=True,
        )

        # Monthly regression refresh (1st of month, 03:00 MSK)
        self.scheduler.add_job(
            self._refresh_regression_models,
            CronTrigger(day="1", hour=3, minute=0, timezone=tz),
            id="regression_refresh",
            name="Monthly Regression Refresh (1st, 03:00 MSK)",
            replace_existing=True,
        )

        # Promotion scanning (every 12h, if enabled)
        if config.PROMOTION_SCAN_ENABLED:
            self.scheduler.add_job(
                self._scan_promotions,
                CronTrigger(hour="*/12", minute=15, timezone=tz),
                id="promotion_scan",
                name="Promotion Scan (every 12h)",
                replace_existing=True,
            )

        logger.info(
            f"Scheduler configured: daily={daily_h:02d}:{daily_m:02d}, "
            f"weekly=Mon {weekly_h:02d}:{weekly_m:02d}, "
            f"monthly=1st Mon {monthly_h:02d}:{monthly_m:02d}"
        )

    async def _run_daily_report(self, _retry_attempt: int = 0) -> None:
        """Scheduled daily report callback with gate notification and retry.

        Protected by asyncio.Lock against concurrent execution and
        state_store check against duplicate runs for the same date.
        """
        # Guard: skip if another call is already running
        if self._daily_report_lock.locked():
            logger.warning("_run_daily_report already running, skipping duplicate trigger")
            return

        async with self._daily_report_lock:
            await self._run_daily_report_impl(_retry_attempt)

    async def _run_daily_report_impl(self, _retry_attempt: int = 0) -> None:
        """Inner implementation of daily report (runs under lock)."""
        from agents.oleg.pipeline.report_types import ReportType, ReportRequest
        from agents.oleg.services.time_utils import get_yesterday_msk

        MAX_RETRIES = 3
        RETRY_INTERVAL_MIN = 30
        RETRIES_EXHAUSTED_KEY = "daily_retries_exhausted"
        yesterday = get_yesterday_msk()

        source = "cron" if _retry_attempt == 0 else f"retry_{_retry_attempt}"
        logger.info(f"_run_daily_report triggered: source={source}, date={yesterday}")

        # Clean up stale retry jobs and recovery flag from previous runs
        if _retry_attempt == 0 and self.scheduler:
            for i in range(1, MAX_RETRIES + 1):
                job_id = f"daily_report_retry_{i}"
                if self.scheduler.get_job(job_id):
                    self.scheduler.remove_job(job_id)
                    logger.info(f"Cancelled stale retry job: {job_id}")
            if self.state_store:
                self.state_store.set_state(RETRIES_EXHAUSTED_KEY, "")

        # Step 1: Pre-check gates for both marketplaces
        wb_result = self.pipeline.gate_checker.check_all("wb")
        ozon_result = self.pipeline.gate_checker.check_all("ozon")
        both_ready = wb_result.can_generate and ozon_result.can_generate

        status_parts = [
            wb_result.format_status_message(str(yesterday), marketplace="wb"),
            ozon_result.format_status_message(str(yesterday), marketplace="ozon"),
        ]
        status_msg = "\n\n".join(status_parts)

        if not both_ready:
            if _retry_attempt < MAX_RETRIES:
                if _retry_attempt == 0:
                    # First attempt: full gate status for both marketplaces
                    status_msg += f"\n\n(попытка 1/{MAX_RETRIES + 1})"
                    status_msg += f"\nПовторная проверка через {RETRY_INTERVAL_MIN} мин."
                    await self._send_admin_message(status_msg)
                else:
                    # Subsequent retries: compact one-liner
                    failing = []
                    if not wb_result.can_generate:
                        failing.append("WB")
                    if not ozon_result.can_generate:
                        failing.append("OZON")
                    compact_msg = (
                        f"Попытка {_retry_attempt + 1}/{MAX_RETRIES + 1}: "
                        f"{', '.join(failing)} — данные не готовы. "
                        f"Следующая через {RETRY_INTERVAL_MIN} мин."
                    )
                    await self._send_admin_message(compact_msg)

                # Schedule retry
                from apscheduler.triggers.date import DateTrigger
                from datetime import datetime, timedelta
                import pytz
                tz = pytz.timezone(config.TIMEZONE)
                retry_time = datetime.now(tz) + timedelta(minutes=RETRY_INTERVAL_MIN)
                self.scheduler.add_job(
                    self._run_daily_report,
                    DateTrigger(run_date=retry_time),
                    id=f"daily_report_retry_{_retry_attempt + 1}",
                    kwargs={"_retry_attempt": _retry_attempt + 1},
                    replace_existing=True,
                )
                return
            else:
                # All retries exhausted: full status + recovery flag
                status_msg += f"\n\n(попытка {MAX_RETRIES + 1}/{MAX_RETRIES + 1})"
                status_msg += "\nВсе попытки исчерпаны. Жду появления данных."
                await self._send_admin_message(status_msg)
                # Set recovery flag so _check_data_ready can auto-trigger later
                if self.state_store:
                    self.state_store.set_state(RETRIES_EXHAUSTED_KEY, str(yesterday))
                await self.watchdog.on_report_failure("daily", marketplace="wb")
                return

        # Clear recovery flag — gates passed, no recovery needed
        if self.state_store:
            self.state_store.set_state(RETRIES_EXHAUSTED_KEY, "")

        # Idempotency: don't start report if already started for this date
        state_key = "daily_report_started"
        if self.state_store:
            last_started = self.state_store.get_state(state_key)
            if last_started == str(yesterday):
                logger.warning(f"Daily report already started for {yesterday}, skipping duplicate")
                return

        # Gates passed — mark as started and notify
        if self.state_store:
            self.state_store.set_state(state_key, str(yesterday))

        await self._send_admin_message(f"Запускаю расчёт за {yesterday}...")

        request = ReportRequest(
            report_type=ReportType.DAILY,
            start_date=str(yesterday),
            end_date=str(yesterday),
        )

        try:
            result = await self.pipeline.generate_report(request)
            if result:
                await self._deliver_report(result, request)
                await self.watchdog.on_report_success("daily", result.cost_usd)
            else:
                await self.watchdog.on_report_failure("daily", marketplace="wb")
        except Exception as e:
            logger.error(f"Daily report failed: {e}", exc_info=True)
            await self.watchdog.on_report_failure("daily", marketplace="wb")

    async def _run_weekly_report(self) -> None:
        """Scheduled weekly report callback."""
        from agents.oleg.pipeline.report_types import ReportType, ReportRequest
        from agents.oleg.services.time_utils import get_last_week_bounds_msk

        monday, sunday = get_last_week_bounds_msk()

        request = ReportRequest(
            report_type=ReportType.WEEKLY,
            start_date=str(monday),
            end_date=str(sunday),
        )

        try:
            result = await self.pipeline.generate_report(request)
            if result:
                await self._deliver_report(result, request)
                await self.watchdog.on_report_success("weekly", result.cost_usd)
            else:
                await self.watchdog.on_report_failure("weekly", marketplace="wb")
        except Exception as e:
            logger.error(f"Weekly report failed: {e}", exc_info=True)
            await self.watchdog.on_report_failure("weekly", marketplace="wb")

    async def _run_monthly_report(self) -> None:
        """Scheduled monthly report callback (first Monday of month)."""
        from agents.oleg.pipeline.report_types import ReportType, ReportRequest
        from agents.oleg.services.time_utils import get_last_month_bounds_msk

        first, last = get_last_month_bounds_msk()

        await self._send_admin_message(
            f"Генерирую месячный отчёт за {first} — {last}..."
        )

        request = ReportRequest(
            report_type=ReportType.MONTHLY,
            start_date=str(first),
            end_date=str(last),
        )

        try:
            result = await self.pipeline.generate_report(request)
            if result:
                await self._deliver_report(result, request)
                await self.watchdog.on_report_success("monthly", result.cost_usd)
            else:
                await self.watchdog.on_report_failure("monthly", marketplace="wb")
        except Exception as e:
            logger.error(f"Monthly report failed: {e}", exc_info=True)
            await self.watchdog.on_report_failure("monthly", marketplace="wb")

    async def _run_marketing_weekly_report(self) -> None:
        """Scheduled marketing weekly report callback."""
        from agents.oleg.pipeline.report_types import ReportType, ReportRequest
        from agents.oleg.services.time_utils import get_last_week_bounds_msk

        monday, sunday = get_last_week_bounds_msk()

        await self._send_admin_message(
            f"Генерирую еженедельный маркетинговый отчёт за {monday} — {sunday}..."
        )

        request = ReportRequest(
            report_type=ReportType.MARKETING_WEEKLY,
            start_date=str(monday),
            end_date=str(sunday),
        )

        try:
            result = await self.pipeline.generate_report(request)
            if result:
                await self._deliver_report(result, request)
                await self.watchdog.on_report_success("marketing_weekly", result.cost_usd)
            else:
                await self.watchdog.on_report_failure("marketing_weekly", marketplace="wb")
        except Exception as e:
            logger.error(f"Marketing weekly report failed: {e}", exc_info=True)
            await self.watchdog.on_report_failure("marketing_weekly", marketplace="wb")

    async def _run_marketing_monthly_report(self) -> None:
        """Scheduled marketing monthly report callback (first Monday of month)."""
        from agents.oleg.pipeline.report_types import ReportType, ReportRequest
        from agents.oleg.services.time_utils import get_last_month_bounds_msk

        first, last = get_last_month_bounds_msk()

        await self._send_admin_message(
            f"Генерирую месячный маркетинговый отчёт за {first} — {last}..."
        )

        request = ReportRequest(
            report_type=ReportType.MARKETING_MONTHLY,
            start_date=str(first),
            end_date=str(last),
        )

        try:
            result = await self.pipeline.generate_report(request)
            if result:
                await self._deliver_report(result, request)
                await self.watchdog.on_report_success("marketing_monthly", result.cost_usd)
            else:
                await self.watchdog.on_report_failure("marketing_monthly", marketplace="wb")
        except Exception as e:
            logger.error(f"Marketing monthly report failed: {e}", exc_info=True)
            await self.watchdog.on_report_failure("marketing_monthly", marketplace="wb")

    async def _run_weekly_price_review(self) -> None:
        """Scheduled weekly price review: run full analysis and format readable report."""
        from agents.oleg.services.time_utils import get_last_week_bounds_msk
        from agents.oleg.services.price_tools import _learning_store
        from scripts.run_price_analysis import analyze_channel, format_comprehensive_report

        monday, sunday = get_last_week_bounds_msk()
        start_date = str(monday)
        end_date = str(sunday)

        await self._send_admin_message(
            f"Генерирую еженедельный ценовой обзор за {start_date} — {end_date}..."
        )

        for channel in ('wb', 'ozon'):
            try:
                report = analyze_channel(channel, start_date, end_date, _learning_store)
                report_md = format_comprehensive_report(report)

                total = report.get('models_total', 0)
                with_elast = report.get('models_with_elasticity', 0)
                policies = report.get('policies', {})
                actions = {}
                for p in policies.values():
                    a = p.get('action', 'hold')
                    actions[a] = actions.get(a, 0) + 1

                brief_parts = [f"Ценовой обзор {channel.upper()}: {total} моделей, {with_elast} с эластичностью"]
                if actions.get('increase'):
                    brief_parts.append(f"повысить: {actions['increase']}")
                if actions.get('decrease'):
                    brief_parts.append(f"снизить: {actions['decrease']}")

                await self._deliver_price_report(
                    report_md=report_md,
                    report_type="Ценовой анализ",
                    start_date=start_date,
                    end_date=end_date,
                    brief_summary=", ".join(brief_parts),
                )

                # Save ROI snapshots to learning store
                if _learning_store:
                    for item in report.get('roi_dashboard', []):
                        try:
                            _learning_store.save_roi_snapshot(
                                item.get('model', ''), channel, item,
                            )
                        except Exception:
                            pass

            except Exception as e:
                logger.error(f"Weekly price review for {channel} failed: {e}", exc_info=True)
                await self._send_admin_message(f"Ошибка ценового обзора {channel.upper()}: {e}")

    async def _run_monthly_price_review(self) -> None:
        """Scheduled monthly price review: full analysis for the previous month."""
        from agents.oleg.services.time_utils import get_last_month_bounds_msk
        from agents.oleg.services.price_tools import _learning_store
        from scripts.run_price_analysis import analyze_channel, format_comprehensive_report

        first, last = get_last_month_bounds_msk()
        start_date = str(first)
        end_date = str(last)

        await self._send_admin_message(
            f"Генерирую ежемесячный ценовой обзор за {start_date} — {end_date}..."
        )

        for channel in ('wb', 'ozon'):
            try:
                report = analyze_channel(channel, start_date, end_date, _learning_store)
                report_md = format_comprehensive_report(report)

                total = report.get('models_total', 0)
                with_elast = report.get('models_with_elasticity', 0)
                policies = report.get('policies', {})
                actions = {}
                for p in policies.values():
                    a = p.get('action', 'hold')
                    actions[a] = actions.get(a, 0) + 1

                brief_parts = [
                    f"Месячный ценовой обзор {channel.upper()}: "
                    f"{total} моделей, {with_elast} с эластичностью"
                ]
                if actions.get('increase'):
                    brief_parts.append(f"повысить: {actions['increase']}")
                if actions.get('decrease'):
                    brief_parts.append(f"снизить: {actions['decrease']}")

                await self._deliver_price_report(
                    report_md=report_md,
                    report_type="Ценовой анализ (месяц)",
                    start_date=start_date,
                    end_date=end_date,
                    brief_summary=", ".join(brief_parts),
                )

                if _learning_store:
                    for item in report.get('roi_dashboard', []):
                        try:
                            _learning_store.save_roi_snapshot(
                                item.get('model', ''), channel, item,
                            )
                        except Exception:
                            pass

            except Exception as e:
                logger.error(f"Monthly price review for {channel} failed: {e}", exc_info=True)
                await self._send_admin_message(f"Ошибка месячного ценового обзора {channel.upper()}: {e}")

    async def _refresh_regression_models(self) -> None:
        """Monthly regression refresh: re-estimate all model elasticities."""
        from agents.oleg.services.time_utils import get_last_month_bounds_msk
        from agents.oleg.services.price_analysis.regression_engine import estimate_price_elasticity
        from agents.oleg.services.price_tools import _learning_store, _get_data

        first, last = get_last_month_bounds_msk()
        end_date = str(last)
        # Use 365 days of data for robust estimation
        from datetime import datetime, timedelta
        start_date = (datetime.strptime(end_date, '%Y-%m-%d') - timedelta(days=365)).strftime('%Y-%m-%d')

        await self._send_admin_message("Пересчёт регрессионных моделей...")

        updated = 0
        changed_models = []

        for channel in ('wb', 'ozon'):
            try:
                if channel == 'wb':
                    from shared.data_layer import get_wb_price_margin_by_model_period
                    models = get_wb_price_margin_by_model_period(start_date, end_date)
                else:
                    from shared.data_layer import get_ozon_price_margin_by_model_period
                    models = get_ozon_price_margin_by_model_period(start_date, end_date)

                if not models:
                    logger.info(f"[{channel}] regression: no model data")
                    continue

                model_names = list({m.get('model', '') for m in models if m.get('model')})
                logger.info(f"[{channel}] regression: {len(model_names)} models to process")

                for model_name in model_names:
                    try:
                        data = _get_data(channel, start_date, end_date, model_name)
                        n_data = len(data) if data else 0
                        if n_data < 14:
                            logger.info(f"[{channel}] regression: {model_name} — {n_data} days (skip, <14)")
                            continue

                        # Get old cached value
                        old_cached = None
                        if _learning_store:
                            old_cached = _learning_store.get_elasticity_cached(model_name, channel)

                        # Estimate new elasticity
                        result = estimate_price_elasticity(data)
                        if 'error' in result:
                            logger.info(f"[{channel}] regression: {model_name} — error: {result['error']}")
                            continue

                        # Cache new result
                        if _learning_store:
                            _learning_store.cache_elasticity(
                                model_name, channel, result, start_date, end_date,
                            )

                        updated += 1

                        # Check if model type changed
                        if old_cached and 'error' not in old_cached:
                            old_model = old_cached.get('selected_model', '')
                            new_model = result.get('selected_model', '')
                            if old_model and new_model and old_model != new_model:
                                changed_models.append(
                                    f"{model_name} ({channel}): {old_model} → {new_model}"
                                )

                    except Exception as e:
                        logger.warning(f"Regression refresh for {model_name}/{channel}: {e}")

            except Exception as e:
                logger.error(f"Regression refresh for {channel} failed: {e}", exc_info=True)

        # Check old unchecked recommendations (>7 days)
        unchecked = []
        if _learning_store:
            try:
                unchecked = _learning_store.get_unchecked_recommendations(min_age_days=7)
                logger.info(f"Found {len(unchecked)} unchecked recommendations (>7 days)")
            except Exception as e:
                logger.warning(f"Failed to get unchecked recommendations: {e}")

        # Report — readable Russian text
        report_md = f"# Пересчёт эластичности моделей\n\n"
        report_md += f"**Период данных:** {start_date} — {end_date}\n\n"
        report_md += f"Обновлено **{updated} моделей** на обоих каналах (WB + Ozon).\n\n"

        if changed_models:
            report_md += "## Изменения в моделях\n\n"
            report_md += "Следующие модели изменили тип регрессии (это значит, что характер зависимости цены и объёма изменился):\n\n"
            for cm in changed_models:
                report_md += f"- {cm}\n"
            report_md += "\n"

        if unchecked:
            report_md += f"## Непроверенные рекомендации ({len(unchecked)})\n\n"
            report_md += "Рекомендации, выданные более 7 дней назад, по которым нет данных о фактическом результате:\n\n"
            for rec in unchecked[:20]:
                model = rec.get('model', '?')
                channel_rec = rec.get('channel', '?')
                created = rec.get('created_at', '?')
                report_md += f"- **{model}** ({channel_rec}) — создана {created}\n"

        brief = f"Эластичность пересчитана: {updated} моделей"
        if changed_models:
            brief += f", {len(changed_models)} сменили тип"
        if unchecked:
            brief += f", {len(unchecked)} непроверенных рекомендаций"

        await self._deliver_price_report(
            report_md=report_md,
            report_type="Регрессионный анализ",
            start_date=str(first),
            end_date=end_date,
            brief_summary=brief,
        )

    async def _scan_promotions(self) -> None:
        """Scan marketplaces for promotions and analyze at article level."""
        from datetime import date, timedelta
        from agents.oleg import config
        from agents.oleg.services.price_analysis.promotion_analyzer import (
            PromotionAnalyzer, format_promotion_report,
        )
        from shared.data_layer import (
            get_wb_by_article, get_ozon_by_article,
            get_nm_to_article_mapping, get_artikuly_statuses,
        )

        # Метрики за последние 30 дней для расчёта маржи/продаж
        end = date.today()
        start = end - timedelta(days=30)
        nm_to_article = get_nm_to_article_mapping()
        article_statuses = get_artikuly_statuses()

        for channel in ('wb', 'ozon'):
            try:
                if channel == 'wb':
                    clients = config.get_wb_clients()
                    if not clients:
                        continue
                    analyzer = PromotionAnalyzer(wb_clients=clients)
                    raw_metrics = get_wb_by_article(str(start), str(end))
                else:
                    clients = config.get_ozon_clients()
                    if not clients:
                        continue
                    analyzer = PromotionAnalyzer(ozon_clients=clients)
                    raw_metrics = get_ozon_by_article(str(start), str(end))

                # Конвертировать list → dict {article_lower: metrics}
                article_metrics = {}
                for m in raw_metrics:
                    art = m.get('article', '').lower()
                    if art:
                        article_metrics[art] = m

                logger.info(
                    f"[{channel}] Loaded {len(article_metrics)} articles, "
                    f"{len(nm_to_article)} nm→article mappings"
                )

                promotions = analyzer.scan_promotions(channel)
                if not promotions:
                    logger.info(f"[{channel}] No promotions found")
                    continue

                # Артикульный анализ каждой акции
                analyses = []
                for promo in promotions:
                    try:
                        analysis = analyzer.analyze_promotion_by_article(
                            channel=channel,
                            promotion=promo,
                            article_metrics=article_metrics,
                            nm_to_article=nm_to_article,
                            article_statuses=article_statuses,
                        )
                        analyses.append(analysis)
                    except Exception as e:
                        logger.warning(f"[{channel}] Promo analysis failed: {e}")

                if not analyses:
                    logger.info(f"[{channel}] No promotions analyzed successfully")
                    continue

                report_md = format_promotion_report(analyses, channel)

                total_participate = sum(
                    a.get('summary', {}).get('participate_count', 0) for a in analyses
                )
                total_clearance = sum(
                    a.get('summary', {}).get('clearance_count', 0) for a in analyses
                )
                total_skip = sum(
                    a.get('summary', {}).get('skip_count', 0) for a in analyses
                )
                net_impact = sum(
                    a.get('summary', {}).get('net_impact', 0) for a in analyses
                )

                today = str(date.today())
                brief = (
                    f"{channel.upper()}: {len(promotions)} акций. "
                    f"Участвовать: {total_participate} арт., "
                    f"выводимые: {total_clearance} арт., "
                    f"пропустить: {total_skip} арт. "
                    f"Чистый эффект: {'+' if net_impact > 0 else ''}{net_impact:,.0f}₽"
                )

                await self._deliver_price_report(
                    report_md=report_md,
                    report_type="Анализ акций",
                    start_date=today,
                    end_date=today,
                    brief_summary=brief,
                )

            except Exception as e:
                logger.error(f"[{channel}] Promotion scan failed: {e}", exc_info=True)

    def _get_notification_recipients(self) -> list:
        """Get all chat IDs that should receive notifications.

        Primary: all users who have interacted with the bot (auto-registered).
        Fallback: ADMIN_CHAT_ID from config (for first-run before anyone has chatted).
        """
        recipients = set()
        if self.auth_service:
            recipients.update(self.auth_service._authenticated)
        # Fallback: always include ADMIN_CHAT_ID if set
        if config.ADMIN_CHAT_ID:
            recipients.add(config.ADMIN_CHAT_ID)
        return list(recipients)

    async def _send_admin_message(self, text: str) -> None:
        """Send a plain-text message to all notification recipients."""
        if not self.bot:
            return

        # Dedup: skip if same message sent in last 5 minutes
        import hashlib
        import time
        msg_hash = hashlib.sha256(text.encode()).hexdigest()[:16]
        now = time.time()
        self._sent_msg_hashes = {
            h: ts for h, ts in self._sent_msg_hashes.items()
            if now - ts < 300
        }
        if msg_hash in self._sent_msg_hashes:
            logger.debug(f"Admin message deduplicated (hash={msg_hash})")
            return
        self._sent_msg_hashes[msg_hash] = now

        for chat_id in self._get_notification_recipients():
            try:
                await self.bot.send_message(chat_id, text)
            except Exception as e:
                logger.warning(f"Failed to send message to {chat_id}: {e}")

    async def _check_data_ready(self) -> None:
        """Hourly check: notify admin as soon as yesterday's data is loaded by ETL.

        Checks both WB and Ozon. Sends one notification per date when BOTH are ready,
        tracked via state_store key 'data_ready_notified'.

        If retries were exhausted earlier, auto-triggers daily report generation.
        """
        if not self.pipeline:
            return

        from agents.oleg.services.time_utils import get_yesterday_msk

        yesterday = get_yesterday_msk()
        state_key = "data_ready_notified"

        # Check if we already notified for this date
        if self.state_store:
            last_notified = self.state_store.get_state(state_key)
            if last_notified == str(yesterday):
                return  # Already notified today

        # Run gate checks for both marketplaces
        try:
            wb_result = self.pipeline.gate_checker.check_all("wb")
            ozon_result = self.pipeline.gate_checker.check_all("ozon")
        except Exception as e:
            logger.warning(f"Data ready check failed: {e}")
            return

        both_ready = wb_result.can_generate and ozon_result.can_generate

        if both_ready:
            # Mark as notified BEFORE sending to prevent duplicate messages
            if self.state_store:
                self.state_store.set_state(state_key, str(yesterday))

            status_parts = [
                wb_result.format_status_message(str(yesterday), marketplace="wb"),
                ozon_result.format_status_message(str(yesterday), marketplace="ozon"),
            ]

            # Add report schedule info
            daily_h, daily_m = (int(x) for x in config.DAILY_REPORT_TIME.split(":"))
            status_parts.append(
                f"📊 Ежедневный отчёт запланирован на {daily_h:02d}:{daily_m:02d} МСК"
            )

            status_msg = "\n\n".join(status_parts)
            await self._send_admin_message(status_msg)

            logger.info(f"Data ready notification sent for {yesterday}")

            # Auto-trigger report if retries were exhausted earlier
            retries_exhausted_key = "daily_retries_exhausted"
            if self.state_store:
                exhausted_date = self.state_store.get_state(retries_exhausted_key)
                if exhausted_date == str(yesterday):
                    logger.info(
                        f"Retries were exhausted for {yesterday}, but data is now ready. "
                        f"Auto-triggering daily report."
                    )
                    # Clear flag before triggering to prevent loops
                    self.state_store.set_state(retries_exhausted_key, "")
                    await self._send_admin_message(
                        f"Данные появились после исчерпания попыток. "
                        f"Автоматически запускаю отчёт за {yesterday}..."
                    )
                    await self._run_daily_report()

    async def _deliver_price_report(
        self,
        report_md: str,
        report_type: str,
        start_date: str,
        end_date: str,
        brief_summary: str,
        source: str = "PriceCoordinator (auto)",
    ) -> Optional[str]:
        """Deliver a price analysis report via Notion + Telegram notification."""
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
                report_md=report_md,
                report_type=report_type,
                source=source,
            )
        except Exception as e:
            logger.warning(f"Notion save for price report failed: {e}")

        # Telegram notification
        parts = []
        if page_url:
            parts.append(f'<a href="{page_url}">📊 {report_type} в Notion</a>')
        parts.append(brief_summary)
        await self._send_admin_message("\n\n".join(parts))

        return page_url

    async def _deliver_report(self, result, request=None) -> None:
        """Deliver a report via Notion (first) + Telegram (with Notion link)."""
        from agents.oleg.bot.formatter import (
            add_caveats_header, format_cost_footer,
        )

        # 1. Save to Notion first to get the page URL
        page_url = None
        try:
            from agents.oleg.services.notion_service import NotionService
            notion = NotionService(
                token=config.NOTION_TOKEN,
                database_id=config.NOTION_DATABASE_ID,
            )
            start_date = request.start_date if request else ""
            end_date = request.end_date if request else ""
            page_url = await notion.sync_report(
                start_date=start_date,
                end_date=end_date,
                report_md=result.detailed_report or result.brief_summary,
                report_type=result.report_type.value,
                chain_steps=result.chain_steps,
            )
        except Exception as e:
            logger.warning(f"Notion save failed (non-critical): {e}")

        if page_url:
            logger.info(f"Notion page URL: {page_url}")
        else:
            logger.warning("Notion sync returned no page URL — link will not appear in TG")

        # 2. Build Telegram message: Notion link at top, then summary
        parts = []
        if page_url:
            parts.append(f'<a href="{page_url}">📊 Подробный отчёт в Notion</a>\n')
        if result.caveats:
            parts.append(add_caveats_header("", result.caveats))
        parts.append(result.brief_summary)
        parts.append(format_cost_footer(
            result.cost_usd, result.chain_steps, result.duration_ms,
        ))
        text = "\n".join(parts)

        # 3. Send to all notification recipients
        if self.bot:
            for chat_id in self._get_notification_recipients():
                try:
                    await self.bot.send_message(chat_id, text)
                except Exception as e:
                    logger.error(f"TG delivery to {chat_id} failed: {e}", exc_info=True)
                    # Don't let TG failures propagate — report was generated and saved to Notion

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

        # Start bot polling (check for conflicts first)
        if self.bot and self.bot.dp:
            conflict = await self._check_telegram_conflict()
            if conflict:
                logger.error(
                    "Another bot instance is running with the same token. "
                    "Falling back to scheduler-only mode (no Telegram commands)."
                )
                await self._send_admin_message(
                    "⚠️ Обнаружен конфликт: другой экземпляр бота запущен "
                    "с тем же токеном. Работаю в режиме только планировщика "
                    "(отчёты генерируются, но команды Telegram недоступны)."
                )
                while self._running:
                    await asyncio.sleep(60)
            else:
                await self.bot.start_polling()
        else:
            # No bot — keep alive for scheduler
            while self._running:
                await asyncio.sleep(1)

    async def _check_telegram_conflict(self) -> bool:
        """Test if another bot instance holds the polling session.

        Makes two getUpdates calls with a delay between them.
        The first call always succeeds (it steals the session), so we wait
        a few seconds for the other instance to reclaim it, then check again.
        """
        import httpx

        token = config.TELEGRAM_BOT_TOKEN
        url = f"https://api.telegram.org/bot{token}/getUpdates"
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                # First call — steals the session from any other instance
                await client.post(url, json={"offset": -1, "limit": 1, "timeout": 1})
                # Wait for the other instance to retry and reclaim
                await asyncio.sleep(5)
                # Second call — if another instance reclaimed, we get 409
                resp = await client.post(url, json={"offset": -1, "limit": 1, "timeout": 1})
                data = resp.json()
                if not data.get("ok") and "conflict" in data.get("description", "").lower():
                    return True
        except Exception as e:
            logger.warning(f"Telegram conflict check failed: {e}")
        return False

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
