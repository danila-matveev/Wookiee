"""
Oleg Agent Runner — автономный процесс-агент.

Генерирует отчёты по расписанию и складывает в delivery_queue (SQLite).
Не зависит от Telegram. Работает вечно.

Запуск: python -m agents.oleg agent
"""
import asyncio
import logging
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

import psycopg2

from agents.oleg import config
from agents.oleg.services.auth_service import AuthService
from shared.clients.openrouter_client import OpenRouterClient
from agents.oleg.services.oleg_agent import OlegAgent
from agents.oleg.services.report_storage import ReportStorage
from agents.oleg.services.report_formatter import ReportFormatter
from agents.oleg.services.notion_service import NotionService
from agents.oleg.services.scheduler_service import SchedulerService
from agents.oleg.services.data_freshness_service import DataFreshnessService
from agents.oleg.services.time_utils import get_today_msk, get_now_msk
from agents.oleg.services.price_analysis.learning_store import LearningStore
from agents.oleg.services.price_tools import set_learning_store

# ─── Logging ──────────────────────────────────────────────────
Path(config.LOG_FILE).parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(config.LOG_FILE, encoding='utf-8'),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


class OlegAgentRunner:
    """Автономный агент: scheduler + генерация отчётов + delivery queue.

    Не использует Telegram Bot API. Результаты кладёт в SQLite
    delivery_queue, откуда их забирает процесс бота.
    """

    def __init__(self):
        logger.info("Initializing Oleg Agent Runner (no Telegram)...")

        # Services — всё кроме Bot / Dispatcher / middleware / routers
        self.auth_service = AuthService(
            config.HASHED_PASSWORD,
            persistence_path=config.USERS_FILE_PATH,
            auth_enabled=config.AUTH_ENABLED,
        )
        self.llm_client = OpenRouterClient(
            api_key=config.OPENROUTER_API_KEY,
            model=config.ANALYTICS_MODEL,
            fallback_model=config.FALLBACK_MODEL,
        )
        logger.info(
            f"LLM: OpenRouter (main={config.ANALYTICS_MODEL}, "
            f"classify={config.CLASSIFY_MODEL})"
        )

        self.oleg_agent = OlegAgent(
            zai_client=self.llm_client,
            playbook_path=config.PLAYBOOK_PATH,
            model=config.ANALYTICS_MODEL,
        )
        self.report_storage = ReportStorage(config.SQLITE_DB_PATH)
        self.notion_service = NotionService(
            token=config.NOTION_TOKEN,
            database_id=config.NOTION_DATABASE_ID,
        )
        self.scheduler = SchedulerService(config.TIMEZONE)
        self.data_freshness = DataFreshnessService(
            db_host=config.DB_HOST,
            db_port=config.DB_PORT,
            db_user=config.DB_USER,
            db_password=config.DB_PASSWORD,
            db_name_wb=config.DB_NAME_WB,
            db_name_ozon=config.DB_NAME_OZON,
        )

        # Price analysis: learning store
        self.learning_store = LearningStore(config.SQLITE_DB_PATH)
        set_learning_store(self.learning_store)
        logger.info("LearningStore initialized and injected into price_tools")

        # Флаг: дневной отчёт за сегодня уже отправлен?
        self._daily_report_sent_date: Optional[date] = None

        logger.info("Oleg Agent Runner initialized")

    # ── Recipients ────────────────────────────────────────────

    def _get_report_recipients(self) -> set:
        """Return user IDs for scheduled reports, falling back to ADMIN_CHAT_ID."""
        users = self.auth_service.authenticated_users
        if users:
            return users
        if config.ADMIN_CHAT_ID:
            return {config.ADMIN_CHAT_ID}
        logger.warning(
            "No report recipients: authenticated_users empty "
            "and ADMIN_CHAT_ID not set"
        )
        return set()

    # ── Common report generation + enqueue ────────────────────

    async def _generate_and_enqueue(
        self,
        user_query: str,
        params: dict,
        report_type: str,
        title: str,
        report_date: Optional[datetime] = None,
        save_to_reports: bool = True,
        metadata: Optional[dict] = None,
        notion_source: str = "Agent (auto)",
        keyboard_type: Optional[str] = None,
    ) -> bool:
        """
        Общий метод: analyze_deep → Notion → format → enqueue.

        Returns True if report was generated and enqueued successfully.
        """
        try:
            result = await self.oleg_agent.analyze_deep(
                user_query=user_query,
                params=params,
            )

            if not result.get("brief_summary") or not result.get("success", True):
                error_detail = result.get("error", "нет brief_summary")
                logger.error(f"{report_type} report failed: {error_detail}")
                for user_id in self._get_report_recipients():
                    self.report_storage.enqueue_notification(
                        user_id=user_id,
                        text=(
                            f"Отчёт ({report_type}) не сформирован.\n\n"
                            f"Причина: {error_detail}\n\n"
                            f"Попробуйте запросить отчёт вручную через меню."
                        ),
                    )
                return False

            # Validate detailed_report content
            report_md = result.get("detailed_report", "")
            if '"brief_summary"' in report_md or '"detailed_report"' in report_md:
                logger.warning(
                    f"{report_type}: detailed_report contains raw JSON, "
                    "using brief as fallback"
                )
                report_md = result.get("brief_summary", "")

            # Sync to Notion
            s = params.get("start_date", "")
            e = params.get("end_date", "")
            notion_url = await self.notion_service.sync_report(
                start_date=s,
                end_date=e,
                report_md=report_md,
                source=notion_source,
            )

            # Build cost info string
            cost_parts = []
            if result.get("cost_usd"):
                cost_parts.append(f"~${result['cost_usd']:.4f}")
            if result.get("iterations"):
                cost_parts.append(f"{result['iterations']} шагов")
            cost_info = " | ".join(cost_parts) if cost_parts else None

            # Format HTML for Telegram
            html_text = ReportFormatter.format_for_telegram(
                brief_summary=result["brief_summary"],
                notion_url=notion_url,
                cost_info=cost_info,
            )

            # Serialize keyboard to JSON (bot will deserialize)
            keyboard_json = None
            if keyboard_type:
                keyboard = ReportFormatter.create_report_keyboard(keyboard_type)
                keyboard_json = keyboard.model_dump_json()

            # Enqueue for each recipient
            recipients = self._get_report_recipients()
            for user_id in recipients:
                try:
                    if save_to_reports:
                        self.report_storage.save_report(
                            user_id=user_id,
                            report_type=report_type,
                            title=title,
                            content=result.get("detailed_report", ""),
                            metadata=metadata,
                            start_date=report_date,
                            end_date=report_date,
                        )
                    self.report_storage.enqueue_delivery(
                        report_id=0,
                        user_id=user_id,
                        html_text=html_text,
                        keyboard_json=keyboard_json,
                    )
                    logger.info(f"Enqueued {report_type} for user {user_id}")
                except Exception as ex:
                    logger.error(f"Failed to enqueue {report_type} for {user_id}: {ex}")

            return True

        except Exception as ex:
            logger.error(f"{report_type} report job failed: {ex}", exc_info=True)
            return False

    # ── Scheduler jobs ───────────────────────────────────────

    def _setup_scheduler(self) -> None:
        """Schedule all automatic jobs (no Telegram calls)."""
        from apscheduler.triggers.cron import CronTrigger

        # ─── Daily report ────────────────────────────────────
        async def send_daily_report():
            logger.info("Sending scheduled daily report (Agent)")
            try:
                freshness = self.data_freshness.check_freshness()
                if not self.data_freshness.is_all_ready(freshness):
                    wb_detail = freshness['wb']['details']
                    ozon_detail = freshness['ozon']['details']
                    logger.warning(
                        f"Daily report SKIPPED: data not ready. "
                        f"WB: {wb_detail}, OZON: {ozon_detail}"
                    )
                    for user_id in self._get_report_recipients():
                        self.report_storage.enqueue_notification(
                            user_id=user_id,
                            text=(
                                "⏳ Дневной отчёт отложен — данные ещё не готовы.\n\n"
                                f"WB: {wb_detail}\n"
                                f"OZON: {ozon_detail}\n\n"
                                "Отчёт будет сформирован автоматически, "
                                "как только данные загрузятся."
                            ),
                        )
                    return

                yesterday = get_now_msk() - timedelta(days=1)
                date_str = yesterday.strftime("%Y-%m-%d")

                success = await self._generate_and_enqueue(
                    user_query="Ежедневная аналитическая сводка",
                    params={
                        "start_date": date_str,
                        "end_date": date_str,
                        "channels": ["wb", "ozon"],
                        "report_type": "daily",
                    },
                    report_type="daily_auto",
                    title=f"Ежедневная сводка за {yesterday.strftime('%d.%m.%Y')}",
                    report_date=yesterday,
                    save_to_reports=True,
                    keyboard_type="daily",
                )
                if success:
                    self._daily_report_sent_date = get_today_msk()

            except Exception as e:
                logger.error(f"Daily report job failed: {e}", exc_info=True)

        # ─── Weekly report (Monday) ──────────────────────────
        async def send_weekly_report():
            logger.info("Sending scheduled weekly report (Agent)")
            try:
                end = get_now_msk() - timedelta(days=1)
                start = end - timedelta(days=6)
                s, e = start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")
                s, e, note = self.data_freshness.adjust_dates(s, e)

                params = {
                    "start_date": s,
                    "end_date": e,
                    "channels": ["wb", "ozon"],
                    "report_type": "weekly",
                }
                if note:
                    params["data_availability_note"] = note
                    logger.info(f"Weekly report: dates adjusted — {note}")

                await self._generate_and_enqueue(
                    user_query="Еженедельная аналитическая сводка",
                    params=params,
                    report_type="weekly_auto",
                    title=f"Еженедельная сводка {s} — {e}",
                    save_to_reports=False,
                    keyboard_type="weekly",
                )
            except Exception as e:
                logger.error(f"Weekly report job failed: {e}", exc_info=True)

        # ─── Monthly check (every Monday — first 7 days) ─────
        async def check_and_send_monthly():
            today = get_now_msk()
            if today.day > 7:
                return

            first_of_month = today.replace(day=1)
            last_month_end = first_of_month - timedelta(days=1)
            last_month_start = last_month_end.replace(day=1)
            month_str = last_month_end.strftime("%Y-%m")

            if self.report_storage.has_report_for_period("monthly_auto", month_str):
                logger.info(f"Monthly report for {month_str} already sent, skipping")
                return

            logger.info(f"Sending monthly report for {month_str}")
            try:
                s = last_month_start.strftime("%Y-%m-%d")
                e = last_month_end.strftime("%Y-%m-%d")
                s, e, note = self.data_freshness.adjust_dates(s, e)

                params = {
                    "start_date": s,
                    "end_date": e,
                    "channels": ["wb", "ozon"],
                    "report_type": "monthly",
                }
                if note:
                    params["data_availability_note"] = note
                    logger.info(f"Monthly report: dates adjusted — {note}")

                await self._generate_and_enqueue(
                    user_query=f"Месячный аналитический отчёт за {month_str}",
                    params=params,
                    report_type="monthly_auto",
                    title=f"Месячный отчёт за {month_str}",
                    save_to_reports=True,
                    metadata={"month": month_str},
                    keyboard_type="monthly",
                )
            except Exception as e:
                logger.error(f"Monthly report job failed: {e}", exc_info=True)

        # ─── Data freshness monitor (every 5 min, 06–14 MSK) ─
        async def check_data_freshness():
            if self.data_freshness.already_notified_today():
                # Данные уже объявлены готовыми; проверяем, отправлен ли дневной отчёт
                today_d = get_today_msk()
                if self._daily_report_sent_date != today_d:
                    logger.info(
                        "Data ready, but daily report not yet sent — "
                        "triggering now"
                    )
                    await send_daily_report()
                return
            try:
                status = self.data_freshness.check_freshness()
                if not self.data_freshness.is_all_ready(status):
                    return

                self.data_freshness.mark_notified()
                msg = self.data_freshness.format_notification(status)
                for user_id in self._get_report_recipients():
                    self.report_storage.enqueue_notification(
                        user_id=user_id, text=msg,
                    )

                # Если дневной отчёт ещё не был отправлен — отправить сейчас
                today_d = get_today_msk()
                if self._daily_report_sent_date != today_d:
                    logger.info("Data just became ready — generating daily report")
                    await send_daily_report()
            except Exception as e:
                logger.error(f"Data freshness check failed: {e}")

        # ─── Weekly price review (Monday 11:00 MSK) ──────────
        async def send_weekly_price_review():
            logger.info("Sending scheduled weekly price review (Agent)")
            try:
                end = get_now_msk() - timedelta(days=1)
                start = end - timedelta(days=6)
                s, e = start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")
                s, e, note = self.data_freshness.adjust_dates(s, e)

                params = {
                    "start_date": s,
                    "end_date": e,
                    "channels": ["wb", "ozon"],
                    "report_type": "price_review",
                }
                if note:
                    params["data_availability_note"] = note
                    logger.info(f"Price review: dates adjusted — {note}")

                await self._generate_and_enqueue(
                    user_query=(
                        "Еженедельный ценовой обзор: эластичность, "
                        "рекомендации по ценам, тренды"
                    ),
                    params=params,
                    report_type="price_review_auto",
                    title=f"Ценовой обзор {s} — {e}",
                    save_to_reports=False,
                    notion_source="Price Review (auto)",
                )
            except Exception as e:
                logger.error(f"Weekly price review job failed: {e}", exc_info=True)

        # ─── Outcome checker (Wednesday 09:00 MSK) ───────────
        async def check_recommendation_outcomes():
            logger.info("Checking recommendation outcomes")
            try:
                unchecked = self.learning_store.get_unchecked_recommendations(
                    min_age_days=7,
                )
                if not unchecked:
                    logger.info("No unchecked recommendations older than 7 days")
                    return

                for rec in unchecked:
                    try:
                        model = rec.get('model', '')
                        channel = rec.get('channel', 'wb')
                        rec_date = rec.get('created_at', '')[:10]

                        from shared.data_layer import (
                            get_wb_price_margin_by_model_period,
                            get_ozon_price_margin_by_model_period,
                        )
                        fact_start = rec_date
                        fact_end = (
                            datetime.strptime(rec_date, '%Y-%m-%d')
                            + timedelta(days=7)
                        ).strftime('%Y-%m-%d')

                        if channel == 'wb':
                            facts = get_wb_price_margin_by_model_period(
                                fact_start, fact_end,
                            )
                        else:
                            facts = get_ozon_price_margin_by_model_period(
                                fact_start, fact_end,
                            )

                        model_fact = next(
                            (f for f in facts
                             if f.get('model', '').lower() == model.lower()),
                            None,
                        )
                        if model_fact:
                            self.learning_store.record_outcome(
                                recommendation_id=rec['id'],
                                actual_margin_impact=model_fact.get('margin', 0),
                                actual_volume_impact=model_fact.get('sales_count', 0),
                            )
                            logger.info(
                                f"Recorded outcome for recommendation "
                                f"{rec['id']} ({model})"
                            )
                    except Exception as e:
                        logger.error(
                            f"Failed to check outcome for rec "
                            f"{rec.get('id')}: {e}"
                        )
            except Exception as e:
                logger.error(f"Outcome checker failed: {e}", exc_info=True)

        # ─── Schedule all jobs ───────────────────────────────
        d_hour, d_minute = map(int, config.DAILY_REPORT_TIME.split(":"))
        self.scheduler.add_daily_report(
            callback=send_daily_report, hour=d_hour, minute=d_minute,
        )

        w_hour, w_minute = map(int, config.WEEKLY_REPORT_TIME.split(":"))
        self.scheduler.add_weekly_report(
            callback=send_weekly_report,
            day_of_week=0, hour=w_hour, minute=w_minute,
        )

        m_hour, m_minute = map(int, config.MONTHLY_REPORT_TIME.split(":"))
        self.scheduler.add_weekly_report(
            callback=check_and_send_monthly,
            day_of_week=0, hour=m_hour, minute=m_minute,
            job_id="monthly_check",
        )

        self.scheduler.scheduler.add_job(
            check_data_freshness,
            trigger=CronTrigger(
                minute="*/5", hour="8-14",
                timezone=self.scheduler.timezone,
            ),
            id="data_freshness_check",
            name="Data Freshness Check (every 5 min, 06:00–14:00)",
            replace_existing=True,
        )

        self.scheduler.scheduler.add_job(
            send_weekly_price_review,
            trigger=CronTrigger(
                day_of_week=0, hour=11, minute=0,
                timezone=self.scheduler.timezone,
            ),
            id="weekly_price_review",
            name="Weekly Price Review (Mon 11:00)",
            replace_existing=True,
        )

        self.scheduler.scheduler.add_job(
            check_recommendation_outcomes,
            trigger=CronTrigger(
                day_of_week=2, hour=9, minute=0,
                timezone=self.scheduler.timezone,
            ),
            id="outcome_checker",
            name="Recommendation Outcome Checker (Wed 09:00)",
            replace_existing=True,
        )

        logger.info(
            "Agent scheduler configured: "
            "daily/weekly/monthly/freshness/price_review/outcome_checker"
        )

    # ── Preflight (no Telegram) ──────────────────────────────

    async def _preflight_checks(self) -> bool:
        """Pre-flight проверки: LLM + PostgreSQL. Без Telegram."""
        all_ok = True

        # 1. LLM API (OpenRouter)
        try:
            health = await self.llm_client.health_check()
            if health:
                logger.info("Pre-flight: LLM API — OK")
            else:
                logger.error("Pre-flight: LLM API — FAIL (health=False)")
                all_ok = False
        except Exception as e:
            logger.error(f"Pre-flight: LLM API — FAIL ({e})")
            all_ok = False

        # 2. PostgreSQL WB
        try:
            conn = psycopg2.connect(
                host=config.DB_HOST, port=config.DB_PORT,
                user=config.DB_USER, password=config.DB_PASSWORD,
                database=config.DB_NAME_WB, connect_timeout=10,
            )
            conn.cursor().execute("SELECT 1")
            conn.close()
            logger.info("Pre-flight: PostgreSQL WB — OK")
        except Exception as e:
            logger.error(f"Pre-flight: PostgreSQL WB — FAIL ({e})")
            all_ok = False

        # 3. PostgreSQL OZON
        try:
            conn = psycopg2.connect(
                host=config.DB_HOST, port=config.DB_PORT,
                user=config.DB_USER, password=config.DB_PASSWORD,
                database=config.DB_NAME_OZON, connect_timeout=10,
            )
            conn.cursor().execute("SELECT 1")
            conn.close()
            logger.info("Pre-flight: PostgreSQL OZON — OK")
        except Exception as e:
            logger.error(f"Pre-flight: PostgreSQL OZON — FAIL ({e})")
            all_ok = False

        # 4. Notion (non-critical — warn only)
        if config.NOTION_TOKEN:
            logger.info("Pre-flight: Notion token — present")

        return all_ok

    # ── Recovery (3-day lookback) ─────────────────────────────

    async def _recover_missed_reports(self) -> None:
        """Generate daily reports for the last 3 days if missed."""
        yesterday_str = (get_now_msk() - timedelta(days=1)).strftime("%Y-%m-%d")

        for days_ago in range(3, 0, -1):
            target = get_now_msk() - timedelta(days=days_ago)
            target_str = target.strftime("%Y-%m-%d")

            if self.report_storage.has_report_for_period("daily_auto", target_str):
                logger.info(
                    f"Recovery: daily report for {target_str} already exists, skip"
                )
                continue

            # Check data readiness
            try:
                freshness = self.data_freshness.check_freshness()
                if not self.data_freshness.is_all_ready(freshness):
                    logger.info(
                        f"Recovery: data not ready yet, skip remaining days"
                    )
                    break
            except Exception as e:
                logger.warning(f"Recovery: freshness check failed ({e}), skip")
                break

            recipients = self._get_report_recipients()
            if not recipients:
                logger.warning("Recovery: no recipients, skip")
                break

            logger.info(
                f"Recovery: generating missed daily report for {target_str}"
            )
            success = await self._generate_and_enqueue(
                user_query="Ежедневная аналитическая сводка",
                params={
                    "start_date": target_str,
                    "end_date": target_str,
                    "channels": ["wb", "ozon"],
                    "report_type": "daily",
                },
                report_type="daily_auto",
                title=f"Ежедневная сводка за {target.strftime('%d.%m.%Y')}",
                report_date=target,
                save_to_reports=True,
                notion_source="Agent (recovery)",
                keyboard_type="daily",
            )
            if success:
                logger.info(f"Recovery: daily report for {target_str} done")
            else:
                logger.error(f"Recovery: daily report for {target_str} failed")

        # If yesterday's report exists now, mark today's daily as done
        if self.report_storage.has_report_for_period("daily_auto", yesterday_str):
            self._daily_report_sent_date = get_today_msk()

    # ── Run forever ──────────────────────────────────────────

    async def run(self) -> None:
        """Start agent: preflight → scheduler → recovery → wait forever."""
        preflight_ok = await self._preflight_checks()
        if not preflight_ok:
            logger.critical("Pre-flight checks FAILED — agent cannot start")
            sys.exit(1)

        self.scheduler.start()
        self._setup_scheduler()

        # Recover missed reports
        try:
            await self._recover_missed_reports()
        except Exception as e:
            logger.warning(f"Recovery check failed: {e}")

        logger.info("Oleg Agent Runner started! Waiting for scheduled jobs...")

        # Run forever (no Telegram polling — just scheduler)
        stop_event = asyncio.Event()
        try:
            await stop_event.wait()
        finally:
            self.scheduler.shutdown()
            deleted = self.report_storage.cleanup_old_reports(
                config.REPORT_RETENTION_DAYS,
            )
            logger.info(f"Agent shutdown. Cleaned up {deleted} old reports")


# ── PID lock ──────────────────────────────────────────────────

def _acquire_pid_lock() -> Optional[Path]:
    """Acquire PID lock file for agent process."""
    lock_path = Path(config.LOG_FILE).parent / "oleg_agent.pid"
    if lock_path.exists():
        try:
            old_pid = int(lock_path.read_text().strip())
            os.kill(old_pid, 0)
            return None  # Process is alive — refuse to start
        except (ValueError, ProcessLookupError, PermissionError):
            pass  # Stale PID — safe to overwrite
    lock_path.write_text(str(os.getpid()))
    return lock_path


def _release_pid_lock():
    """Remove agent PID lock file."""
    lock_path = Path(config.LOG_FILE).parent / "oleg_agent.pid"
    try:
        lock_path.unlink(missing_ok=True)
    except Exception:
        pass


def main():
    """Entry point for agent mode."""
    if not config.OPENROUTER_API_KEY:
        print("ERROR: OPENROUTER_API_KEY not set in .env")
        sys.exit(1)

    lock = _acquire_pid_lock()
    if lock is None:
        print(
            "ERROR: Another Oleg Agent instance is already running. Exiting."
        )
        logger.critical(
            "Refused to start: another agent instance is already running "
            "(PID lock)"
        )
        sys.exit(1)

    runner = OlegAgentRunner()

    try:
        asyncio.run(runner.run())
    except KeyboardInterrupt:
        logger.info("Agent stopped by user")
    except Exception as e:
        logger.error(f"Agent crashed: {e}", exc_info=True)
        sys.exit(1)
    finally:
        _release_pid_lock()


if __name__ == "__main__":
    main()
