"""
Reporter Agent system prompt — loaded from playbook.md.
"""
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Default playbook path (can be overridden in config)
_DEFAULT_PLAYBOOK = Path(__file__).resolve().parent.parent.parent / "playbook.md"
_V1_PLAYBOOK = Path(__file__).resolve().parent.parent.parent.parent / "oleg" / "playbook.md"

REPORTER_PREAMBLE = """Ты — Reporter, суб-агент системы Олег v2.

Твоя роль: сбор данных и формирование структурированных финансовых отчётов.
Ты работаешь с проверенными SQL-запросами через tools и формируешь отчёты
по формулам из playbook.

ВАЖНЫЕ ПРАВИЛА:
1. Используй tools для получения данных — НЕ придумывай цифры
2. Начинай с get_brand_finance для общей картины
3. Используй get_margin_levers для декомпозиции "почему изменилась маржа"
4. Всегда проверяй данные через validate_data_quality
5. ДРР — ВСЕГДА с разбивкой на внутреннюю и внешнюю рекламу
6. Выкуп % — лаговый показатель (3-21 дн), НЕ используй как причину дневных изменений
7. СПП% при объединении каналов — ТОЛЬКО средневзвешенный
8. GROUP BY по модели — ВСЕГДА с LOWER()

Формат ответа:
- brief_summary: краткая сводка для Telegram (BBCode)
- detailed_report: полный отчёт в Markdown для Notion
"""


def get_reporter_system_prompt(playbook_path: str = None) -> str:
    """Load the full system prompt: preamble + playbook."""
    # Try v2 playbook first, then v1
    playbook_file = Path(playbook_path) if playbook_path else _DEFAULT_PLAYBOOK
    if not playbook_file.exists():
        playbook_file = _V1_PLAYBOOK

    playbook_content = ""
    if playbook_file.exists():
        try:
            playbook_content = playbook_file.read_text(encoding="utf-8")
            logger.info(f"Loaded playbook from {playbook_file} ({len(playbook_content)} chars)")
        except Exception as e:
            logger.error(f"Failed to load playbook: {e}")
    else:
        logger.warning("No playbook.md found, using preamble only")

    if playbook_content:
        return f"{REPORTER_PREAMBLE}\n\n---\n\n{playbook_content}"
    return REPORTER_PREAMBLE
