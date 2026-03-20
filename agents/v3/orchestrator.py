"""Oleg v3 — Analytics Orchestrator.

LangGraph StateGraph that coordinates micro-agents for daily/weekly reports.
Replaces the monolithic OlegOrchestrator from v2.
"""
import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Optional, TypedDict

from agents.v3 import config
from agents.v3.runner import run_agent
from services.observability.logger import log_orchestrator_run, new_run_id

logger = logging.getLogger(__name__)


# ── State ────────────────────────────────────────────────────────────────

class OlegState(TypedDict):
    """Shared state for Oleg orchestrator graph."""
    task_type: str  # "daily_report" | "weekly_report" | "ad_hoc"
    date_from: str
    date_to: str
    comparison_from: str
    comparison_to: str
    channel: str  # "both" | "wb" | "ozon"
    trigger: str  # "cron" | "user_telegram" | "user_cli" | "manual"
    run_id: str

    # Accumulated artifacts from micro-agents
    artifacts: dict[str, Any]  # agent_name -> result dict from run_agent

    # Final output
    report: Optional[dict]  # From report-compiler

    # Status tracking
    agents_called: int
    agents_succeeded: int
    agents_failed: int
    total_duration_ms: int


# ── Orchestrator ─────────────────────────────────────────────────────────

async def run_daily_report(
    date_from: str,
    date_to: str,
    comparison_from: str,
    comparison_to: str,
    channel: str = "both",
    trigger: str = "manual",
) -> dict:
    """Run a full daily report through the micro-agent pipeline.

    1. Run margin-analyst, revenue-decomposer, ad-efficiency in parallel
    2. Pass artifacts to report-compiler
    3. Return final report

    Returns:
        {
            "run_id": str,
            "status": "success" | "partial" | "failed",
            "report": {detailed_report, brief_report, telegram_summary},
            "artifacts": {agent_name: result},
            "agents_called": int,
            "agents_succeeded": int,
            "agents_failed": int,
            "duration_ms": int,
        }
    """
    run_id = new_run_id()
    started_at = datetime.now(timezone.utc)
    start_time = time.monotonic()

    task_context = (
        f"Период: {date_from} — {date_to}. "
        f"Сравнение с: {comparison_from} — {comparison_to}. "
        f"Каналы: {channel}."
    )

    # ── Phase 1: Run analytical agents in parallel ──

    analysis_agents = ["margin-analyst", "revenue-decomposer", "ad-efficiency"]

    tasks = [
        run_agent(
            agent_name=agent_name,
            task=f"Проанализируй данные за период. {task_context}",
            parent_run_id=run_id,
            trigger=trigger,
            task_type="daily_report",
        )
        for agent_name in analysis_agents
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    artifacts: dict[str, Any] = {}
    agents_called = len(analysis_agents)
    agents_succeeded = 0
    agents_failed = 0

    for agent_name, result in zip(analysis_agents, results):
        if isinstance(result, Exception):
            logger.error("Agent %s raised exception: %s", agent_name, result)
            artifacts[agent_name] = {
                "agent_name": agent_name,
                "status": "failed",
                "artifact": None,
                "raw_output": str(result),
                "duration_ms": 0,
                "run_id": "",
            }
            agents_failed += 1
        else:
            artifacts[agent_name] = result
            if result["status"] == "success":
                agents_succeeded += 1
            else:
                agents_failed += 1

    # ── Phase 2: Compile report from artifacts ──

    # Build the task for report-compiler with all artifacts
    compiler_input: dict[str, Any] = {
        "period": {"date_from": date_from, "date_to": date_to},
        "comparison_period": {"date_from": comparison_from, "date_to": comparison_to},
        "channel": channel,
        "artifacts": {},
    }

    for name, result in artifacts.items():
        if result["status"] == "success" and result.get("artifact"):
            compiler_input["artifacts"][name] = result["artifact"]
        else:
            compiler_input["artifacts"][name] = {
                "status": "failed",
                "error": result.get("raw_output", "Unknown error")[:500],
            }

    compiler_task = (
        f"Собери аналитический отчёт из следующих артефактов:\n\n"
        f"{json.dumps(compiler_input, ensure_ascii=False, default=str)}"
    )

    agents_called += 1
    compiler_result = await run_agent(
        agent_name="report-compiler",
        task=compiler_task,
        parent_run_id=run_id,
        trigger=trigger,
        task_type="daily_report",
    )

    artifacts["report-compiler"] = compiler_result
    if compiler_result["status"] == "success":
        agents_succeeded += 1
    else:
        agents_failed += 1

    # ── Determine overall status ──

    duration_ms = int((time.monotonic() - start_time) * 1000)

    if agents_failed == 0:
        status = "success"
    elif agents_succeeded > 0:
        status = "partial"
    else:
        status = "failed"

    # ── Log orchestrator run ──

    asyncio.create_task(log_orchestrator_run(
        run_id=run_id,
        orchestrator="oleg",
        orchestrator_version="3.0",
        task_type="daily_report",
        trigger=trigger,
        status=status,
        started_at=started_at,
        finished_at=datetime.now(timezone.utc),
        duration_ms=duration_ms,
        agents_called=agents_called,
        agents_succeeded=agents_succeeded,
        agents_failed=agents_failed,
        total_tokens=0,  # TODO: aggregate from agent results
        total_cost_usd=0.0,
    ))

    return {
        "run_id": run_id,
        "status": status,
        "report": compiler_result.get("artifact"),
        "artifacts": artifacts,
        "agents_called": agents_called,
        "agents_succeeded": agents_succeeded,
        "agents_failed": agents_failed,
        "duration_ms": duration_ms,
    }


async def run_weekly_report(
    date_from: str,
    date_to: str,
    comparison_from: str,
    comparison_to: str,
    channel: str = "both",
    trigger: str = "manual",
) -> dict:
    """Run weekly report — same pipeline as daily but with weekly task type."""
    run_id = new_run_id()
    started_at = datetime.now(timezone.utc)
    start_time = time.monotonic()

    task_context = (
        f"Недельный отчёт. Период: {date_from} — {date_to}. "
        f"Сравнение с: {comparison_from} — {comparison_to}. "
        f"Каналы: {channel}."
    )

    analysis_agents = ["margin-analyst", "revenue-decomposer", "ad-efficiency"]

    tasks = [
        run_agent(
            agent_name=name,
            task=f"Проанализируй данные за неделю. {task_context}",
            parent_run_id=run_id,
            trigger=trigger,
            task_type="weekly_report",
        )
        for name in analysis_agents
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    artifacts: dict[str, Any] = {}
    agents_called = len(analysis_agents)
    agents_succeeded = 0
    agents_failed = 0

    for name, result in zip(analysis_agents, results):
        if isinstance(result, Exception):
            logger.error("Agent %s raised exception: %s", name, result)
            artifacts[name] = {
                "agent_name": name,
                "status": "failed",
                "artifact": None,
                "raw_output": str(result),
                "duration_ms": 0,
                "run_id": "",
            }
            agents_failed += 1
        else:
            artifacts[name] = result
            if result["status"] == "success":
                agents_succeeded += 1
            else:
                agents_failed += 1

    # Compile
    compiler_input: dict[str, Any] = {
        "period": {"date_from": date_from, "date_to": date_to},
        "comparison_period": {"date_from": comparison_from, "date_to": comparison_to},
        "channel": channel,
        "artifacts": {},
    }
    for n, r in artifacts.items():
        if r["status"] == "success" and r.get("artifact"):
            compiler_input["artifacts"][n] = r["artifact"]
        else:
            compiler_input["artifacts"][n] = {
                "status": "failed",
                "error": r.get("raw_output", "Unknown error")[:500],
            }

    agents_called += 1
    compiler_result = await run_agent(
        agent_name="report-compiler",
        task=(
            f"Собери недельный аналитический отчёт:\n\n"
            f"{json.dumps(compiler_input, ensure_ascii=False, default=str)}"
        ),
        parent_run_id=run_id,
        trigger=trigger,
        task_type="weekly_report",
    )
    artifacts["report-compiler"] = compiler_result
    if compiler_result["status"] == "success":
        agents_succeeded += 1
    else:
        agents_failed += 1

    duration_ms = int((time.monotonic() - start_time) * 1000)

    if agents_failed == 0:
        status = "success"
    elif agents_succeeded > 0:
        status = "partial"
    else:
        status = "failed"

    asyncio.create_task(log_orchestrator_run(
        run_id=run_id,
        orchestrator="oleg",
        orchestrator_version="3.0",
        task_type="weekly_report",
        trigger=trigger,
        status=status,
        started_at=started_at,
        finished_at=datetime.now(timezone.utc),
        duration_ms=duration_ms,
        agents_called=agents_called,
        agents_succeeded=agents_succeeded,
        agents_failed=agents_failed,
        total_tokens=0,
        total_cost_usd=0.0,
    ))

    return {
        "run_id": run_id,
        "status": status,
        "report": compiler_result.get("artifact"),
        "artifacts": artifacts,
        "agents_called": agents_called,
        "agents_succeeded": agents_succeeded,
        "agents_failed": agents_failed,
        "duration_ms": duration_ms,
    }
