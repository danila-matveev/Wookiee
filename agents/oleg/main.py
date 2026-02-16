"""
Oleg Bot — ИИ финансовый аналитик Wookiee

Точка входа: python -m agents.oleg
"""
import asyncio
import logging
import os
import sys
import time
from datetime import date, datetime, timedelta
from typing import Optional
from pathlib import Path

import psycopg2

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

from agents.oleg import config
from agents.oleg.services.auth_service import AuthService
from shared.clients.zai_client import ZAIClient
from agents.oleg.services.oleg_agent import OlegAgent
from agents.oleg.services.report_storage import ReportStorage
from agents.oleg.services.report_formatter import ReportFormatter
from agents.oleg.services.feedback_service import FeedbackService
from agents.oleg.services.notion_service import NotionService
from agents.oleg.services.scheduler_service import SchedulerService
from agents.oleg.services.data_freshness_service import DataFreshnessService

from agents.oleg.services.price_analysis.learning_store import LearningStore
from agents.oleg.services.price_tools import set_learning_store

from agents.oleg.handlers import auth, menu, scheduled_reports, custom_queries

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


class OlegBot:
    """Главный класс бота Олега — ИИ финансовый аналитик"""

    def __init__(self):
        logger.info("Initializing Oleg Bot...")

        # Bot & Dispatcher
        self.bot = Bot(
            token=config.TELEGRAM_BOT_TOKEN,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )
        self.dp = Dispatcher(storage=MemoryStorage())

        # Services
        self.auth_service = AuthService(
            config.HASHED_PASSWORD,
            persistence_path=config.USERS_FILE_PATH,
        )
        self.zai_client = ZAIClient(
            api_key=config.ZAI_API_KEY,
            model=config.ZAI_MODEL,
        )
        # For analytics (tool-use): prefer OpenRouter if available, fallback to z.ai
        if config.OPENROUTER_API_KEY:
            self.analytics_client = ZAIClient(
                api_key=config.OPENROUTER_API_KEY,
                model=config.OPENROUTER_MODEL,
                base_url="https://openrouter.ai/api/v1",
            )
            logger.info(f"Analytics client: OpenRouter ({config.OPENROUTER_MODEL})")
        else:
            self.analytics_client = self.zai_client
            logger.info("Analytics client: z.ai (no OpenRouter key)")
        self.oleg_agent = OlegAgent(
            zai_client=self.analytics_client,
            playbook_path=config.PLAYBOOK_PATH,
            model=config.OPENROUTER_MODEL if config.OPENROUTER_API_KEY else config.OLEG_MODEL,
        )
        # LLM-based query understanding (uses cheap glm-4.5-flash)
        from agents.oleg.services.query_understanding import QueryUnderstandingService
        self.query_understanding = QueryUnderstandingService(
            zai_client=self.zai_client,
        )
        self.report_storage = ReportStorage(config.SQLITE_DB_PATH)
        self.feedback_service = FeedbackService(notion_token=config.NOTION_TOKEN)
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

        # Register middleware & routers
        self._setup_middleware()
        self._register_routers()

        logger.info("Oleg Bot initialized")

    def _setup_middleware(self) -> None:
        """DI middleware — инжектирует сервисы в хендлеры"""

        @self.dp.message.middleware()
        async def inject_services(handler, event, data):
            data['auth_service'] = self.auth_service
            data['oleg_agent'] = self.oleg_agent
            data['report_storage'] = self.report_storage
            data['feedback_service'] = self.feedback_service
            data['notion_service'] = self.notion_service
            data['query_understanding'] = self.query_understanding
            return await handler(event, data)

        @self.dp.callback_query.middleware()
        async def inject_services_callback(handler, event, data):
            data['auth_service'] = self.auth_service
            data['oleg_agent'] = self.oleg_agent
            data['report_storage'] = self.report_storage
            data['feedback_service'] = self.feedback_service
            data['notion_service'] = self.notion_service
            data['query_understanding'] = self.query_understanding
            return await handler(event, data)

    def _register_routers(self) -> None:
        """Регистрация роутеров"""
        self.dp.include_router(auth.router)
        self.dp.include_router(menu.router)
        self.dp.include_router(scheduled_reports.router)
        self.dp.include_router(custom_queries.router)

        logger.info("Routers registered")

    def _get_report_recipients(self) -> set:
        """Return user IDs for scheduled reports, falling back to ADMIN_CHAT_ID."""
        users = self.auth_service.authenticated_users
        if users:
            return users
        if config.ADMIN_CHAT_ID:
            return {config.ADMIN_CHAT_ID}
        logger.warning("No report recipients: authenticated_users empty and ADMIN_CHAT_ID not set")
        return set()

    def _setup_scheduler(self) -> None:
        """Schedule automatic reports: daily, weekly, monthly + data freshness"""

        # ─── Daily report (Oleg via tool-use) ────────────────
        async def send_daily_report():
            logger.info("Sending scheduled daily report (Oleg)")
            try:
                # Проверяем готовность данных перед генерацией
                freshness = self.data_freshness.check_freshness()
                if not self.data_freshness.is_all_ready(freshness):
                    wb_detail = freshness['wb']['details']
                    ozon_detail = freshness['ozon']['details']
                    logger.warning(
                        f"Daily report SKIPPED: data not ready. "
                        f"WB: {wb_detail}, OZON: {ozon_detail}"
                    )
                    # Уведомить пользователей что отчёт отложен
                    for user_id in self._get_report_recipients():
                        try:
                            await self.bot.send_message(
                                chat_id=user_id,
                                text=(
                                    "⏳ Дневной отчёт отложен — данные ещё не готовы.\n\n"
                                    f"WB: {wb_detail}\n"
                                    f"OZON: {ozon_detail}\n\n"
                                    "Отчёт будет сформирован автоматически, "
                                    "как только данные загрузятся."
                                ),
                            )
                        except Exception as e:
                            logger.error(f"Failed to notify {user_id} about delay: {e}")
                    return

                yesterday = datetime.now() - timedelta(days=1)
                date_str = yesterday.strftime("%Y-%m-%d")

                result = await self.oleg_agent.analyze_deep(
                    user_query="Ежедневная аналитическая сводка",
                    params={
                        "start_date": date_str,
                        "end_date": date_str,
                        "channels": ["wb", "ozon"],
                        "report_type": "daily",
                    },
                )

                if not result.get("brief_summary") or not result.get("success", True):
                    error_detail = result.get("error", "нет brief_summary")
                    logger.error(f"Daily report failed: {error_detail}")
                    for user_id in self._get_report_recipients():
                        try:
                            await self.bot.send_message(
                                chat_id=user_id,
                                text=(
                                    f"Дневной отчёт не сформирован.\n\n"
                                    f"Причина: {error_detail}\n\n"
                                    f"Попробуйте запросить отчёт вручную через меню."
                                ),
                            )
                        except Exception as e:
                            logger.error(f"Failed to notify {user_id} about report error: {e}")
                    return

                # Sync to Notion (validate content first)
                report_md = result.get("detailed_report", "")
                if '"brief_summary"' in report_md or '"detailed_report"' in report_md:
                    logger.warning("Daily report: detailed_report contains raw JSON, skipping Notion")
                    report_md = result.get("brief_summary", "")  # Use brief as fallback
                notion_url = await self.notion_service.sync_report(
                    start_date=date_str,
                    end_date=date_str,
                    report_md=report_md,
                    source="Telegram Bot",
                )

                # Build cost info
                cost_parts = []
                if result.get("cost_usd"):
                    cost_parts.append(f"~${result['cost_usd']:.4f}")
                if result.get("iterations"):
                    cost_parts.append(f"{result['iterations']} шагов")
                cost_info = " | ".join(cost_parts) if cost_parts else None

                html_text = ReportFormatter.format_for_telegram(
                    brief_summary=result["brief_summary"],
                    notion_url=notion_url,
                    cost_info=cost_info,
                )
                keyboard = ReportFormatter.create_report_keyboard("daily")

                for user_id in self._get_report_recipients():
                    try:
                        self.report_storage.save_report(
                            user_id=user_id,
                            report_type="daily_auto",
                            title=f"Ежедневная сводка за {yesterday.strftime('%d.%m.%Y')}",
                            content=result.get("detailed_report", ""),
                            start_date=yesterday,
                            end_date=yesterday,
                        )
                        await self._send_html(user_id, html_text, keyboard)
                        logger.info(f"Sent daily report to user {user_id}")
                    except Exception as e:
                        logger.error(f"Failed to send report to user {user_id}: {e}")

                # Пометить что отчёт за сегодня отправлен
                self._daily_report_sent_date = date.today()

            except Exception as e:
                logger.error(f"Daily report job failed: {e}", exc_info=True)

        # ─── Weekly report (Monday) ────────────────
        async def send_weekly_report():
            logger.info("Sending scheduled weekly report (Oleg)")
            try:
                end = datetime.now() - timedelta(days=1)
                start = end - timedelta(days=6)
                s, e = start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")

                result = await self.oleg_agent.analyze_deep(
                    user_query="Еженедельная аналитическая сводка",
                    params={
                        "start_date": s,
                        "end_date": e,
                        "channels": ["wb", "ozon"],
                        "report_type": "weekly",
                    },
                )

                if not result.get("brief_summary") or not result.get("success", True):
                    logger.error(f"Weekly report failed: {result.get('error', 'no brief_summary')}")
                    return

                notion_url = await self.notion_service.sync_report(
                    start_date=s, end_date=e,
                    report_md=result.get("detailed_report", ""),
                )

                cost_parts = []
                if result.get("cost_usd"):
                    cost_parts.append(f"~${result['cost_usd']:.4f}")
                if result.get("iterations"):
                    cost_parts.append(f"{result['iterations']} шагов")
                cost_info = " | ".join(cost_parts) if cost_parts else None

                html_text = ReportFormatter.format_for_telegram(
                    brief_summary=result["brief_summary"],
                    notion_url=notion_url,
                    cost_info=cost_info,
                )
                keyboard = ReportFormatter.create_report_keyboard("weekly")

                for user_id in self._get_report_recipients():
                    try:
                        await self._send_html(user_id, html_text, keyboard)
                        logger.info(f"Sent weekly report to user {user_id}")
                    except Exception as e:
                        logger.error(f"Failed to send weekly report to {user_id}: {e}")

            except Exception as e:
                logger.error(f"Weekly report job failed: {e}", exc_info=True)

        # ─── Monthly check (every Monday — sends if new month started) ──
        async def check_and_send_monthly():
            today = datetime.now()
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

                result = await self.oleg_agent.analyze_deep(
                    user_query=f"Месячный аналитический отчёт за {month_str}",
                    params={
                        "start_date": s,
                        "end_date": e,
                        "channels": ["wb", "ozon"],
                        "report_type": "monthly",
                    },
                )

                if not result.get("brief_summary") or not result.get("success", True):
                    logger.error(f"Monthly report failed: {result.get('error', 'no brief_summary')}")
                    return

                notion_url = await self.notion_service.sync_report(
                    start_date=s, end_date=e,
                    report_md=result.get("detailed_report", ""),
                )

                cost_parts = []
                if result.get("cost_usd"):
                    cost_parts.append(f"~${result['cost_usd']:.4f}")
                if result.get("iterations"):
                    cost_parts.append(f"{result['iterations']} шагов")
                cost_info = " | ".join(cost_parts) if cost_parts else None

                html_text = ReportFormatter.format_for_telegram(
                    brief_summary=result["brief_summary"],
                    notion_url=notion_url,
                    cost_info=cost_info,
                )
                keyboard = ReportFormatter.create_report_keyboard("monthly")

                for user_id in self._get_report_recipients():
                    try:
                        self.report_storage.save_report(
                            user_id=user_id,
                            report_type="monthly_auto",
                            title=f"Месячный отчёт за {month_str}",
                            content=result.get("detailed_report", ""),
                            metadata={"month": month_str},
                        )
                        await self._send_html(user_id, html_text, keyboard)
                        logger.info(f"Sent monthly report to user {user_id}")
                    except Exception as e:
                        logger.error(f"Failed to send monthly report to {user_id}: {e}")

            except Exception as e:
                logger.error(f"Monthly report job failed: {e}", exc_info=True)

        # ─── Data freshness monitor ────────────────
        # Флаг: дневной отчёт за сегодня уже отправлен?
        self._daily_report_sent_date: Optional[date] = None

        async def check_data_freshness():
            if self.data_freshness.already_notified_today():
                # Данные уже были объявлены готовыми сегодня.
                # Проверяем, не нужно ли догенерировать отчёт
                # (если send_daily_report пропустил из-за неготовности данных).
                today = date.today()
                if self._daily_report_sent_date != today:
                    logger.info("Data ready, but daily report not yet sent — triggering now")
                    await send_daily_report()
                    if self._daily_report_sent_date != today:
                        # send_daily_report пометит дату если успешно (см. ниже)
                        pass
                return
            try:
                status = self.data_freshness.check_freshness()
                if not self.data_freshness.is_all_ready(status):
                    return

                self.data_freshness.mark_notified()
                msg = self.data_freshness.format_notification(status)
                for user_id in self._get_report_recipients():
                    try:
                        await self.bot.send_message(chat_id=user_id, text=msg)
                    except Exception as e:
                        logger.error(f"Failed to send freshness notification to {user_id}: {e}")

                # Если дневной отчёт ещё не был отправлен — отправить сейчас
                today = date.today()
                if self._daily_report_sent_date != today:
                    logger.info("Data just became ready — generating daily report")
                    await send_daily_report()
            except Exception as e:
                logger.error(f"Data freshness check failed: {e}")

        # ─── Schedule all jobs ────────────────
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

        from apscheduler.triggers.cron import CronTrigger
        self.scheduler.scheduler.add_job(
            check_data_freshness,
            trigger=CronTrigger(
                minute="*/5", hour="6-14",
                timezone=self.scheduler.timezone,
            ),
            id="data_freshness_check",
            name="Data Freshness Check (every 5 min, 06:00–14:00)",
            replace_existing=True,
        )

        # ─── Weekly price review (Monday 11:00 MSK) ────────────
        async def send_weekly_price_review():
            logger.info("Sending scheduled weekly price review (Oleg)")
            try:
                end = datetime.now() - timedelta(days=1)
                start = end - timedelta(days=6)
                s, e = start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")

                result = await self.oleg_agent.analyze(
                    user_query="Еженедельный ценовой обзор: эластичность, рекомендации по ценам, тренды",
                    params={
                        "start_date": s,
                        "end_date": e,
                        "channels": ["wb", "ozon"],
                        "report_type": "price_review",
                    },
                )

                if not result.get("brief_summary") or not result.get("success", True):
                    logger.error(f"Weekly price review failed: {result.get('error')}")
                    return

                notion_url = await self.notion_service.sync_report(
                    start_date=s, end_date=e,
                    report_md=result.get("detailed_report", ""),
                    source="Price Review (auto)",
                )

                cost_parts = []
                if result.get("cost_usd"):
                    cost_parts.append(f"~${result['cost_usd']:.4f}")
                if result.get("iterations"):
                    cost_parts.append(f"{result['iterations']} шагов")
                cost_info = " | ".join(cost_parts) if cost_parts else None

                html_text = ReportFormatter.format_for_telegram(
                    brief_summary=result["brief_summary"],
                    notion_url=notion_url,
                    cost_info=cost_info,
                )

                for user_id in self._get_report_recipients():
                    try:
                        await self._send_html(user_id, html_text)
                        logger.info(f"Sent weekly price review to user {user_id}")
                    except Exception as e:
                        logger.error(f"Failed to send price review to {user_id}: {e}")
            except Exception as e:
                logger.error(f"Weekly price review job failed: {e}", exc_info=True)

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

        # ─── Outcome checker (Wednesday 09:00 MSK) ────────────
        async def check_recommendation_outcomes():
            logger.info("Checking recommendation outcomes")
            try:
                unchecked = self.learning_store.get_unchecked_recommendations(min_age_days=7)
                if not unchecked:
                    logger.info("No unchecked recommendations older than 7 days")
                    return

                for rec in unchecked:
                    try:
                        model = rec.get('model', '')
                        channel = rec.get('channel', 'wb')
                        rec_date = rec.get('created_at', '')[:10]

                        # Получить фактические данные за 7 дней после рекомендации
                        from shared.data_layer import (
                            get_wb_price_margin_by_model_period,
                            get_ozon_price_margin_by_model_period,
                        )
                        fact_start = rec_date
                        fact_end = (datetime.strptime(rec_date, '%Y-%m-%d') + timedelta(days=7)).strftime('%Y-%m-%d')

                        if channel == 'wb':
                            facts = get_wb_price_margin_by_model_period(fact_start, fact_end)
                        else:
                            facts = get_ozon_price_margin_by_model_period(fact_start, fact_end)

                        model_fact = next((f for f in facts if f.get('model', '').lower() == model.lower()), None)
                        if model_fact:
                            self.learning_store.record_outcome(
                                recommendation_id=rec['id'],
                                actual_margin_impact=model_fact.get('margin', 0),
                                actual_volume_impact=model_fact.get('sales_count', 0),
                            )
                            logger.info(f"Recorded outcome for recommendation {rec['id']} ({model})")
                    except Exception as e:
                        logger.error(f"Failed to check outcome for rec {rec.get('id')}: {e}")
            except Exception as e:
                logger.error(f"Outcome checker failed: {e}", exc_info=True)

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

        logger.info("Scheduler configured: daily/weekly/monthly/freshness/price_review/outcome_checker")

    async def _send_html(self, user_id: int, html_text: str, keyboard=None) -> None:
        """Send HTML message, splitting by paragraphs if needed."""
        MAX_LEN = 4000
        if len(html_text) <= MAX_LEN:
            await self.bot.send_message(
                chat_id=user_id, text=html_text,
                parse_mode="HTML", reply_markup=keyboard,
            )
        else:
            # Split by paragraph breaks to avoid cutting HTML tags
            paragraphs = html_text.split('\n\n')
            chunks = []
            current = ""
            for p in paragraphs:
                if len(current) + len(p) + 2 > MAX_LEN:
                    if current:
                        chunks.append(current)
                    current = p[:MAX_LEN]  # safety trim
                else:
                    current = current + "\n\n" + p if current else p
            if current:
                chunks.append(current)

            for i, chunk in enumerate(chunks):
                kb = keyboard if i == len(chunks) - 1 else None
                await self.bot.send_message(
                    chat_id=user_id, text=chunk,
                    parse_mode="HTML", reply_markup=kb,
                )

    async def _preflight_checks(self) -> bool:
        """
        Pre-flight проверки перед стартом polling.
        Если критичная проверка не прошла — возвращает False.
        """
        all_ok = True

        # 1. z.ai API
        try:
            health = await self.zai_client.health_check()
            if health:
                logger.info("Pre-flight: z.ai API — OK")
            else:
                logger.error("Pre-flight: z.ai API — FAIL (health=False)")
                all_ok = False
        except Exception as e:
            logger.error(f"Pre-flight: z.ai API — FAIL ({e})")
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

        # 4. Telegram Bot API
        try:
            me = await self.bot.get_me()
            logger.info(f"Pre-flight: Telegram Bot API — OK (@{me.username})")
        except Exception as e:
            logger.error(f"Pre-flight: Telegram Bot API — FAIL ({e})")
            all_ok = False

        # 5. Notion (не критично — warn)
        if config.NOTION_TOKEN:
            try:
                # Простая проверка — если токен есть, считаем OK
                logger.info("Pre-flight: Notion token — present")
            except Exception as e:
                logger.warning(f"Pre-flight: Notion — WARN ({e})")

        return all_ok

    async def _recover_missed_reports(self) -> None:
        """Generate daily report if it was missed (e.g. bot was down at 10:05)."""
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        if self.report_storage.has_report_for_period("daily_auto", yesterday):
            logger.info(f"Recovery: daily report for {yesterday} already exists, skip")
            return

        try:
            freshness = self.data_freshness.check_freshness()
            if not self.data_freshness.is_all_ready(freshness):
                logger.info(f"Recovery: data for {yesterday} not ready yet, skip")
                return
        except Exception as e:
            logger.warning(f"Recovery: freshness check failed ({e}), skip")
            return

        recipients = self._get_report_recipients()
        if not recipients:
            logger.warning("Recovery: no recipients, skip")
            return

        logger.info(f"Recovery: generating missed daily report for {yesterday}")
        try:
            result = await self.oleg_agent.analyze_deep(
                user_query="Ежедневная аналитическая сводка",
                params={
                    "start_date": yesterday,
                    "end_date": yesterday,
                    "channels": ["wb", "ozon"],
                    "report_type": "daily",
                },
            )
            if not result.get("brief_summary") or not result.get("success", True):
                logger.error(f"Recovery: report generation failed: {result.get('error')}")
                return

            report_md = result.get("detailed_report", "")
            if '"brief_summary"' in report_md or '"detailed_report"' in report_md:
                logger.warning("Recovery: detailed_report contains raw JSON, using brief as fallback")
                report_md = result.get("brief_summary", "")
            notion_url = await self.notion_service.sync_report(
                start_date=yesterday, end_date=yesterday,
                report_md=report_md,
                source="Telegram Bot (recovery)",
            )

            cost_parts = []
            if result.get("cost_usd"):
                cost_parts.append(f"~${result['cost_usd']:.4f}")
            if result.get("iterations"):
                cost_parts.append(f"{result['iterations']} шагов")
            cost_info = " | ".join(cost_parts) if cost_parts else None

            html_text = ReportFormatter.format_for_telegram(
                brief_summary=result["brief_summary"],
                notion_url=notion_url,
                cost_info=cost_info,
            )
            keyboard = ReportFormatter.create_report_keyboard("daily")

            yd = datetime.strptime(yesterday, "%Y-%m-%d")
            for user_id in recipients:
                try:
                    self.report_storage.save_report(
                        user_id=user_id,
                        report_type="daily_auto",
                        title=f"Ежедневная сводка за {yd.strftime('%d.%m.%Y')}",
                        content=result.get("detailed_report", ""),
                        start_date=yd,
                        end_date=yd,
                    )
                    await self._send_html(user_id, html_text, keyboard)
                    logger.info(f"Recovery: sent daily report to user {user_id}")
                except Exception as e:
                    logger.error(f"Recovery: failed to send to {user_id}: {e}")

            self._daily_report_sent_date = date.today()
            logger.info(f"Recovery: daily report for {yesterday} done")
        except Exception as e:
            logger.error(f"Recovery: failed: {e}", exc_info=True)

    async def run(self) -> None:
        """Запуск бота"""
        # Pre-flight проверки
        preflight_ok = await self._preflight_checks()
        if not preflight_ok:
            logger.critical("Pre-flight checks FAILED — бот не может стартовать")
            sys.exit(1)

        self.scheduler.start()
        self._setup_scheduler()

        # Recover missed reports before starting polling
        try:
            await self._recover_missed_reports()
        except Exception as e:
            logger.warning(f"Recovery check failed: {e}")

        # Clear any stale polling sessions to avoid ConflictError
        try:
            await self.bot.delete_webhook(drop_pending_updates=False)
            logger.info("Cleared previous webhook/polling session")
        except Exception as e:
            logger.warning(f"Failed to clear webhook: {e}")

        logger.info("Oleg Bot started!")

        try:
            await self._start_polling_with_conflict_timeout()
        finally:
            await self.shutdown()

    async def _start_polling_with_conflict_timeout(
        self, conflict_timeout: int = 60,
    ) -> None:
        """
        Запускает polling с таймаутом на TelegramConflictError.

        Если ConflictError не разрешается за conflict_timeout секунд,
        бот завершается с exit(1). Docker restart policy перезапустит.
        """
        conflict_first_seen: Optional[float] = None
        shutdown_requested = asyncio.Event()

        async def monitor_conflict():
            nonlocal conflict_first_seen
            while not shutdown_requested.is_set():
                if conflict_first_seen is not None:
                    elapsed = time.time() - conflict_first_seen
                    if elapsed > conflict_timeout:
                        logger.critical(
                            f"TelegramConflictError persisted for {elapsed:.0f}s "
                            f"— exiting. Another bot instance is likely running."
                        )
                        os._exit(1)
                await asyncio.sleep(5)

        # Intercept ConflictError via aiogram's error handler
        from aiogram.types import ErrorEvent
        from aiogram.exceptions import TelegramConflictError

        @self.dp.errors()
        async def on_polling_error(event: ErrorEvent):
            nonlocal conflict_first_seen
            if isinstance(event.exception, TelegramConflictError):
                if conflict_first_seen is None:
                    conflict_first_seen = time.time()
                    logger.warning(
                        f"TelegramConflictError detected. "
                        f"Will exit if not resolved in {conflict_timeout}s"
                    )
            else:
                # Reset timer on non-conflict errors (polling is alive)
                conflict_first_seen = None

        monitor_task = asyncio.create_task(monitor_conflict())

        try:
            await self.dp.start_polling(
                self.bot,
                allowed_updates=self.dp.resolve_used_update_types(),
            )
        finally:
            shutdown_requested.set()
            monitor_task.cancel()
            try:
                await monitor_task
            except asyncio.CancelledError:
                pass

    async def shutdown(self) -> None:
        """Cleanup on shutdown"""
        logger.info("Shutting down Oleg Bot...")
        self.scheduler.shutdown()
        await self.bot.session.close()
        deleted = self.report_storage.cleanup_old_reports(config.REPORT_RETENTION_DAYS)
        logger.info(f"Cleaned up {deleted} old reports")
        logger.info("Shutdown complete")


def _acquire_pid_lock() -> Optional[Path]:
    """Acquire PID lock file. Returns lock path on success, None if another instance is running."""
    lock_path = Path(config.LOG_FILE).parent / "oleg_bot.pid"
    if lock_path.exists():
        try:
            old_pid = int(lock_path.read_text().strip())
            # Check if old process is still alive
            os.kill(old_pid, 0)
            # Process is alive — refuse to start
            return None
        except (ValueError, ProcessLookupError, PermissionError):
            # PID file is stale (process dead or invalid) — safe to overwrite
            pass

    lock_path.write_text(str(os.getpid()))
    return lock_path


def _release_pid_lock():
    """Remove PID lock file."""
    lock_path = Path(config.LOG_FILE).parent / "oleg_bot.pid"
    try:
        lock_path.unlink(missing_ok=True)
    except Exception:
        pass


def main():
    """Entry point"""
    if not config.TELEGRAM_BOT_TOKEN:
        print("ERROR: TELEGRAM_BOT_TOKEN not set in .env")
        sys.exit(1)

    if not config.ZAI_API_KEY:
        print("ERROR: ZAI_API_KEY not set in .env")
        sys.exit(1)

    lock = _acquire_pid_lock()
    if lock is None:
        print("ERROR: Another Oleg Bot instance is already running. Exiting.")
        logger.critical("Refused to start: another instance is already running (PID lock)")
        sys.exit(1)

    bot = OlegBot()

    try:
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Bot crashed: {e}", exc_info=True)
        sys.exit(1)
    finally:
        _release_pid_lock()


if __name__ == "__main__":
    main()
