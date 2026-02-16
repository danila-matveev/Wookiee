"""
МОЗГ Людмилы — OpenRouter API для структурирования задач и встреч.

Model tiers:
- LIGHT (glm-4.7-flash): intent detection
- MAIN (glm-4.7): structuring, digests, summaries
"""
import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any

from agents.lyudmila import config
from agents.lyudmila.persona import (
    LYUDA_SYSTEM_PROMPT,
    TASK_STRUCTURING_PROMPT,
    MEETING_STRUCTURING_PROMPT,
    TASK_REFINE_PROMPT,
    MEETING_REFINE_PROMPT,
    DIGEST_PROMPT,
    WEEKLY_PERSONAL_PROMPT,
    WEEKLY_TEAM_PROMPT,
    INTENT_DETECTION_PROMPT,
)
from agents.lyudmila.models.task import TaskStructure
from agents.lyudmila.models.meeting import MeetingStructure

from shared.clients.openrouter_client import OpenRouterClient

logger = logging.getLogger(__name__)


class LyudaAI:
    """
    OpenRouter клиент для Людмилы.

    Все взаимодействия проходят через ИИ:
    - Структурирование задач (с оргструктурой и подсказками)
    - Структурирование встреч
    - Итеративное уточнение
    - Генерация дайджеста (сгруппированного по датам)
    - Еженедельные сводки (персональная + командная)
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        light_model: Optional[str] = None,
        main_model: Optional[str] = None,
    ):
        self.api_key = api_key or config.OPENROUTER_API_KEY
        self.light_model = light_model or config.LIGHT_MODEL
        self.main_model = main_model or config.MAIN_MODEL
        self.llm = OpenRouterClient(api_key=self.api_key, model=self.main_model)

    async def structure_task(
        self,
        user_text: str,
        available_users: str,
        creator_name: str = "",
        team_structure: str = "",
        user_context: str = "",
    ) -> TaskStructure:
        """
        Структурировать описание задачи через LLM.

        Args:
            user_text: Сырой текст от пользователя
            available_users: Список сотрудников (fallback)
            creator_name: Имя постановщика
            team_structure: Оргструктура с должностями (из Supabase)
            user_context: Контекст пользователя (история, предпочтения)
        """
        today = datetime.now().strftime("%d.%m.%Y (%A)")
        prompt = TASK_STRUCTURING_PROMPT.format(
            user_text=user_text,
            today_date=today,
            creator_name=creator_name or "не указан",
            team_structure=team_structure or available_users,
            user_context=user_context or "Нет данных",
        )

        response = await self._complete(LYUDA_SYSTEM_PROMPT, prompt, max_tokens=1500)
        data = self._parse_json(response)
        return TaskStructure.from_dict(data)

    async def structure_meeting(
        self,
        user_text: str,
        available_users: str,
        creator_name: str = "",
        team_structure: str = "",
    ) -> MeetingStructure:
        """
        Структурировать описание встречи через LLM.

        Args:
            user_text: Сырой текст от пользователя
            available_users: Список сотрудников (fallback)
            creator_name: Имя организатора
            team_structure: Оргструктура с должностями (из Supabase)
        """
        today = datetime.now().strftime("%d.%m.%Y (%A)")
        prompt = MEETING_STRUCTURING_PROMPT.format(
            user_text=user_text,
            today_date=today,
            creator_name=creator_name or "не указан",
            team_structure=team_structure or available_users,
        )

        response = await self._complete(LYUDA_SYSTEM_PROMPT, prompt, max_tokens=1500)
        data = self._parse_json(response)
        return MeetingStructure.from_dict(data)

    async def refine_task(
        self,
        current: TaskStructure,
        user_feedback: str,
        available_users: str,
        team_structure: str = "",
    ) -> TaskStructure:
        """Итеративное уточнение задачи"""
        prompt = TASK_REFINE_PROMPT.format(
            current_structure=json.dumps(current.to_dict(), ensure_ascii=False, indent=2),
            user_feedback=user_feedback,
            team_structure=team_structure or available_users,
        )
        response = await self._complete(LYUDA_SYSTEM_PROMPT, prompt, max_tokens=1500)
        data = self._parse_json(response)
        return TaskStructure.from_dict(data)

    async def refine_meeting(
        self,
        current: MeetingStructure,
        user_feedback: str,
        available_users: str,
        team_structure: str = "",
    ) -> MeetingStructure:
        """Итеративное уточнение встречи"""
        prompt = MEETING_REFINE_PROMPT.format(
            current_structure=json.dumps(current.to_dict(), ensure_ascii=False, indent=2),
            user_feedback=user_feedback,
            team_structure=team_structure or available_users,
        )
        response = await self._complete(LYUDA_SYSTEM_PROMPT, prompt, max_tokens=1500)
        data = self._parse_json(response)
        return MeetingStructure.from_dict(data)

    async def generate_digest(self, digest_data: Dict[str, Any]) -> str:
        """
        Сгенерировать утренний дайджест через LLM.

        Args:
            digest_data: Структурированные данные (из DigestService._get_digest_data)
        """
        prompt = DIGEST_PROMPT.format(**digest_data)
        return await self._complete(LYUDA_SYSTEM_PROMPT, prompt, max_tokens=2000)

    async def generate_weekly_personal(self, data: Dict[str, Any]) -> str:
        """Еженедельная персональная сводка"""
        prompt = WEEKLY_PERSONAL_PROMPT.format(**data)
        return await self._complete(LYUDA_SYSTEM_PROMPT, prompt, max_tokens=2500)

    async def generate_weekly_team(self, data: Dict[str, Any]) -> str:
        """Еженедельная командная сводка"""
        prompt = WEEKLY_TEAM_PROMPT.format(**data)
        return await self._complete(LYUDA_SYSTEM_PROMPT, prompt, max_tokens=3000)

    # ─── Intent Detection (Свободный ввод) ────────────────────────

    async def detect_intent(self, user_text: str) -> str:
        """
        Быстрое определение intent по тексту пользователя.
        Uses LIGHT model for speed and cost.

        Returns:
            'task', 'meeting', или 'unknown'
        """
        prompt = INTENT_DETECTION_PROMPT.format(user_text=user_text[:500])
        response = await self._complete(
            LYUDA_SYSTEM_PROMPT, prompt, max_tokens=50, model=self.light_model,
        )
        data = self._parse_json(response)
        intent = data.get("intent", "unknown")
        if intent not in ("task", "meeting", "unknown"):
            intent = "unknown"
        logger.info(f"Intent detected: {intent} for text: {user_text[:80]}...")
        return intent

    # ─── Private ──────────────────────────────────────────────────

    async def _complete(
        self,
        system_message: str,
        user_message: str,
        max_tokens: int = 1000,
        model: Optional[str] = None,
    ) -> str:
        """Отправить запрос в OpenRouter API"""
        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_message},
        ]

        result = await self.llm.complete(
            messages=messages,
            temperature=0.4,
            max_tokens=max_tokens,
            model=model or self.main_model,
        )

        content = result.get("content")
        if content is None:
            error = result.get("error", "unknown error")
            if not error:
                error = "API вернул пустой ответ"
            logger.error(f"LLM API error: {error}")
            raise RuntimeError(f"Ошибка ИИ: {error}")

        usage = result.get("usage", {})
        logger.info(
            f"LyudaAI [{model or self.main_model}]: "
            f"{usage.get('input_tokens', usage.get('prompt_tokens', '?'))}+"
            f"{usage.get('output_tokens', usage.get('completion_tokens', '?'))} tokens"
        )
        return content

    def _parse_json(self, text: str) -> dict:
        """Извлечь JSON из ответа LLM (может быть обёрнут в ```json)"""
        cleaned = text.strip()

        # Убираем markdown-обёртку
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            start = 1
            end = len(lines)
            for i in range(len(lines) - 1, -1, -1):
                if lines[i].strip() == "```":
                    end = i
                    break
            cleaned = "\n".join(lines[start:end])

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM JSON: {e}\nRaw: {text[:500]}")
            raise RuntimeError("ИИ вернул некорректный ответ. Попробуйте ещё раз.")
