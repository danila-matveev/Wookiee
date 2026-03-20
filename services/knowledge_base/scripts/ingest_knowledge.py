#!/usr/bin/env python3
"""
Ingest ALL project knowledge files into the vector KB.

Covers: playbooks, business rules, metric guides, agent specs,
data quality notes, system architecture docs.

Usage:
    python -m services.knowledge_base.scripts.ingest_knowledge [--force]
"""

import asyncio
import logging
import re
import sys
from pathlib import Path

# Setup path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from services.knowledge_base.ingest import ingest_text
from services.knowledge_base.store import KnowledgeStore

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent.parent.parent
OLEG_DIR = ROOT / "agents" / "oleg"
DOCS_DIR = ROOT / "docs"

# ---------------------------------------------------------------------------
# Knowledge files to ingest
# ---------------------------------------------------------------------------
# Each entry: path, file_name (KB key), module, content_type, source_tag, description
#
# source_tag taxonomy:
#   course     — Let's Rock course (8 модулей по WB). Теория маркетплейсов.
#   playbook   — Плейбуки агентов: правила принятия решений, формулы, пороги.
#   reference  — Справочники: метрики, схема БД, качество данных, бизнес-правила.
#   agent_spec — Архитектура системы, спецификации агентов, роли, инструменты.
#   guide      — Гайды по разработке, принципы построения агентов, процессы.
#
KNOWLEDGE_FILES = [
    # =====================================================================
    # PLAYBOOKS — правила принятия решений для агентов
    # Искать когда: нужны формулы, пороговые значения, правила анализа
    # =====================================================================
    {
        "path": OLEG_DIR / "christina_playbook.md",
        "file_name": "playbook_christina_kb_management",
        "module": "special",
        "content_type": "theory",
        "source_tag": "playbook",
        "description": (
            "Плейбук Кристины — управление базой знаний. "
            "Правила добавления/обновления/удаления записей, классификация по модулям, "
            "теги source_tag, проверка дубликатов, верификация контента."
        ),
    },
    {
        "path": OLEG_DIR / "seo_playbook.md",
        "file_name": "playbook_seo_analysis",
        "module": "3",  # Funnel/CTR
        "content_type": "theory",
        "source_tag": "playbook",
        "description": (
            "Плейбук SEO-анализа (Макар). "
            "Метрики WB: медианная позиция, видимость, переходы, конверсии. "
            "Правила анализа на уровне артикулов и моделей. Бенчмарки CTR/CR."
        ),
    },
    {
        "path": DOCS_DIR / "abc_analysis_playbook.md",
        "file_name": "playbook_abc_analysis",
        "module": "6",  # Analytics
        "content_type": "theory",
        "source_tag": "playbook",
        "description": (
            "ABC-анализ продуктов Wookiee. "
            "Иерархия: бренд → модель → артикул/SKU. "
            "Маппинг model_kod ↔ model_osnova (Vuki, Moon, Ruby, Joy, Set). "
            "Классификация A/B/C по маржинальной прибыли и обороту."
        ),
    },
    # =====================================================================
    # REFERENCE — справочники, метрики, схемы, качество данных
    # Искать когда: нужны формулы KPI, значение колонок, известные баги данных
    # =====================================================================
    {
        "path": DOCS_DIR / "database" / "rules.md",
        "file_name": "business_rules_core",
        "module": "6",  # Analytics
        "content_type": "theory",
        "source_tag": "reference",
        "description": (
            "Основные бизнес-правила Wookiee. "
            "5 рычагов маржи (цена до СПП, СПП%, ДРР, логистика, себестоимость). "
            "Правила ежедневного управления ценами. Еженедельный пересмотр ABC. "
            "Пороговые решения: когда снижать/повышать цену, управление рекламой."
        ),
    },
    {
        "path": DOCS_DIR / "database" / "DB_METRICS_GUIDE.md",
        "file_name": "metrics_guide_comprehensive",
        "module": "2",  # Unit economics
        "content_type": "theory",
        "source_tag": "reference",
        "description": (
            "Полный справочник метрик и KPI (76 KB). "
            "Определения и формулы: маржа, маржа%, выручка, средний чек, ДРР, ROMI, "
            "логистика, себестоимость, СПП%, процент выкупа, конверсии воронки, "
            "оборачиваемость, косвенные расходы. "
            "Правила расчёта: дневные, недельные, месячные."
        ),
    },
    {
        "path": DOCS_DIR / "database" / "DATA_QUALITY_NOTES.md",
        "file_name": "data_quality_notes",
        "module": "6",  # Analytics
        "content_type": "theory",
        "source_tag": "reference",
        "description": (
            "Известные проблемы качества данных. "
            "Пробелы в данных WB/OZON, расхождения между API и реальностью, "
            "лаг выкупа 3-21 дней, особенности расчёта СПП, "
            "предупреждения при интерпретации метрик."
        ),
    },
    {
        "path": DOCS_DIR / "database" / "DATABASE_REFERENCE.md",
        "file_name": "database_schema_reference",
        "module": "6",  # Analytics
        "content_type": "theory",
        "source_tag": "reference",
        "description": (
            "Схема базы данных (63 KB). "
            "Таблицы pbi_wb_wookiee и pbi_ozon_wookiee: все колонки с описаниями. "
            "Маппинг юридических лиц (ИП vs ООО). "
            "SQL-паттерны для запросов к данным маркетплейсов."
        ),
    },
    # =====================================================================
    # AGENT_SPEC — архитектура системы и спецификации агентов
    # Искать когда: нужно понять роль агента, его инструменты, ограничения
    # =====================================================================
    {
        "path": OLEG_DIR / "SYSTEM.md",
        "file_name": "system_oleg_architecture",
        "module": "special",
        "content_type": "theory",
        "source_tag": "agent_spec",
        "description": (
            "Архитектура Oleg v2 — мульти-агентная система. "
            "Роли суб-агентов: Reporter (финансы), Researcher (гипотезы), "
            "Quality (верификация), Marketer (реклама), Funnel (воронка), "
            "Christina (KB). Оркестрация, ReAct loop, лимиты итераций."
        ),
    },
    {
        "path": OLEG_DIR / "agents" / "reporter" / "AGENT_SPEC.md",
        "file_name": "agent_spec_reporter",
        "module": "6",  # Analytics
        "content_type": "theory",
        "source_tag": "agent_spec",
        "description": (
            "Спецификация Reporter-агента. "
            "30 инструментов: 12 финансовых + 18 ценовых. "
            "Источники данных, правила поведения, формат ответов."
        ),
    },
    {
        "path": OLEG_DIR / "agents" / "researcher" / "AGENT_SPEC.md",
        "file_name": "agent_spec_researcher",
        "module": "6",  # Analytics
        "content_type": "theory",
        "source_tag": "agent_spec",
        "description": (
            "Спецификация Researcher-агента. "
            "Гипотезно-ориентированное исследование. 10 инструментов "
            "(WB/OZON API, МойСклад, корреляционный анализ). "
            "Фреймворк 5 рычагов маржи."
        ),
    },
    {
        "path": OLEG_DIR / "agents" / "quality" / "AGENT_SPEC.md",
        "file_name": "agent_spec_quality",
        "module": "special",
        "content_type": "theory",
        "source_tag": "agent_spec",
        "description": (
            "Спецификация Quality-агента. "
            "Обработка обратной связи, верификация утверждений в отчётах, "
            "обновление плейбуков на основе данных. 5 инструментов проверки."
        ),
    },
    # =====================================================================
    # PLAYBOOKS (продолжение) — ETL и процессы
    # =====================================================================
    {
        "path": ROOT / "agents" / "ibrahim" / "playbook.md",
        "file_name": "playbook_ibrahim_etl",
        "module": "special",
        "content_type": "theory",
        "source_tag": "playbook",
        "description": (
            "Плейбук Ибрагима (ETL-инженер). "
            "Правила синхронизации данных WB/OZON через API. "
            "Контроль качества данных, reconciliation, управление схемой БД. "
            "Расписание и приоритеты синхронизации."
        ),
    },
    # =====================================================================
    # GUIDE — гайды по разработке и принципам
    # Искать когда: нужны паттерны проектирования агентов, архитектурные решения
    # =====================================================================
    {
        "path": DOCS_DIR / "guides" / "agent-principles.md",
        "file_name": "guide_agent_principles",
        "module": "special",
        "content_type": "theory",
        "source_tag": "guide",
        "description": (
            "Принципы разработки AI-агентов Wookiee (41 KB). "
            "Паттерны проектирования: ReAct loop, tool hardening, error recovery. "
            "Лучшие практики: промпт-инжиниринг, управление контекстом, "
            "обработка ошибок, идемпотентность."
        ),
    },
    {
        "path": DOCS_DIR / "agents" / "analytics-engine.md",
        "file_name": "guide_analytics_engine",
        "module": "6",  # Analytics
        "content_type": "theory",
        "source_tag": "guide",
        "description": (
            "Архитектура аналитического движка. "
            "Оркестрация агентов, потоки данных, интеграция с Notion и Telegram."
        ),
    },
]

# Sections to SKIP (formatting templates, not domain knowledge)
SKIP_PATTERNS = [
    r"## СТРУКТУРА detailed_report",
    r"## Формат ответа",
    r"## telegram_summary",
    r"## brief_summary",
    r"## detailed_report",
    r"### \d+\) ",
    r"ASCII-визуализация",
]


def _extract_domain_knowledge(text: str) -> str:
    """Extract domain knowledge sections, skip formatting templates."""
    lines = text.split("\n")
    result_lines = []
    skip_until_next_heading = False

    for line in lines:
        if any(re.search(pat, line) for pat in SKIP_PATTERNS):
            skip_until_next_heading = True
            continue

        if line.startswith("## ") and skip_until_next_heading:
            if not any(re.search(pat, line) for pat in SKIP_PATTERNS):
                skip_until_next_heading = False

        if not skip_until_next_heading:
            result_lines.append(line)

    return "\n".join(result_lines).strip()


async def ingest_knowledge(force: bool = False):
    """Ingest all knowledge files into KB."""
    store = KnowledgeStore()
    existing = store.get_ingested_files()
    total_chunks = 0
    skipped = 0
    errors = 0

    for entry in KNOWLEDGE_FILES:
        path = entry["path"]
        file_name = entry["file_name"]

        if not path.exists():
            logger.warning("File not found, skipping: %s", path)
            errors += 1
            continue

        if not force and file_name in existing:
            logger.info("Already ingested, skipping: %s", file_name)
            skipped += 1
            continue

        logger.info("Processing: %s → %s", path.name, file_name)

        raw_text = path.read_text(encoding="utf-8")
        domain_text = _extract_domain_knowledge(raw_text)

        if len(domain_text) < 50:
            logger.warning("Too little content from %s (%d chars), skipping",
                           path.name, len(domain_text))
            errors += 1
            continue

        # Delete old chunks if force
        if force:
            deleted = store.delete_by_file(file_name)
            if deleted:
                logger.info("Deleted %d old chunks for %s", deleted, file_name)

        try:
            chunks = await ingest_text(
                text=domain_text,
                file_name=file_name,
                module=entry["module"],
                content_type=entry["content_type"],
                source_tag=entry["source_tag"],
            )

            if chunks > 0:
                store.mark_verified(file_name, verified=True)

            total_chunks += chunks
            logger.info("Ingested %s: %d chunks (module=%s)", file_name, chunks, entry["module"])

        except Exception as e:
            logger.error("Failed to ingest %s: %s", file_name, e)
            errors += 1
            # Cooldown on rate limit
            if "429" in str(e) or "retries" in str(e).lower():
                logger.info("Rate limit — waiting 120s...")
                await asyncio.sleep(120)

    logger.info("=" * 60)
    logger.info("KNOWLEDGE INGESTION COMPLETE")
    logger.info("  Ingested: %d files, %d chunks", len(KNOWLEDGE_FILES) - skipped - errors, total_chunks)
    logger.info("  Skipped:  %d (already in KB)", skipped)
    logger.info("  Errors:   %d", errors)
    logger.info("=" * 60)

    stats = store.get_detailed_stats()
    logger.info("KB stats: %s", stats)

    return total_chunks


if __name__ == "__main__":
    force = "--force" in sys.argv
    asyncio.run(ingest_knowledge(force=force))
