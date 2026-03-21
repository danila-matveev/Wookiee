"""KB pattern loader: load/save patterns from Supabase kb_patterns table."""

import logging
import os

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

from shared.config import SUPABASE_ENV_PATH

logger = logging.getLogger(__name__)

__all__ = ["load_kb_patterns", "save_proposed_patterns"]


def _get_supabase_conn():
    if os.path.exists(SUPABASE_ENV_PATH):
        load_dotenv(SUPABASE_ENV_PATH)

    supabase_config = {
        'host': os.getenv('POSTGRES_HOST', 'aws-0-eu-central-1.pooler.supabase.com'),
        'port': int(os.getenv('POSTGRES_PORT', 6543)),
        'database': os.getenv('POSTGRES_DB', 'postgres'),
        'user': os.getenv('POSTGRES_USER', 'postgres'),
        'password': os.getenv('POSTGRES_PASSWORD', ''),
    }
    return psycopg2.connect(**supabase_config)


def load_kb_patterns(verified_only: bool = True) -> list[dict]:
    """Load patterns from kb_patterns table.

    Args:
        verified_only: if True, only return rows where verified=true.

    Returns:
        List of pattern dicts, or [] on any error.
    """
    try:
        conn = _get_supabase_conn()
        cur = conn.cursor()

        if verified_only:
            cur.execute(
                """
                SELECT pattern_name, description, category, source_tag,
                       trigger_condition, severity, action_hint
                FROM public.kb_patterns
                WHERE verified = TRUE
                ORDER BY pattern_name
                """
            )
        else:
            cur.execute(
                """
                SELECT pattern_name, description, category, source_tag,
                       trigger_condition, severity, action_hint
                FROM public.kb_patterns
                ORDER BY pattern_name
                """
            )

        rows = cur.fetchall()
        cur.close()
        conn.close()

        patterns = []
        for row in rows:
            pattern_name, description, category, source_tag, trigger_condition, severity, action_hint = row
            patterns.append({
                "name": pattern_name,
                "description": description,
                "category": category,
                "source_tag": source_tag,
                "trigger_condition": trigger_condition,
                "severity": severity,
                "hint_template": action_hint,
            })

        return patterns

    except Exception as exc:
        logger.warning("kb_patterns: failed to load patterns: %s", exc)
        return []


def save_proposed_patterns(patterns: list[dict]) -> int:
    """Insert proposed patterns with verified=false, created_by='advisor'.

    Upserts by pattern_name — existing patterns are skipped (ON CONFLICT DO NOTHING).

    Args:
        patterns: list of dicts with keys matching kb_patterns columns.

    Returns:
        Number of rows actually inserted, or 0 on error.
    """
    if not patterns:
        return 0

    try:
        conn = _get_supabase_conn()
        cur = conn.cursor()

        inserted = 0
        for p in patterns:
            cur.execute(
                """
                INSERT INTO public.kb_patterns
                    (pattern_name, description, category, source_tag,
                     trigger_condition, severity, action_hint,
                     impact_on, verified, confidence)
                VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s, %s, FALSE, %s)
                ON CONFLICT (pattern_name) DO NOTHING
                """,
                (
                    p.get("name") or p.get("pattern_name"),
                    p.get("description", ""),
                    p.get("category", "other"),
                    p.get("source_tag", "advisor"),
                    psycopg2.extras.Json(p["trigger_condition"]) if "trigger_condition" in p else "{}",
                    p.get("severity", "warning"),
                    p.get("hint_template") or p.get("action_hint", ""),
                    p.get("impact_on", "both"),
                    p.get("confidence", "medium"),
                ),
            )
            inserted += cur.rowcount

        conn.commit()
        cur.close()
        conn.close()

        return inserted

    except Exception as exc:
        logger.warning("kb_patterns: failed to save proposed patterns: %s", exc)
        return 0
