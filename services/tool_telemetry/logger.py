"""Observability logger for agent and orchestrator runs.

Uses psycopg2 directly (no supabase client). All logging functions are
fire-and-forget — they never raise exceptions.
"""
import asyncio
import logging
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# DB connection configuration (lazy — not connected on import)
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(PROJECT_ROOT / ".env")

_POSTGRES_HOST: str = os.getenv("POSTGRES_HOST", os.getenv("SUPABASE_HOST", "localhost"))
_POSTGRES_PORT: int = int(os.getenv("POSTGRES_PORT", os.getenv("SUPABASE_PORT", "5432")))
_POSTGRES_DB: str = os.getenv("POSTGRES_DB", os.getenv("SUPABASE_DB", "postgres"))
_POSTGRES_USER: str = os.getenv("POSTGRES_USER", os.getenv("SUPABASE_USER", "postgres"))
_POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", os.getenv("SUPABASE_PASSWORD", ""))


def _make_conn_params() -> dict:
    host = _POSTGRES_HOST
    return {
        "host": host,
        "port": _POSTGRES_PORT,
        "dbname": _POSTGRES_DB,
        "user": _POSTGRES_USER,
        "password": _POSTGRES_PASSWORD,
        "sslmode": (
            "require"
            if "supabase" in host.lower() or "pooler" in host.lower()
            else "prefer"
        ),
    }


def _get_conn():
    """Create a new psycopg2 connection."""
    return psycopg2.connect(**_make_conn_params())


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

_MAX_TEXT = 2000


def _trunc(value: Optional[str], limit: int = _MAX_TEXT) -> Optional[str]:
    if value is None:
        return None
    return value[:limit] if len(value) > limit else value


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def new_run_id() -> str:
    """Generate a new UUID string for a run."""
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Sync helpers (called via asyncio.to_thread)
# ---------------------------------------------------------------------------


def _insert_agent_run(
    run_id: str,
    agent_name: str,
    agent_type: str,
    agent_version: str,
    status: str,
    started_at: datetime,
    finished_at: Optional[datetime] = None,
    duration_ms: Optional[int] = None,
    error_message: Optional[str] = None,
    model: Optional[str] = None,
    prompt_tokens: Optional[int] = None,
    completion_tokens: Optional[int] = None,
    total_tokens: Optional[int] = None,
    cost_usd: Optional[float] = None,
    llm_calls: Optional[int] = None,
    tool_calls: Optional[int] = None,
    system_prompt_hash: Optional[str] = None,
    user_input: Optional[str] = None,
    output_summary: Optional[str] = None,
    artifact: Optional[Any] = None,
    task_type: Optional[str] = None,
    trigger: Optional[str] = None,
    parent_run_id: Optional[str] = None,
) -> None:
    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO agent_runs (
                run_id, agent_name, agent_type, agent_version, status,
                started_at, finished_at, duration_ms, error_message,
                model, prompt_tokens, completion_tokens, total_tokens,
                cost_usd, llm_calls, tool_calls, system_prompt_hash,
                user_input, output_summary, artifact, task_type,
                trigger, parent_run_id
            ) VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s
            )
            """,
            (
                run_id,
                agent_name,
                agent_type,
                agent_version,
                status,
                started_at,
                finished_at,
                duration_ms,
                _trunc(error_message),
                model,
                prompt_tokens,
                completion_tokens,
                total_tokens,
                cost_usd,
                llm_calls,
                tool_calls,
                system_prompt_hash,
                _trunc(user_input),
                _trunc(output_summary),
                psycopg2.extras.Json(artifact) if artifact is not None else None,
                task_type,
                trigger,
                parent_run_id,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def _insert_orchestrator_run(
    run_id: str,
    orchestrator: str,
    orchestrator_version: str,
    task_type: str,
    trigger: str,
    status: str,
    started_at: datetime,
    agents_called: int,
    agents_succeeded: int,
    agents_failed: int,
    total_tokens: int,
    total_cost_usd: float,
    finished_at: Optional[datetime] = None,
    duration_ms: Optional[int] = None,
    report_format: Optional[str] = None,
    delivered_to: Optional[str] = None,
) -> None:
    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO orchestrator_runs (
                run_id, orchestrator, orchestrator_version, task_type, trigger,
                status, started_at, finished_at, duration_ms,
                agents_called, agents_succeeded, agents_failed,
                total_tokens, total_cost_usd, report_format, delivered_to
            ) VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s, %s
            )
            ON CONFLICT (run_id) DO NOTHING
            """,
            (
                run_id,
                orchestrator,
                orchestrator_version,
                task_type,
                trigger,
                status,
                started_at,
                finished_at,
                duration_ms,
                agents_called,
                agents_succeeded,
                agents_failed,
                total_tokens,
                total_cost_usd,
                report_format,
                delivered_to,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def _upsert_agent_registry(
    agent_name: str,
    agent_type: str,
    version: str,
    system_prompt: str,
    prompt_hash: str,
    md_file_path: Optional[str] = None,
    mcp_tools: Optional[list] = None,
    model_tier: Optional[str] = None,
    default_model: Optional[str] = None,
    description: Optional[str] = None,
    changelog: Optional[str] = None,
    created_by: Optional[str] = None,
) -> None:
    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO agent_registry (
                agent_name, agent_type, version, system_prompt, prompt_hash,
                md_file_path, mcp_tools, model_tier, default_model,
                description, changelog, created_by
            ) VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s
            )
            ON CONFLICT (agent_name, version) DO NOTHING
            """,
            (
                agent_name,
                agent_type,
                version,
                system_prompt,
                prompt_hash,
                md_file_path,
                mcp_tools,  # TEXT[] — pass as Python list, psycopg2 handles it
                model_tier,
                default_model,
                description,
                changelog,
                created_by,
            ),
        )
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Public async API
# ---------------------------------------------------------------------------


async def log_agent_run(
    run_id: str,
    agent_name: str,
    agent_type: str,
    agent_version: str,
    status: str,
    started_at: datetime,
    finished_at: Optional[datetime] = None,
    duration_ms: Optional[int] = None,
    error_message: Optional[str] = None,
    model: Optional[str] = None,
    prompt_tokens: Optional[int] = None,
    completion_tokens: Optional[int] = None,
    total_tokens: Optional[int] = None,
    cost_usd: Optional[float] = None,
    llm_calls: Optional[int] = None,
    tool_calls: Optional[int] = None,
    system_prompt_hash: Optional[str] = None,
    user_input: Optional[str] = None,
    output_summary: Optional[str] = None,
    artifact: Optional[Any] = None,
    task_type: Optional[str] = None,
    trigger: Optional[str] = None,
    parent_run_id: Optional[str] = None,
) -> None:
    """Deprecated: agent_runs table is no longer actively used.

    Writes disabled 2026-04-13 (audit remediation).
    Table preserved in infra schema for historical data.
    """
    return


async def log_orchestrator_run(
    run_id: str,
    orchestrator: str,
    orchestrator_version: str,
    task_type: str,
    trigger: str,
    status: str,
    started_at: datetime,
    agents_called: int,
    agents_succeeded: int,
    agents_failed: int,
    total_tokens: int,
    total_cost_usd: float,
    finished_at: Optional[datetime] = None,
    duration_ms: Optional[int] = None,
    report_format: Optional[str] = None,
    delivered_to: Optional[str] = None,
) -> None:
    """Deprecated: orchestrator_runs table is no longer actively used.

    Writes disabled 2026-04-13 (audit remediation).
    Table preserved in infra schema for historical data.
    """
    return


async def register_agent_version(
    agent_name: str,
    agent_type: str,
    version: str,
    system_prompt: str,
    prompt_hash: str,
    md_file_path: Optional[str] = None,
    mcp_tools: Optional[list] = None,
    model_tier: Optional[str] = None,
    default_model: Optional[str] = None,
    description: Optional[str] = None,
    changelog: Optional[str] = None,
    created_by: Optional[str] = None,
) -> None:
    """Insert to agent_registry if version doesn't exist. Never raises."""
    try:
        await asyncio.to_thread(
            _upsert_agent_registry,
            agent_name=agent_name,
            agent_type=agent_type,
            version=version,
            system_prompt=system_prompt,
            prompt_hash=prompt_hash,
            md_file_path=md_file_path,
            mcp_tools=mcp_tools,
            model_tier=model_tier,
            default_model=default_model,
            description=description,
            changelog=changelog,
            created_by=created_by,
        )
    except Exception as exc:
        logger.warning(
            "register_agent_version failed (agent=%s version=%s): %s",
            agent_name,
            version,
            exc,
        )
