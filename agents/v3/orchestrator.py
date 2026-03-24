"""Oleg v3 — Analytics Orchestrator.

LangGraph StateGraph that coordinates micro-agents for daily/weekly/monthly
reports, marketing, funnel, finolog, and price analysis.
Replaces the monolithic OlegOrchestrator from v2.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Optional, TypedDict

from agents.v3 import config
from agents.v3.runner import run_agent
from agents.v3.state import StateStore
from agents.v3.report_formatter import (
    ensure_report_fields as _ensure_report_fields,
    fill_telegram_summary as _fill_telegram_summary,
    COMPILER_FORMAT_INSTRUCTIONS,
)
from services.observability.logger import log_orchestrator_run, new_run_id

logger = logging.getLogger(__name__)


# ── Confidence & cost constants ───────────────────────────────────────────────

FAILED_AGENT_META: dict = {
    "confidence": 0.0,
    "confidence_reason": "агент не выполнился",
    "data_coverage": 0.0,
    "limitations": ["агент завершился с ошибкой"],
    "conclusions": [],
}

AGENT_WEIGHTS: dict[str, float] = {
    "margin-analyst": 1.0,
    "revenue-decomposer": 1.0,
    "ad-efficiency": 1.0,
    "price-strategist": 1.0,
    "pricing-impact-analyst": 0.5,
    "hypothesis-tester": 0.5,
    "anomaly-detector": 0.5,
}


def aggregate_confidence(confidences: dict[str, float]) -> float:
    """Weighted average confidence across agents."""
    if not confidences:
        return 0.0
    total_weight = 0.0
    weighted_sum = 0.0
    for agent_name, conf in confidences.items():
        w = AGENT_WEIGHTS.get(agent_name, 0.5)
        weighted_sum += w * conf
        total_weight += w
    return round(weighted_sum / total_weight, 2) if total_weight > 0 else 0.0


def worst_limitation(artifacts: dict) -> str | None:
    """Return worst limitation string for Telegram footer.

    MUST be called AFTER FAILED_AGENT_META injection for failed agents.
    Missing _meta is treated as confidence=0.0 (worst case).
    Excludes report-compiler (it doesn't produce analytical conclusions).
    """
    candidates = []
    for name, art in artifacts.items():
        if name == "report-compiler":
            continue
        meta = art.get("_meta") or {}
        conf = meta.get("confidence", 0.0)
        if conf < 0.75:
            candidates.append((name, conf))
    if not candidates:
        return None
    name, _ = min(candidates, key=lambda x: x[1])
    meta = (artifacts[name].get("_meta") or {})
    lims = meta.get("limitations", [])
    return f"{name}: {lims[0]}" if lims else None


def load_persistent_instructions(state: StateStore, agent_names: list[str]) -> str:
    """Load active persistent instructions for given agents from StateStore.

    Returns a formatted string to append to task_context, or empty string.
    """
    lines: list[str] = []
    for agent_name in agent_names:
        raw = state.get(f"pi:{agent_name}")
        if not raw:
            continue
        try:
            instructions = json.loads(raw)
            for instr in instructions:
                if instr.get("active", True):
                    lines.append(f"- [{agent_name}] {instr['instruction']}")
        except (json.JSONDecodeError, KeyError, TypeError):
            continue

    if not lines:
        return ""

    return (
        "\n\n\u041f\u041e\u0421\u0422\u041e\u042f\u041d\u041d\u042b\u0415 \u0418\u041d\u0421\u0422\u0420\u0423\u041a\u0426\u0418\u0418 (\u0438\u0437 \u043e\u0431\u0440\u0430\u0442\u043d\u043e\u0439 \u0441\u0432\u044f\u0437\u0438 \u043a\u043e\u043c\u0430\u043d\u0434\u044b, \u0434\u0435\u0439\u0441\u0442\u0432\u0443\u044e\u0442 \u0434\u043e \u043e\u0442\u043c\u0435\u043d\u044b):\n"
        + "\n".join(lines)
        + "\n\u0421\u0442\u0440\u043e\u0433\u043e \u0441\u043e\u0431\u043b\u044e\u0434\u0430\u0439 \u044d\u0442\u0438 \u0438\u043d\u0441\u0442\u0440\u0443\u043a\u0446\u0438\u0438.\n"
    )


def _ensure_report_fields_legacy(report: dict) -> dict:
    """[DEPRECATED — replaced by agents.v3.report_formatter.ensure_report_fields]"""
    if not report or not isinstance(report, dict):
        return report

    # Skip if detailed_report already exists AND is substantial (>= 3000 chars)
    existing = report.get("detailed_report", "")
    if existing and len(existing) >= 3000:
        return report

    # Flatten nested report key — some models wrap data inside daily_report/weekly_report/etc.
    _REPORT_KEYS = {
        "daily_report", "weekly_report", "monthly_report",
        "marketing_weekly", "marketing_monthly", "marketing_daily",
        "funnel_weekly", "price_analysis", "finolog_weekly",
    }
    for rk in _REPORT_KEYS:
        nested = report.get(rk)
        if isinstance(nested, dict):
            for k, v in nested.items():
                if k not in report or not report[k]:
                    report[k] = v
            break

    lines: list[str] = []

    # Meta / passport
    meta = report.get("meta", {})
    if meta:
        lines.append("## ▶ 0. Паспорт")
        if meta.get("period"):
            p = meta["period"]
            if isinstance(p, dict):
                lines.append(f"**Период:** {p.get('current', '')} vs {p.get('previous', '')}")
            else:
                lines.append(f"**Период:** {p}")
        if meta.get("channels"):
            lines.append(f"**Каналы:** {', '.join(meta['channels']) if isinstance(meta['channels'], list) else meta['channels']}")
        if meta.get("confidence"):
            conf = meta["confidence"]
            marker = "🟢" if conf >= 0.75 else ("🟡" if conf >= 0.45 else "🔴")
            lines.append(f"**Достоверность:** {marker} {conf}")
        if meta.get("limitations"):
            lines.append("\n**Ограничения:**")
            for lim in meta["limitations"]:
                lines.append(f"- {lim}")
        lines.append("")

    # Executive summary
    es = report.get("executive_summary", {})
    if es:
        lines.append("## ▶ 1. Ключевые выводы")
        if es.get("headline"):
            lines.append(f"**{es['headline']}**\n")
        for insight in es.get("key_insights", []):
            lines.append(f"- {insight}")
        lines.append("")

    # Generic section renderer
    def _render_section(key: str, title: str, section_num: int):
        data = report.get(key)
        if not data:
            return
        lines.append(f"## ▶ {section_num}. {title}")
        if isinstance(data, str):
            lines.append(data)
        elif isinstance(data, dict):
            _render_dict(data)
        elif isinstance(data, list):
            _render_list(data)
        lines.append("")

    def _render_dict(d: dict, indent: int = 0):
        prefix = "  " * indent
        for k, v in d.items():
            if k.startswith("_"):
                continue
            if isinstance(v, dict):
                lines.append(f"{prefix}**{k}:**")
                _render_dict(v, indent + 1)
            elif isinstance(v, list):
                lines.append(f"{prefix}**{k}:**")
                _render_list(v, indent + 1)
            else:
                lines.append(f"{prefix}**{k}:** {v}")

    def _render_list(lst: list, indent: int = 0):
        prefix = "  " * indent
        for item in lst:
            if isinstance(item, dict):
                # Try to render as table row or key-value
                parts = [f"{k}: {v}" for k, v in item.items() if not str(k).startswith("_")]
                lines.append(f"{prefix}- {' | '.join(parts)}")
            else:
                lines.append(f"{prefix}- {item}")

    # Render remaining sections — covers financial, marketing, funnel, price report types
    section_map = [
        # Financial
        ("plan_fact", "План-Факт", 2),
        ("plan_vs_fact", "План-Факт", 2),
        ("financial_performance", "Ключевые изменения", 3),
        ("key_changes", "Ключевые изменения", 3),
        ("revenue_and_orders_analysis", "Выручка и заказы", 3),
        ("pricing_strategy", "Ценовая стратегия и СПП", 4),
        ("margin_waterfall", "Каскад маржинальности", 5),
        ("margin_cascade", "Каскад маржинальности", 5),
        ("margin_analysis", "Каскад маржинальности", 5),
        ("channel_analysis", "Площадки", 6),
        ("channels", "Площадки", 6),
        ("channels_overview", "Площадки", 6),
        ("product_analysis", "Модели", 6),
        ("drivers_antidrivers", "Драйверы и антидрайверы", 7),
        ("drivers", "Драйверы и антидрайверы", 7),
        ("model_performance", "Модели", 6),
        ("metrics", "Ключевые метрики", 3),
        ("advertising_efficiency", "Реклама", 7),
        ("advertising_efficiency_analysis", "Реклама", 7),
        ("ad_efficiency", "Реклама", 7),
        ("hypotheses", "Гипотезы → Действия", 8),
        ("operational_metrics", "Операционные метрики", 8),
        ("recommendations", "Рекомендации", 9),
        ("advisor_recommendations", "Рекомендации Advisor", 9),
        ("limitations", "Ограничения данных", 0),
        ("summary", "Сводка", 10),
        # Marketing
        ("campaign_data", "Рекламные кампании", 2),
        ("campaign_analysis", "Рекламные кампании", 2),
        ("organic_vs_paid", "Органика vs Реклама", 3),
        ("organic_paid_split", "Органика vs Реклама", 3),
        ("funnel_analysis", "Воронка маркетинга", 4),
        ("model_efficiency", "Эффективность по моделям", 5),
        ("ad_efficiency", "Эффективность рекламы", 5),
        ("channel_mix", "Канальный микс", 6),
        # Funnel
        ("brand_funnel", "Воронка бренда", 2),
        ("model_funnels", "Воронки по моделям", 3),
        ("bottleneck", "Узкие места", 4),
        ("bottlenecks", "Узкие места", 4),
        ("keyword_portfolio", "Ключевые слова", 5),
        ("keyword_analysis", "Ключевые слова", 5),
        ("conversion_analysis", "Анализ конверсий", 3),
        # Price
        ("price_matrix", "Ценовая матрица", 2),
        ("price_trends", "Тренды продаж", 3),
        ("sales_trends", "Тренды продаж", 3),
        ("stock_price_matrix", "Матрица остатки-цена", 4),
        ("marketing_impact", "Влияние на маркетинг", 5),
        ("hypothesis_results", "Проверка гипотез", 6),
        ("action_plan", "План действий", 7),
    ]

    rendered_sections = set()
    rendered_keys = set()
    for key, title, num in section_map:
        if key in report and num not in rendered_sections:
            _render_section(key, title, num)
            rendered_sections.add(num)
            rendered_keys.add(key)

    # Render any remaining structured data not covered by section_map
    _SKIP_KEYS = {
        "detailed_report", "telegram_summary", "meta", "executive_summary",
        "report_type", "period", "comparison_period", "channel", "task_type",
        "sections_included", "sections_skipped", "warnings", "_meta",
    }
    next_section = max(rendered_sections, default=10) + 1
    for key, value in report.items():
        if key in rendered_keys or key in _SKIP_KEYS:
            continue
        if key.startswith("_"):
            continue
        if not value:
            continue
        # Convert underscored key to human-readable title
        title = key.replace("_", " ").title()
        _render_section(key, title, next_section)
        rendered_keys.add(key)
        next_section += 1

    detailed = "\n".join(lines)

    # Build telegram summary from executive_summary
    tg_lines = []
    if es:
        if es.get("headline"):
            tg_lines.append(f"[b]{es['headline']}[/b]")
        for insight in es.get("key_insights", [])[:5]:
            tg_lines.append(f"• {insight}")

    report["detailed_report"] = detailed
    report["telegram_summary"] = "\n".join(tg_lines) if tg_lines else ""

    logger.info(
        "Fallback: converted structured JSON to detailed_report (%d chars) + telegram_summary (%d chars)",
        len(detailed), len(report["telegram_summary"]),
    )
    return report


def _fill_telegram_summary_legacy(report: dict) -> None:
    """[DEPRECATED — replaced by agents.v3.report_formatter.fill_telegram_summary]"""
    if not report or not isinstance(report, dict):
        return
    if (report.get("telegram_summary") or "").strip():
        return

    detailed = (report.get("detailed_report") or "").strip()
    if not detailed:
        return

    import re as _re

    # Strip markdown headers, toggle markers, bold markers
    clean = _re.sub(r"^#{1,3}\s+▶?\s*", "", detailed, flags=_re.MULTILINE)
    clean = clean.replace("**", "")

    # Take first non-empty lines up to ~1000 chars
    lines = [ln.strip() for ln in clean.split("\n") if ln.strip()]
    summary_lines: list[str] = []
    total = 0
    for ln in lines:
        if total + len(ln) > 1000:
            break
        # Skip table separator rows
        if _re.match(r"^[\|\-\s:]+$", ln):
            continue
        summary_lines.append(ln)
        total += len(ln)

    summary = "\n".join(summary_lines)
    if summary:
        report["telegram_summary"] = summary
        logger.info("Fallback: generated telegram_summary from detailed_report (%d chars)", len(summary))


# ── State ────────────────────────────────────────────────────────────────────

class OlegState(TypedDict):
    """Shared state for Oleg orchestrator graph."""
    task_type: str  # "daily_report" | "weekly_report" | "monthly_report" | ...
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


# ── Shared pipeline ──────────────────────────────────────────────────────────

async def _run_report_pipeline(
    analysis_agents: list[str],
    task_context: str,
    task_type: str,
    date_from: str,
    date_to: str,
    comparison_from: str,
    comparison_to: str,
    channel: str,
    trigger: str,
    compiler_prompt_prefix: str = "Собери аналитический отчёт",
    prior_artifacts: dict = None,  # NEW: artifacts from previous phase
    skip_compiler: bool = False,   # NEW: skip report-compiler phase
) -> dict:
    """Shared pipeline for all report types.

    1. Run *analysis_agents* in parallel.
    2. Pass their artifacts to report-compiler.
    3. Log via observability and return result dict.

    Returns:
        {
            "run_id": str,
            "status": "success" | "partial" | "failed",
            "report": {detailed_report, telegram_summary},
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

    # ── Load persistent instructions from PromptTuner ────────────────────
    try:
        pi_state = StateStore(config.STATE_DB_PATH)
        pi_note = load_persistent_instructions(pi_state, analysis_agents + ["report-compiler"])
        if pi_note:
            task_context += pi_note
    except Exception as e:
        logger.warning("Failed to load persistent instructions: %s", e)

    # ── Phase 1: Run analytical agents in parallel ──────────────────────────

    # Build artifact context for cross-phase communication
    artifact_context = ""
    if prior_artifacts:
        artifact_context = (
            "\n\nРезультаты предыдущей фазы анализа:\n"
            + json.dumps(prior_artifacts, ensure_ascii=False, default=str)
        )

    tasks = [
        run_agent(
            agent_name=agent_name,
            task=f"Проанализируй данные. {task_context}{artifact_context}",
            parent_run_id=run_id,
            trigger=trigger,
            task_type=task_type,
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

    # Inject FAILED_AGENT_META for failed agents
    for agent_name, result in artifacts.items():
        if result["status"] != "success":
            if not isinstance(result.get("artifact"), dict):
                result["artifact"] = {}
            result["artifact"]["_meta"] = FAILED_AGENT_META.copy()

    # ── Phase 2: Compile report from artifacts (unless skipped) ──────────────

    compiler_result = None
    if not skip_compiler:
        compiler_input: dict[str, Any] = {
            "task_type": task_type,
            "period": {"date_from": date_from, "date_to": date_to},
            "comparison_period": {"date_from": comparison_from, "date_to": comparison_to},
            "channel": channel,
            "artifacts": {},
        }

        for name, result in artifacts.items():
            if result["status"] == "success" and result.get("artifact"):
                compiler_input["artifacts"][name] = result["artifact"]
            else:
                error_msg = result.get("raw_output", "Unknown error")[:500]
                failure_reason = "timeout" if "timeout" in error_msg.lower() else "error"
                compiler_input["artifacts"][name] = {
                    "status": "failed",
                    "failure_reason": failure_reason,
                    "error": error_msg,
                    "_meta": FAILED_AGENT_META,
                }

        compiler_task = (
            f"{compiler_prompt_prefix}:\n"
            f"{COMPILER_FORMAT_INSTRUCTIONS}\n"
            f"Данные:\n{json.dumps(compiler_input, ensure_ascii=False, default=str)}"
        )

        agents_called += 1
        compiler_result = await run_agent(
            agent_name="report-compiler",
            task=compiler_task,
            parent_run_id=run_id,
            trigger=trigger,
            task_type=task_type,
        )

        artifacts["report-compiler"] = compiler_result
        if compiler_result["status"] == "success":
            agents_succeeded += 1
        else:
            agents_failed += 1

    # ── Determine overall status ────────────────────────────────────────────

    duration_ms = int((time.monotonic() - start_time) * 1000)

    if agents_failed == 0:
        status = "success"
    elif agents_succeeded > 0:
        status = "partial"
    else:
        status = "failed"

    # ── Aggregate confidence, limitations, tokens & cost ────────────────────

    # Aggregate confidence (exclude report-compiler)
    confidences = {}
    for name, result in artifacts.items():
        if name == "report-compiler":
            continue
        art = result.get("artifact") if isinstance(result, dict) else result
        meta = (art.get("_meta") or {}) if isinstance(art, dict) else {}
        if "confidence" in meta:
            confidences[name] = meta["confidence"]

    agg_confidence = aggregate_confidence(confidences)

    # Build artifacts view for worst_limitation
    artifacts_for_lim = {}
    for name, result in artifacts.items():
        art = result.get("artifact") if isinstance(result, dict) else result
        artifacts_for_lim[name] = art if isinstance(art, dict) else {}

    worst_lim = worst_limitation(artifacts_for_lim)

    # Aggregate tokens & cost
    total_tokens = sum(r.get("total_tokens", 0) for r in artifacts.values() if isinstance(r, dict))
    total_cost = sum(r.get("cost_usd", 0.0) for r in artifacts.values() if isinstance(r, dict))

    # ── Log orchestrator run ────────────────────────────────────────────────

    asyncio.create_task(log_orchestrator_run(
        run_id=run_id,
        orchestrator="oleg",
        orchestrator_version="3.0",
        task_type=task_type,
        trigger=trigger,
        status=status,
        started_at=started_at,
        finished_at=datetime.now(timezone.utc),
        duration_ms=duration_ms,
        agents_called=agents_called,
        agents_succeeded=agents_succeeded,
        agents_failed=agents_failed,
        total_tokens=total_tokens,
        total_cost_usd=total_cost,
    ))

    # Ensure report has detailed_report + telegram_summary
    raw_artifact = compiler_result.get("artifact") if compiler_result else None
    if isinstance(raw_artifact, str):
        # Compiler returned raw markdown instead of JSON — wrap it
        report_data = {"detailed_report": raw_artifact, "telegram_summary": ""}
    elif isinstance(raw_artifact, dict):
        report_data = raw_artifact
    else:
        report_data = {}

    # Always run deterministic formatter — it checks quality internally
    report_data = _ensure_report_fields(report_data)

    # Fallback: generate telegram_summary from detailed_report if empty
    _fill_telegram_summary(report_data)

    return {
        "run_id": run_id,
        "status": status,
        "report": report_data,
        "artifacts": artifacts,
        "agents_called": agents_called,
        "agents_succeeded": agents_succeeded,
        "agents_failed": agents_failed,
        "duration_ms": duration_ms,
        "aggregate_confidence": agg_confidence,
        "worst_limitation": worst_lim,
        "total_tokens": total_tokens,
        "total_cost_usd": total_cost,
    }


# ── Public report entry points ───────────────────────────────────────────────

async def run_daily_report(
    date_from: str,
    date_to: str,
    comparison_from: str,
    comparison_to: str,
    channel: str = "both",
    trigger: str = "manual",
) -> dict:
    """Run a full daily report through the micro-agent pipeline."""
    task_context = (
        f"Период: {date_from} — {date_to}. "
        f"Сравнение с: {comparison_from} — {comparison_to}. "
        f"Каналы: {channel}."
    )
    return await _run_report_pipeline(
        analysis_agents=["margin-analyst", "revenue-decomposer", "ad-efficiency"],
        task_context=task_context,
        task_type="daily_report",
        date_from=date_from,
        date_to=date_to,
        comparison_from=comparison_from,
        comparison_to=comparison_to,
        channel=channel,
        trigger=trigger,
        compiler_prompt_prefix="Собери аналитический отчёт из следующих артефактов",
    )


async def run_weekly_report(
    date_from: str,
    date_to: str,
    comparison_from: str,
    comparison_to: str,
    channel: str = "both",
    trigger: str = "manual",
) -> dict:
    """Run weekly report — same agent set as daily but weekly task type."""
    task_context = (
        f"Недельный отчёт. Период: {date_from} — {date_to}. "
        f"Сравнение с: {comparison_from} — {comparison_to}. "
        f"Каналы: {channel}."
    )
    return await _run_report_pipeline(
        analysis_agents=["margin-analyst", "revenue-decomposer", "ad-efficiency"],
        task_context=task_context,
        task_type="weekly_report",
        date_from=date_from,
        date_to=date_to,
        comparison_from=comparison_from,
        comparison_to=comparison_to,
        channel=channel,
        trigger=trigger,
        compiler_prompt_prefix="Собери недельный аналитический отчёт",
    )


async def run_monthly_report(
    date_from: str,
    date_to: str,
    comparison_from: str,
    comparison_to: str,
    channel: str = "both",
    trigger: str = "manual",
) -> dict:
    """Run monthly report — same agents as daily/weekly, monthly task type."""
    task_context = (
        f"Месячный отчёт. Период: {date_from} — {date_to}. "
        f"Сравнение с: {comparison_from} — {comparison_to}. "
        f"Каналы: {channel}."
    )
    return await _run_report_pipeline(
        analysis_agents=["margin-analyst", "revenue-decomposer", "ad-efficiency"],
        task_context=task_context,
        task_type="monthly_report",
        date_from=date_from,
        date_to=date_to,
        comparison_from=comparison_from,
        comparison_to=comparison_to,
        channel=channel,
        trigger=trigger,
        compiler_prompt_prefix="Собери месячный аналитический отчёт",
    )


async def run_marketing_report(
    date_from: str,
    date_to: str,
    comparison_from: str,
    comparison_to: str,
    report_period: str = "weekly",
    channel: str = "both",
    trigger: str = "manual",
) -> dict:
    """Run marketing report (weekly or monthly).

    Args:
        report_period: "weekly" or "monthly" — determines task_type.
    """
    _marketing_task_types = {"daily": "marketing_daily", "weekly": "marketing_weekly", "monthly": "marketing_monthly"}
    task_type = _marketing_task_types.get(report_period, "marketing_weekly")
    period_label = "Недельный" if report_period == "weekly" else "Месячный"
    task_context = (
        f"{period_label} маркетинговый отчёт. Период: {date_from} — {date_to}. "
        f"Сравнение с: {comparison_from} — {comparison_to}. "
        f"Каналы: {channel}."
    )
    return await _run_report_pipeline(
        analysis_agents=["campaign-optimizer", "organic-vs-paid", "ad-efficiency"],
        task_context=task_context,
        task_type=task_type,
        date_from=date_from,
        date_to=date_to,
        comparison_from=comparison_from,
        comparison_to=comparison_to,
        channel=channel,
        trigger=trigger,
        compiler_prompt_prefix="Собери маркетинговый отчёт",
    )


async def run_funnel_report(
    date_from: str,
    date_to: str,
    comparison_from: str,
    comparison_to: str,
    channel: str = "both",
    trigger: str = "manual",
) -> dict:
    """Run funnel (воронка продаж) weekly report."""
    task_context = (
        f"Воронка продаж. Период: {date_from} — {date_to}. "
        f"Сравнение с: {comparison_from} — {comparison_to}. "
        f"Каналы: {channel}."
    )
    return await _run_report_pipeline(
        analysis_agents=["funnel-digitizer", "keyword-analyst"],
        task_context=task_context,
        task_type="funnel_weekly",
        date_from=date_from,
        date_to=date_to,
        comparison_from=comparison_from,
        comparison_to=comparison_to,
        channel=channel,
        trigger=trigger,
        compiler_prompt_prefix="Собери отчёт по воронке продаж",
    )


async def run_finolog_report(
    date_from: str,
    date_to: str,
    trigger: str = "manual",
) -> dict:
    """Run Finolog ДДС / cash flow weekly report.

    No comparison period or channel needed for cash flow analysis.
    """
    task_context = (
        f"ДДС / cash flow. Период: {date_from} — {date_to}."
    )
    return await _run_report_pipeline(
        analysis_agents=["finolog-analyst"],
        task_context=task_context,
        task_type="finolog_weekly",
        date_from=date_from,
        date_to=date_to,
        comparison_from="",
        comparison_to="",
        channel="both",
        trigger=trigger,
        compiler_prompt_prefix="Собери отчёт ДДС / cash flow",
    )


async def run_price_analysis(
    date_from: str,
    date_to: str,
    comparison_from: str,
    comparison_to: str,
    channel: str = "both",
    trigger: str = "manual",
) -> dict:
    """Multi-agent price analysis: 3-phase pipeline.

    Phase 1: Data collection (parallel) — price-strategist, margin-analyst, ad-efficiency
    Phase 2: Cross-analysis (parallel, with Phase 1 artifacts) — pricing-impact-analyst, hypothesis-tester
    Phase 3: Report compilation — report-compiler with all artifacts
    """
    run_id = new_run_id()
    start_time = time.monotonic()

    base_context = (
        f"Ценовой анализ. Период: {date_from} — {date_to}. "
        f"Сравнение с: {comparison_from} — {comparison_to}. "
        f"Каналы: {channel}."
    )

    # ── Phase 1: Data collection (parallel) ──────────────────────────
    logger.info("[price_analysis] Phase 1: data collection starting")

    phase1 = await _run_report_pipeline(
        analysis_agents=["price-strategist", "margin-analyst", "ad-efficiency"],
        task_context=base_context,
        task_type="price_analysis",
        date_from=date_from,
        date_to=date_to,
        comparison_from=comparison_from,
        comparison_to=comparison_to,
        channel=channel,
        trigger=trigger,
        skip_compiler=True,
    )

    # Extract successful artifacts for Phase 2
    phase1_artifacts = {}
    for name, result in phase1["artifacts"].items():
        if result.get("status") == "success" and result.get("artifact"):
            phase1_artifacts[name] = result["artifact"]

    logger.info(
        "[price_analysis] Phase 1 done: %d/%d succeeded, artifacts: %s",
        phase1["agents_succeeded"], phase1["agents_called"],
        list(phase1_artifacts.keys()),
    )

    # ── Phase 2: Cross-analysis (parallel, with Phase 1 artifacts) ───
    logger.info("[price_analysis] Phase 2: cross-analysis starting")

    phase2 = await _run_report_pipeline(
        analysis_agents=["pricing-impact-analyst", "hypothesis-tester"],
        task_context=base_context,
        task_type="price_analysis",
        date_from=date_from,
        date_to=date_to,
        comparison_from=comparison_from,
        comparison_to=comparison_to,
        channel=channel,
        trigger=trigger,
        prior_artifacts=phase1_artifacts,
        skip_compiler=True,
    )

    logger.info(
        "[price_analysis] Phase 2 done: %d/%d succeeded",
        phase2["agents_succeeded"], phase2["agents_called"],
    )

    # ── Phase 3: Compilation (all artifacts → report-compiler) ───────
    logger.info("[price_analysis] Phase 3: compilation starting")

    all_artifacts = {**phase1["artifacts"], **phase2["artifacts"]}

    compiler_input: dict[str, Any] = {
        "period": {"date_from": date_from, "date_to": date_to},
        "comparison_period": {"date_from": comparison_from, "date_to": comparison_to},
        "channel": channel,
        "report_type": "price_analysis",
        "artifacts": {},
    }

    for name, result in all_artifacts.items():
        if result.get("status") == "success" and result.get("artifact"):
            compiler_input["artifacts"][name] = result["artifact"]
        else:
            compiler_input["artifacts"][name] = {
                "status": "failed",
                "error": result.get("raw_output", "Unknown error")[:500],
            }

    compiler_task = (
        "Собери отчёт по ценовому анализу. "
        "Используй 8-секционную структуру ценового отчёта:\n"
        "0) Паспорт  1) Итоги  2) Ценовая матрица  "
        "3) Тренды продаж  4) Матрица остатки-цена  "
        "5) Влияние на маркетинг  6) Проверка гипотез  7) План действий\n"
        f"{COMPILER_FORMAT_INSTRUCTIONS}\n"
        f"Данные:\n{json.dumps(compiler_input, ensure_ascii=False, default=str)}"
    )

    compiler_result = await run_agent(
        agent_name="report-compiler",
        task=compiler_task,
        parent_run_id=run_id,
        trigger=trigger,
        task_type="price_analysis",
    )

    all_artifacts["report-compiler"] = compiler_result

    # ── Aggregate stats ──────────────────────────────────────────────
    duration_ms = int((time.monotonic() - start_time) * 1000)
    total_called = phase1["agents_called"] + phase2["agents_called"] + 1
    total_succeeded = phase1["agents_succeeded"] + phase2["agents_succeeded"]
    total_failed = phase1["agents_failed"] + phase2["agents_failed"]
    if compiler_result["status"] == "success":
        total_succeeded += 1
    else:
        total_failed += 1

    status = "success" if total_failed == 0 else ("partial" if total_succeeded > 0 else "failed")

    # Inject FAILED_AGENT_META for failed agents
    for name, result in all_artifacts.items():
        if name == "report-compiler":
            continue
        if isinstance(result, dict) and result.get("status") != "success":
            if not isinstance(result.get("artifact"), dict):
                result["artifact"] = {}
            result["artifact"]["_meta"] = FAILED_AGENT_META.copy()

    # Aggregate confidence
    confidences = {}
    for name, result in all_artifacts.items():
        if name == "report-compiler":
            continue
        art = result.get("artifact") if isinstance(result, dict) else result
        meta = (art.get("_meta") or {}) if isinstance(art, dict) else {}
        if "confidence" in meta:
            confidences[name] = meta["confidence"]

    agg_confidence = aggregate_confidence(confidences)

    artifacts_for_lim = {
        n: (r.get("artifact") if isinstance(r, dict) else r) or {}
        for n, r in all_artifacts.items()
    }
    worst_lim = worst_limitation(artifacts_for_lim)

    total_tokens = sum(r.get("total_tokens", 0) for r in all_artifacts.values() if isinstance(r, dict))
    total_cost = sum(r.get("cost_usd", 0.0) for r in all_artifacts.values() if isinstance(r, dict))

    asyncio.create_task(log_orchestrator_run(
        run_id=run_id,
        orchestrator="oleg",
        orchestrator_version="3.0",
        task_type="price_analysis",
        trigger=trigger,
        status=status,
        started_at=datetime.now(timezone.utc),
        finished_at=datetime.now(timezone.utc),
        duration_ms=duration_ms,
        agents_called=total_called,
        agents_succeeded=total_succeeded,
        agents_failed=total_failed,
        total_tokens=total_tokens,
        total_cost_usd=total_cost,
    ))

    logger.info(
        "[price_analysis] Complete: status=%s, %d agents, %dms",
        status, total_called, duration_ms,
    )

    # Ensure report has detailed_report + telegram_summary
    raw_price = compiler_result.get("artifact") if compiler_result else None
    if isinstance(raw_price, str):
        price_report = {"detailed_report": raw_price, "telegram_summary": ""}
    elif isinstance(raw_price, dict):
        price_report = raw_price
    else:
        price_report = {}

    # Always run deterministic formatter — it checks quality internally
    price_report = _ensure_report_fields(price_report)

    # Fallback: generate telegram_summary from detailed_report if empty
    _fill_telegram_summary(price_report)

    return {
        "run_id": run_id,
        "status": status,
        "report": price_report,
        "artifacts": all_artifacts,
        "agents_called": total_called,
        "agents_succeeded": total_succeeded,
        "agents_failed": total_failed,
        "duration_ms": duration_ms,
        "aggregate_confidence": agg_confidence,
        "worst_limitation": worst_lim,
        "total_tokens": total_tokens,
        "total_cost_usd": total_cost,
    }
