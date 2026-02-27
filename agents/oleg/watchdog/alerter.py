"""
Alerter — sends Telegram alerts with diagnostic results.
"""
import hashlib
import logging
import time
from typing import Dict, Optional

from agents.oleg.watchdog.diagnostic import DiagnosticReport

logger = logging.getLogger(__name__)


class Alerter:
    """Telegram alerter for watchdog events."""

    DEDUP_WINDOW_SEC = 300  # 5 minutes

    def __init__(self, bot=None, admin_chat_id: int = 0, auth_service=None):
        self.bot = bot
        self.admin_chat_id = admin_chat_id
        self.auth_service = auth_service
        self._sent_hashes: Dict[str, float] = {}

    def _get_recipients(self) -> list:
        """Get notification recipients from auth_service + admin fallback."""
        recipients = set()
        if self.auth_service:
            recipients.update(self.auth_service._authenticated)
        if self.admin_chat_id:
            recipients.add(self.admin_chat_id)
        return list(recipients)

    def _cleanup_old_hashes(self) -> None:
        """Remove expired entries from dedup cache."""
        now = time.time()
        expired = [h for h, ts in self._sent_hashes.items()
                   if now - ts > self.DEDUP_WINDOW_SEC]
        for h in expired:
            del self._sent_hashes[h]

    async def send_alert(self, message: str) -> bool:
        """Send a plain text alert to all notification recipients."""
        # Dedup: skip if same message sent in last 5 minutes
        self._cleanup_old_hashes()
        msg_hash = hashlib.sha256(message.encode()).hexdigest()[:16]
        if msg_hash in self._sent_hashes:
            logger.info(f"Alert deduplicated (hash={msg_hash})")
            return True

        recipients = self._get_recipients()
        if not self.bot or not recipients:
            logger.warning(f"Alert not sent (no bot/recipients): {message[:100]}")
            return False

        sent = False
        for chat_id in recipients:
            try:
                await self.bot.send_message(
                    chat_id=chat_id,
                    text=message[:4000],
                )
                logger.info(f"Alert sent to {chat_id}")
                sent = True
            except Exception as e:
                logger.error(f"Failed to send alert to {chat_id}: {e}")

        if sent:
            self._sent_hashes[msg_hash] = time.time()

        return sent

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
