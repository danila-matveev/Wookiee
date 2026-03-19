#!/usr/bin/env python3
"""
Ingest playbook domain knowledge into the vector KB.

Reads playbook.md, marketing_playbook.md, funnel_playbook.md,
extracts domain knowledge sections (skipping report formatting templates),
and ingests them with source_tag='playbook'.

Usage:
    python -m services.knowledge_base.scripts.ingest_playbooks [--force]
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

OLEG_DIR = Path(__file__).resolve().parent.parent.parent.parent / "agents" / "oleg"

# Playbooks to ingest with their module mappings
PLAYBOOKS = [
    {
        "path": OLEG_DIR / "playbook.md",
        "file_name": "playbook_reporter_rules",
        "module": "6",  # Analytics
        "description": "Reporter playbook — financial analysis rules",
    },
    {
        "path": OLEG_DIR / "marketing_playbook.md",
        "file_name": "playbook_marketing_rules",
        "module": "5",  # Advertising
        "description": "Marketing playbook — funnel and ad analysis rules",
    },
    {
        "path": OLEG_DIR / "funnel_playbook.md",
        "file_name": "playbook_funnel_rules",
        "module": "3",  # Sales funnel
        "description": "Funnel playbook — conversion and CRO rules",
    },
]

# Sections to SKIP (formatting/structure templates, not domain knowledge)
SKIP_PATTERNS = [
    r"## СТРУКТУРА detailed_report",
    r"## Формат ответа",
    r"## telegram_summary",
    r"## brief_summary",
    r"## detailed_report",
    r"### \d+\) ",  # Report section templates like "### 1) Исполнительная сводка"
    r"Таблица:.*\|.*\|",  # Table structure definitions
    r"ASCII-визуализация",
]


def _extract_domain_knowledge(text: str) -> str:
    """Extract domain knowledge sections, skip formatting templates."""
    lines = text.split("\n")
    result_lines = []
    skip_until_next_heading = False

    for line in lines:
        # Check if this heading starts a skip section
        if any(re.search(pat, line) for pat in SKIP_PATTERNS):
            skip_until_next_heading = True
            continue

        # New top-level heading resets skip
        if line.startswith("## ") and skip_until_next_heading:
            if not any(re.search(pat, line) for pat in SKIP_PATTERNS):
                skip_until_next_heading = False

        if not skip_until_next_heading:
            result_lines.append(line)

    return "\n".join(result_lines).strip()


async def ingest_playbooks(force: bool = False):
    """Ingest all playbooks into KB."""
    store = KnowledgeStore()
    total_chunks = 0

    for pb in PLAYBOOKS:
        path = pb["path"]
        file_name = pb["file_name"]

        if not path.exists():
            logger.warning("Playbook not found: %s", path)
            continue

        # Check if already ingested
        if not force:
            existing = store.get_ingested_files()
            if file_name in existing:
                logger.info("Skipping already ingested: %s", file_name)
                continue

        logger.info("Processing: %s → %s", path.name, file_name)

        # Read and extract domain knowledge
        raw_text = path.read_text(encoding="utf-8")
        domain_text = _extract_domain_knowledge(raw_text)

        if len(domain_text) < 100:
            logger.warning("Too little domain knowledge extracted from %s (%d chars), skipping",
                           path.name, len(domain_text))
            continue

        # Delete old if force
        if force:
            deleted = store.delete_by_file(file_name)
            if deleted:
                logger.info("Deleted %d old chunks for %s", deleted, file_name)

        # Ingest
        chunks = await ingest_text(
            text=domain_text,
            file_name=file_name,
            module=pb["module"],
            content_type="theory",
            source_tag="playbook",
        )

        # Mark as verified (playbooks are curated)
        if chunks > 0:
            store.mark_verified(file_name, verified=True)

        total_chunks += chunks
        logger.info("Ingested %s: %d chunks (module=%s)", file_name, chunks, pb["module"])

    logger.info("=" * 60)
    logger.info("PLAYBOOK INGESTION COMPLETE: %d total chunks", total_chunks)
    logger.info("=" * 60)

    # Show updated stats
    stats = store.get_detailed_stats()
    logger.info("KB stats: %s", stats)

    return total_chunks


if __name__ == "__main__":
    force = "--force" in sys.argv
    asyncio.run(ingest_playbooks(force=force))
