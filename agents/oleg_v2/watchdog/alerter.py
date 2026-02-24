"""
Alerter — sends Telegram alerts with diagnostic results.
"""
import logging
from typing import Optional

from agents.oleg_v2.watchdog.diagnostic import DiagnosticReport

logger = logging.getLogger(__name__)


class Alerter:
    """Telegram alerter for watchdog events."""

    def __init__(self, bot=None, admin_chat_id: int = 0):
        self.bot = bot
        self.admin_chat_id = admin_chat_id

    async def send_alert(self, message: str) -> bool:
        """Send a plain text alert to admin."""
        if not self.bot or not self.admin_chat_id:
            logger.warning(f"Alert not sent (no bot/chat_id): {message[:100]}")
            return False

        try:
            await self.bot.send_message(
                chat_id=self.admin_chat_id,
                text=message[:4000],
            )
            logger.info(f"Alert sent to {self.admin_chat_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to send alert: {e}")
            return False

    async def send_diagnostic_alert(self, diagnostic: DiagnosticReport) -> bool:
        """Send a formatted diagnostic alert."""
        message = diagnostic.format_telegram()
        return await self.send_alert(message)

    async def send_report_failure_alert(
        self,
        report_type: str,
        consecutive_failures: int = 1,
        diagnostic: Optional[DiagnosticReport] = None,
    ) -> bool:
        """Send escalating alert based on consecutive failures."""
        if consecutive_failures == 1:
            message = (
                f"Отчёт ({report_type}) не создан. "
                f"Запустил диагностику, ищу причину."
            )
        elif consecutive_failures == 2:
            message = (
                f"⚠️ Отчёт ({report_type}) не создан 2-й день подряд. "
            )
        else:
            message = (
                f"🚨 КРИТИЧНО: {consecutive_failures} дней без отчётов "
                f"({report_type}). Требуется ваше внимание СЕЙЧАС."
            )

        if diagnostic:
            message += "\n\n" + diagnostic.format_telegram()

        return await self.send_alert(message)
