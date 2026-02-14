"""
Feedback Service — обработка обратной связи через Олега.

Олег перепроверяет данные через инструменты (tool-use),
сравнивает свой расчёт с замечанием пользователя.
Может принять, отклонить или частично принять feedback.
"""
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

from agents.oleg import config

logger = logging.getLogger(__name__)

PLAYBOOK_PATH = Path(config.PLAYBOOK_PATH)
FEEDBACK_LOG_PATH = Path(config.FEEDBACK_LOG_PATH)


class FeedbackService:
    """Обработка обратной связи через Олега с перепроверкой данных."""

    def __init__(self, notion_token: str = ""):
        self.notion_token = notion_token

    async def process_feedback(
        self,
        feedback_text: str,
        original_report: str,
        query_params: dict,
        oleg_agent,
        user_id: int = 0,
        report_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Обработка feedback через Олега с перепроверкой данных.

        Олег ОБЯЗАН запросить данные заново через инструменты и сравнить
        свой расчёт с замечанием пользователя.

        Returns:
            {
                "category": "format|rule|calculation_error",
                "verdict": "accepted|rejected|partially_accepted",
                "user_message": "сообщение для Telegram",
                "auto_updated": True/False,
                "cost_usd": float,
            }
        """
        report_context = report_context or {}

        # Step 1: Oleg verifies feedback through tool-use
        verification = await oleg_agent.verify_feedback(
            feedback_text=feedback_text,
            original_report=original_report,
            params=query_params,
        )

        category = verification.get("category", "format")
        verdict = verification.get("verdict", "accepted")
        user_message = verification.get("user_message", "Обратная связь принята.")
        playbook_update = verification.get("playbook_update")
        cost = verification.get("cost_usd", 0)

        result = {
            "category": category,
            "verdict": verdict,
            "user_message": user_message,
            "auto_updated": False,
            "cost_usd": cost,
            "reasoning_steps": verification.get("reasoning_steps", []),
        }

        # Step 2: Update playbook if feedback accepted
        if verdict in ("accepted", "partially_accepted") and playbook_update:
            try:
                self._update_playbook(category, playbook_update)
                self._log_feedback(
                    category=category,
                    verdict=verdict,
                    description=playbook_update,
                    feedback_text=feedback_text,
                    user_id=user_id,
                )
                result["auto_updated"] = True
            except Exception as e:
                logger.error(f"Failed to update playbook: {e}")

        # Step 3: Log rejected feedback too (for analysis)
        if verdict == "rejected":
            try:
                self._log_feedback(
                    category=category,
                    verdict=verdict,
                    description=verification.get("explanation", ""),
                    feedback_text=feedback_text,
                    user_id=user_id,
                )
            except Exception as e:
                logger.error(f"Failed to log rejected feedback: {e}")

        # Step 4: Notion comment
        notion_page_id = report_context.get("notion_page_id")
        if notion_page_id and self.notion_token:
            try:
                await self._add_notion_comment(
                    page_id=notion_page_id,
                    comment=(
                        f"[Feedback от user {user_id}] ({category}/{verdict}): "
                        f"{feedback_text}\n\nОлег: {user_message}"
                    ),
                )
            except Exception as e:
                logger.warning(f"Failed to add Notion comment: {e}")

        return result

    def _update_playbook(self, category: str, description: str) -> None:
        """Добавить правило в playbook Олега."""
        if not PLAYBOOK_PATH.exists():
            logger.warning(f"Playbook not found: {PLAYBOOK_PATH}")
            return

        content = PLAYBOOK_PATH.read_text(encoding="utf-8")
        today = datetime.now().strftime("%Y-%m-%d")
        entry = f"\n- [{today}] ({category}) {description}"

        if "## История правок" in content:
            content += entry
        else:
            content += f"\n\n## История правок\n{entry}"

        PLAYBOOK_PATH.write_text(content, encoding="utf-8")
        logger.info(f"Playbook updated: {category} — {description[:60]}")

    def _log_feedback(
        self,
        category: str,
        verdict: str,
        description: str,
        feedback_text: str,
        user_id: int,
    ) -> None:
        """Записать в feedback_log Олега."""
        today = datetime.now().strftime("%Y-%m-%d %H:%M")

        entry = (
            f"\n### {today} — Feedback ({verdict})\n\n"
            f"**User ID:** {user_id}\n"
            f"**Категория:** {category}\n"
            f"**Вердикт:** {verdict}\n"
            f"**Текст пользователя:** {feedback_text}\n"
            f"**Описание/обновление:** {description}\n"
        )

        if FEEDBACK_LOG_PATH.exists():
            content = FEEDBACK_LOG_PATH.read_text(encoding="utf-8")
            content += entry
        else:
            content = "# Лог обратной связи — Олег\n\n" + entry

        FEEDBACK_LOG_PATH.write_text(content, encoding="utf-8")
        logger.info(f"Feedback logged: {category}/{verdict}")

    async def _add_notion_comment(self, page_id: str, comment: str) -> None:
        """Добавить комментарий к странице Notion через API."""
        import httpx

        url = "https://api.notion.com/v1/comments"
        headers = {
            "Authorization": f"Bearer {self.notion_token}",
            "Content-Type": "application/json",
            "Notion-Version": "2022-06-28",
        }
        body = {
            "parent": {"page_id": page_id},
            "rich_text": [
                {"type": "text", "text": {"content": comment[:2000]}},
            ],
        }

        async with httpx.AsyncClient() as client:
            resp = await client.post(url, headers=headers, json=body, timeout=15)
            if resp.status_code == 200:
                logger.info(f"Notion comment added to page {page_id}")
            else:
                logger.warning(f"Notion comment failed ({resp.status_code}): {resp.text}")
