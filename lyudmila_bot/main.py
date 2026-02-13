"""
Lyudmila Bot — IEE-агент, офис-менеджер и бизнес-ассистент Wookiee

Точка входа: python -m lyudmila_bot.main
"""
import asyncio
import logging
import sys
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from lyudmila_bot import config
from lyudmila_bot.services.bitrix_service import BitrixService
from lyudmila_bot.services.user_cache import UserCache
from lyudmila_bot.services.db_service import DBService
from lyudmila_bot.services.auth_service import AuthService
from lyudmila_bot.services.lyuda_ai import LyudaAI
from lyudmila_bot.services.digest_service import DigestService
from lyudmila_bot.services.scheduler_service import LyudmilaScheduler
from lyudmila_bot.services.supabase_service import LyudmilaSupabase
from lyudmila_bot.services.sync_service import BitrixSyncService
from lyudmila_bot.services.weekly_digest_service import WeeklyDigestService
from lyudmila_bot.services.context_service import ContextService

from lyudmila_bot.handlers import auth, menu, task_creation, meeting_creation, digest, free_input

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


class LyudmilaBot:
    """Главный класс бота Людмилы"""

    def __init__(self):
        logger.info("Initializing Lyudmila Bot...")

        # Bot & Dispatcher
        self.bot = Bot(
            token=config.LYUDMILA_BOT_TOKEN,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )
        self.dp = Dispatcher()

        # Services
        self.bitrix_service = BitrixService()
        self.user_cache = UserCache(self.bitrix_service)
        self.db_service = DBService()
        self.auth_service = AuthService(self.bitrix_service, self.db_service)
        self.lyuda_ai = LyudaAI()
        self.scheduler = LyudmilaScheduler(config.DEFAULT_TIMEZONE)

        # Supabase — память Людмилы
        self.supabase = LyudmilaSupabase()
        self.sync_service = BitrixSyncService(self.bitrix_service, self.supabase)

        # Digest (с Supabase для группировки по датам)
        self.digest_service = DigestService(self.bitrix_service, self.lyuda_ai, supabase=self.supabase)
        self.weekly_service = WeeklyDigestService(self.lyuda_ai, self.supabase)
        self.context_service = ContextService(self.supabase)

        # Register middleware & routers
        self._setup_middleware()
        self._register_routers()

        logger.info("Lyudmila Bot initialized")

    def _setup_middleware(self) -> None:
        """DI middleware — инжектирует сервисы в хендлеры"""

        @self.dp.message.middleware()
        async def inject_services(handler, event, data):
            data['auth_service'] = self.auth_service
            data['db_service'] = self.db_service
            data['bitrix_service'] = self.bitrix_service
            data['user_cache'] = self.user_cache
            data['lyuda_ai'] = self.lyuda_ai
            data['digest_service'] = self.digest_service
            data['supabase'] = self.supabase
            data['sync_service'] = self.sync_service
            data['weekly_service'] = self.weekly_service
            data['context_service'] = self.context_service
            return await handler(event, data)

        @self.dp.callback_query.middleware()
        async def inject_services_callback(handler, event, data):
            data['auth_service'] = self.auth_service
            data['db_service'] = self.db_service
            data['bitrix_service'] = self.bitrix_service
            data['user_cache'] = self.user_cache
            data['lyuda_ai'] = self.lyuda_ai
            data['digest_service'] = self.digest_service
            data['supabase'] = self.supabase
            data['sync_service'] = self.sync_service
            data['weekly_service'] = self.weekly_service
            data['context_service'] = self.context_service
            return await handler(event, data)

    def _register_routers(self) -> None:
        """Регистрация роутеров (порядок важен!)"""
        self.dp.include_router(auth.router)
        self.dp.include_router(task_creation.router)
        self.dp.include_router(meeting_creation.router)
        self.dp.include_router(digest.router)
        self.dp.include_router(menu.router)
        self.dp.include_router(free_input.router)  # ПОСЛЕДНИМ — catch-all для свободного ввода

        logger.info("Routers registered")

    def _setup_scheduler(self) -> None:
        """Настроить расписание"""
        # Обновление кеша сотрудников
        self.scheduler.schedule_cache_refresh(
            self.user_cache.load,
            minutes=config.USER_CACHE_REFRESH_MINUTES,
        )

        # Проверка уволенных
        async def check_deactivated():
            """Деактивировать уволенных сотрудников"""
            for tg_id, user in list(self.auth_service.authenticated_users.items()):
                try:
                    bitrix_user = await self.bitrix_service.get_user_by_id(user.bitrix_user_id)
                    if not bitrix_user or not bitrix_user.get('ACTIVE', True):
                        self.auth_service.logout(tg_id)
                        self.db_service.deactivate_user(tg_id)
                        logger.info(f"Deactivated fired user: tg={tg_id}")
                except Exception as e:
                    logger.error(f"Deactivation check error for {tg_id}: {e}")

        self.scheduler.schedule_deactivation_check(check_deactivated, hours=6)

        # Дайджесты для всех пользователей
        async def send_digest(telegram_id: int):
            """Отправить дайджест конкретному пользователю"""
            user = self.auth_service.get_user(telegram_id)
            if not user or not user.digest_enabled:
                return

            try:
                digest_text = await self.digest_service.generate_digest(user)
                from lyudmila_bot.handlers.common import menu_only_keyboard
                await self.bot.send_message(
                    chat_id=telegram_id,
                    text=digest_text,
                    parse_mode="HTML",
                    reply_markup=menu_only_keyboard(),
                )
                logger.info(f"Digest sent to {telegram_id}")
            except Exception as e:
                logger.error(f"Failed to send digest to {telegram_id}: {e}")

        # Планируем дайджесты для существующих пользователей
        for user_data in self.db_service.get_all_active_users():
            if user_data.get('digest_enabled'):
                hour, minute = map(int, user_data.get('digest_time', '09:00').split(':'))
                self.scheduler.schedule_digest(
                    telegram_id=user_data['telegram_id'],
                    callback=send_digest,
                    hour=hour,
                    minute=minute,
                    timezone=user_data.get('timezone', config.DEFAULT_TIMEZONE),
                )

        # ─── Еженедельные сводки (понедельник) ─────────────────────
        if config.SUPABASE_HOST:
            # Персональная сводка каждому пользователю — пн 09:05
            async def send_weekly_personal(telegram_id: int):
                user = self.auth_service.get_user(telegram_id)
                if not user:
                    return
                try:
                    text = await self.weekly_service.generate_personal(user)
                    from lyudmila_bot.handlers.common import menu_only_keyboard
                    await self.bot.send_message(
                        chat_id=telegram_id,
                        text=text,
                        parse_mode="HTML",
                        reply_markup=menu_only_keyboard(),
                    )
                    logger.info(f"Weekly personal sent to {telegram_id}")
                except Exception as e:
                    logger.error(f"Failed to send weekly personal to {telegram_id}: {e}")

            for user_data in self.db_service.get_all_active_users():
                tid = user_data['telegram_id']
                self.scheduler.schedule_weekly(
                    f"weekly_personal_{tid}",
                    send_weekly_personal,
                    day_of_week="mon", hour=9, minute=5,
                    kwargs={"telegram_id": tid},
                )

            # Командная сводка — пн 10:00 (одна на всех, отправляем первому пользователю)
            async def send_weekly_team():
                try:
                    text = await self.weekly_service.generate_team()
                    from lyudmila_bot.handlers.common import menu_only_keyboard
                    # Отправляем всем активным пользователям
                    for ud in self.db_service.get_all_active_users():
                        try:
                            await self.bot.send_message(
                                chat_id=ud['telegram_id'],
                                text=text,
                                parse_mode="HTML",
                                reply_markup=menu_only_keyboard(),
                            )
                        except Exception as e:
                            logger.warning(f"Failed to send team weekly to {ud['telegram_id']}: {e}")
                    logger.info("Weekly team digest sent")
                except Exception as e:
                    logger.error(f"Failed to generate team weekly: {e}")

            self.scheduler.schedule_weekly(
                "weekly_team",
                send_weekly_team,
                day_of_week="mon", hour=10, minute=0,
            )

        # ─── Синхронизация Bitrix → Supabase ──────────────────────
        if config.SUPABASE_HOST:
            self.scheduler.schedule_sync(
                "sync_employees",
                self.sync_service.sync_employees,
                minutes=30,
            )
            self.scheduler.schedule_sync(
                "sync_recent_tasks",
                self.sync_service.sync_recent_tasks,
                minutes=60,
            )
            self.scheduler.schedule_sync(
                "sync_full_nightly",
                self.sync_service.full_sync,
                hour=3,  # 03:00 ночью
            )

        self.scheduler.start()

    async def _on_startup(self) -> None:
        """Действия при запуске"""
        # Загрузить кеш сотрудников
        try:
            await self.user_cache.load()
            logger.info(f"User cache loaded: {self.user_cache.count} employees")
        except Exception as e:
            logger.error(f"Failed to load user cache: {e}")

        # Проверить Bitrix
        healthy = await self.bitrix_service.health_check()
        if healthy:
            logger.info("Bitrix24 connection: OK")
        else:
            logger.warning("Bitrix24 connection: FAILED")

        # Подключить Supabase (память Людмилы)
        if config.SUPABASE_HOST:
            try:
                await self.supabase.connect()
                sb_ok = await self.supabase.health_check()
                if sb_ok:
                    logger.info("Supabase connection: OK")
                    # Первичная синхронизация сотрудников
                    await self.sync_service.sync_employees()
                else:
                    logger.warning("Supabase connection: health check failed")
            except Exception as e:
                logger.error(f"Supabase connection failed: {e}")
        else:
            logger.warning("Supabase not configured (SUPABASE_HOST empty)")

        # Запустить scheduler
        self._setup_scheduler()

        logger.info("Lyudmila Bot started!")

    async def run(self) -> None:
        """Запуск бота"""
        await self._on_startup()
        try:
            await self.dp.start_polling(self.bot)
        finally:
            self.scheduler.shutdown()
            await self.supabase.close()


def main():
    """Entry point"""
    if not config.LYUDMILA_BOT_TOKEN:
        print("ERROR: LYUDMILA_BOT_TOKEN not set in .env")
        sys.exit(1)

    if not config.BITRIX_WEBHOOK_URL:
        print("ERROR: Bitrix_rest_api (webhook URL) not set in .env")
        sys.exit(1)

    bot = LyudmilaBot()

    try:
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Bot crashed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
