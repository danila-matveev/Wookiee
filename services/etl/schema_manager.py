"""
Schema Manager — LLM-powered schema evolution for managed DB.

Compares managed vs read-only schemas, proposes improvements,
generates SQL migrations (not auto-applied).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

from services.marketplace_etl.config.database import (
    get_db_connection,
    get_source_db_connection,
    SOURCE_DB_WB,
    SOURCE_DB_OZON,
)

logger = logging.getLogger(__name__)

# Default proposals directory (relative to project root)
_DEFAULT_PROPOSALS_DIR = Path("services/etl/data/schema_proposals")

SCHEMA_ANALYSIS_PROMPT = """Ты — дата-инженер, анализирующий схему PostgreSQL БД.

Схема managed БД (наша, управляемая):
{managed_schema}

Схема source БД (read-only, подрядчик):
{source_schema}

Задачи:
1. Сравни схемы — найди расхождения (новые/отсутствующие колонки, разные типы)
2. Предложи улучшения для managed БД (индексы, нормализация, новые поля)
3. Сгенерируй SQL-миграции для каждого предложения
4. Каждая миграция должна быть безопасной (IF NOT EXISTS, NULLABLE для новых колонок)

Формат ответа — JSON:
{{
    "discrepancies": [
        {{"table": "...", "issue": "...", "severity": "high|medium|low"}}
    ],
    "proposals": [
        {{
            "name": "short_name",
            "description": "...",
            "priority": "high|medium|low",
            "sql": "ALTER TABLE ..."
        }}
    ],
    "summary": "..."
}}"""


def _get_schema_info(conn, schemas: list[str]) -> str:
    """Extract schema information from a database connection."""
    lines = []
    with conn.cursor() as cur:
        for schema in schemas:
            cur.execute(
                "SELECT table_name, column_name, data_type, is_nullable, "
                "column_default "
                "FROM information_schema.columns "
                "WHERE table_schema = %s "
                "ORDER BY table_name, ordinal_position",
                (schema,),
            )
            rows = cur.fetchall()
            current_table = None
            for table, col, dtype, nullable, default in rows:
                fqn = f"{schema}.{table}"
                if fqn != current_table:
                    lines.append(f"\n{fqn}:")
                    current_table = fqn
                null_str = "" if nullable == "YES" else " NOT NULL"
                def_str = f" DEFAULT {default}" if default else ""
                lines.append(f"  {col} {dtype}{null_str}{def_str}")

            # Indexes
            cur.execute(
                "SELECT indexname, indexdef FROM pg_indexes "
                "WHERE schemaname = %s",
                (schema,),
            )
            idx_rows = cur.fetchall()
            if idx_rows:
                lines.append(f"\nIndexes ({schema}):")
                for name, defn in idx_rows:
                    lines.append(f"  {defn}")

    return "\n".join(lines)


class SchemaManager:
    """Analyzes and evolves the managed DB schema using LLM."""

    def __init__(self, proposals_dir: Path | None = None):
        self.proposals_dir = proposals_dir or _DEFAULT_PROPOSALS_DIR
        self.proposals_dir.mkdir(parents=True, exist_ok=True)

    def compare_schemas(self) -> dict:
        """Compare managed and source DB schemas."""
        result = {}

        try:
            managed_conn = get_db_connection()
            result["managed"] = _get_schema_info(managed_conn, ["wb", "ozon"])
            managed_conn.close()
        except Exception as e:
            result["managed"] = f"Error: {e}"
            logger.error("Failed to get managed schema: %s", e)

        try:
            source_wb = get_source_db_connection(SOURCE_DB_WB)
            source_ozon = get_source_db_connection(SOURCE_DB_OZON)
            wb_info = _get_schema_info(source_wb, ["public"])
            ozon_info = _get_schema_info(source_ozon, ["public"])
            result["source"] = f"--- WB (pbi_wb_wookiee) ---\n{wb_info}\n\n--- OZON (pbi_ozon_wookiee) ---\n{ozon_info}"
            source_wb.close()
            source_ozon.close()
        except Exception as e:
            result["source"] = f"Error: {e}"
            logger.warning("Cannot connect to source DBs: %s", e)

        return result

    async def analyze(self, llm_client=None) -> dict:
        """Run full schema analysis with LLM."""
        schemas = self.compare_schemas()

        if llm_client is None:
            logger.warning("No LLM client provided, returning raw schemas")
            return {"status": "skipped", "schemas": schemas}

        prompt = SCHEMA_ANALYSIS_PROMPT.format(
            managed_schema=schemas.get("managed", "N/A"),
            source_schema=schemas.get("source", "N/A"),
        )

        response = await llm_client.complete(
            messages=[
                {"role": "system", "content": "Respond in JSON only."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=4000,
        )

        content = response.get("content", "")
        if not content:
            return {"error": response.get("error", "empty response")}

        try:
            text = content.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1]
                text = text.rsplit("```", 1)[0]
            result = json.loads(text)
        except json.JSONDecodeError:
            logger.warning("Could not parse LLM schema analysis as JSON")
            result = {"raw_response": content}

        # Save proposals as SQL files
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        for proposal in result.get("proposals", []):
            name = proposal.get("name", "unnamed").replace(" ", "_")
            sql = proposal.get("sql", "")
            if sql:
                path = self.proposals_dir / f"{timestamp}_{name}.sql"
                path.write_text(
                    f"-- {proposal.get('description', '')}\n"
                    f"-- Priority: {proposal.get('priority', 'unknown')}\n"
                    f"-- Generated: {timestamp}\n"
                    f"-- !! REVIEW BEFORE APPLYING !!\n\n"
                    f"{sql}\n"
                )
                logger.info("Schema proposal saved: %s", path.name)

        result["timestamp"] = timestamp
        return result
