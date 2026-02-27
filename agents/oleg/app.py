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

        # Data-ready check (hourly 06:00–13:00 MSK, Mon-Sat)
        self.scheduler.add_job(
            self._check_data_ready,
            CronTrigger(day_of_week="mon-sat", hour="6-13", minute=0, timezone=tz),
            id="data_ready_check",
            name="Data Ready Check (hourly 06-13 MSK)",
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
        yesterday = get_yesterday_msk()

        source = "cron" if _retry_attempt == 0 else f"retry_{_retry_attempt}"
        logger.info(f"_run_daily_report triggered: source={source}, date={yesterday}")

        # Clean up stale retry jobs from previous runs (on fresh cron trigger)
        if _retry_attempt == 0 and self.scheduler:
            for i in range(1, MAX_RETRIES + 1):
                job_id = f"daily_report_retry_{i}"
                if self.scheduler.get_job(job_id):
                    self.scheduler.remove_job(job_id)
                    logger.info(f"Cancelled stale retry job: {job_id}")

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
            attempt_info = f"\n\n(попытка {_retry_attempt + 1}/{MAX_RETRIES + 1})"
            status_msg += attempt_info

            if _retry_attempt < MAX_RETRIES:
                status_msg += f"\nПовторная проверка через {RETRY_INTERVAL_MIN} мин."
                await self._send_admin_message(status_msg)

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
                status_msg += "\nВсе попытки исчерпаны. Отчёт не сгенерирован."
                await self._send_admin_message(status_msg)
                await self.watchdog.on_report_failure("daily", marketplace="wb")
                return

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
                    continue

                model_names = list({m.get('model', '') for m in models if m.get('model')})

                for model_name in model_names:
                    try:
                        data = _get_data(channel, start_date, end_date, model_name)
                        if not data or len(data) < 14:
                            continue

                        # Get old cached value
                        old_cached = None
                        if _learning_store:
                            old_cached = _learning_store.get_elasticity_cached(model_name, channel)

                        # Estimate new elasticity
                        result = estimate_price_elasticity(data)
                        if 'error' in result:
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
        """Scan marketplaces for new promotions and analyze them."""
        from agents.oleg import config
        from agents.oleg.services.price_analysis.promotion_analyzer import PromotionAnalyzer
        from agents.oleg.services.price_tools import _learning_store

        for channel in ('wb', 'ozon'):
            try:
                if channel == 'wb':
                    clients = config.get_wb_clients()
                    if not clients:
                        continue
                    analyzer = PromotionAnalyzer(wb_clients=clients)
                else:
                    clients = config.get_ozon_clients()
                    if not clients:
                        continue
                    analyzer = PromotionAnalyzer(ozon_clients=clients)

                promotions = analyzer.scan_promotions(channel)
                if not promotions:
                    logger.info(f"[{channel}] No promotions found")
                    continue

                # Analyze each promotion
                results = []
                participate_count = 0
                skip_count = 0

                for promo in promotions:
                    try:
                        analysis = analyzer.analyze_promotion(
                            promotion=promo,
                            model_metrics={},
                            elasticity=None,
                        )
                        results.append(analysis)
                        rec = analysis.get('recommendation', '')
                        if 'участвовать' in rec.lower() or 'participate' in rec.lower():
                            participate_count += 1
                        else:
                            skip_count += 1
                    except Exception as e:
                        logger.warning(f"[{channel}] Promo analysis failed: {e}")

                # Build report
                report_md = f"# Сканирование акций {channel.upper()}\n\n"
                report_md += f"Обнаружено акций: {len(promotions)}\n\n"
                if results:
                    report_md += "## Результаты анализа\n\n"
                    for r in results:
                        name = r.get('promotion_name', r.get('name', 'Без названия'))
                        rec = r.get('recommendation', 'Не определено')
                        report_md += f"- **{name}**: {rec}\n"

                from datetime import date
                today = str(date.today())

                brief = (
                    f"Обнаружено {len(promotions)} акций на {channel.upper()}. "
                    f"Участвовать: {participate_count}, пропустить: {skip_count}."
                )

                await self._deliver_price_report(
                    report_md=report_md,
                    report_type="Анализ акций",
                    start_date=today,
                    end_date=today,
                    brief_summary=brief,
                )

                # Save recommendations to LearningStore
                if _learning_store and results:
                    for r in results:
                        try:
                            _learning_store.save_recommendation(
                                model=r.get('model', 'all'),
                                channel=channel,
                                recommendation=r,
                            )
                        except Exception:
                            pass

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
            status_parts = [
                wb_result.format_status_message(str(yesterday), marketplace="wb"),
                ozon_result.format_status_message(str(yesterday), marketplace="ozon"),
            ]
            status_msg = "\n\n".join(status_parts)
            await self._send_admin_message(status_msg)

            # Mark as notified
            if self.state_store:
                self.state_store.set_state(state_key, str(yesterday))

            logger.info(f"Data ready notification sent for {yesterday}")

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
