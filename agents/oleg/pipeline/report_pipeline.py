"""
Report pipeline — full reliability flow for Oleg v2.0 report generation.

Pipeline steps (sequential):
1. Pre-flight gate check (gate_checker.check_all) — block on hard failures
2. Send pre-flight Telegram notification (success or failure reason)
3. Run LLM chain with retry (up to 2 retries on empty/short responses)
4. Validate sections + graceful degradation (Russian placeholders for missing)
5. Check that report has at least some real content (not all placeholders)
6. Publish to Notion (sync_report upsert)
7. Send Telegram notification with Notion URL (Telegram failure = warning, not error)

Implements:
- REL-02: Retry on empty LLM response (max 2 retries)
- REL-03: Empty/all-placeholder reports are NOT published
- REL-04: Missing sections get Russian human-readable placeholders
- REL-05: All required sections present after validate_and_degrade
- REL-07: Telegram ONLY after successful Notion publish; Telegram failure does not fail pipeline

Per D-13: Notion is the primary artifact. Telegram failure after successful Notion
publish does NOT mark the pipeline as failed — it is recorded as a warning.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import date
from typing import List, Optional

from agents.oleg.pipeline.gate_checker import GateChecker, format_preflight_message
from agents.oleg.pipeline.report_types import REPORT_CONFIGS, ReportType
from agents.oleg.orchestrator.chain import ChainResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class ReportPipelineResult:
    """Result of a single report pipeline run."""
    success: bool = False
    skipped: bool = False
    failed: bool = False
    reason: str = ""
    notion_url: str = ""
    warnings: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Substantiality check
# ---------------------------------------------------------------------------

def _is_substantial(result: ChainResult) -> bool:
    """Return True if the chain result has enough content to be a real report.

    Criteria (per Claude's Discretion in 03-CONTEXT.md):
    - detailed must be >= 200 chars
    - detailed must contain at least one ## heading (markdown section)
    """
    detailed = result.detailed or ""
    if len(detailed) < 200:
        return False
    if "##" not in detailed:
        return False
    return True


# ---------------------------------------------------------------------------
# Chain with retry (REL-02)
# ---------------------------------------------------------------------------

async def _run_chain_with_retry(
    orchestrator,
    task: str,
    task_type: str,
    context: dict,
    max_retries: int = 2,
) -> Optional[ChainResult]:
    """Run orchestrator.run_chain with up to max_retries retries on empty response.

    Returns ChainResult if any attempt returns substantial content.
    Returns None if all attempts (1 initial + max_retries) produce empty results.
    """
    for attempt in range(max_retries + 1):
        result = await orchestrator.run_chain(task=task, task_type=task_type, context=context)
        if _is_substantial(result):
            return result
        if attempt < max_retries:
            logger.warning(
                f"Empty chain result (attempt {attempt + 1}/{max_retries + 1}), retrying — "
                f"detailed length={len(result.detailed or '')}"
            )
    logger.error(
        f"Chain returned empty result after {max_retries + 1} total attempts for task_type={task_type}"
    )
    return None


# ---------------------------------------------------------------------------
# Post-processing: strip LLM formatting artifacts
# ---------------------------------------------------------------------------

def _clean_report_text(report_md: str) -> str:
    """Remove LLM formatting artifacts from the detailed report.

    Fixes that prompt instructions alone cannot reliably prevent:
    - "(Reconciliation)" appended to "Сведение ΔМаржи"
    - "(Top/Bottom)" appended to "Юнит-экономика артикулов"
    - telegram_summary / brief_summary sections bleeding into Notion report
    """
    # Strip English qualifiers from known section names
    report_md = re.sub(
        r'(## (?:▶ )?Сведение ΔМаржи)\s*\(Reconciliation\)',
        r'\1',
        report_md,
    )
    report_md = re.sub(
        r'(## (?:▶ )?Юнит-экономика артикулов)\s*\(Top/Bottom\)',
        r'\1',
        report_md,
    )

    # Remove telegram_summary / brief_summary bleed sections (always at end).
    # Also strip the --- separator that precedes them if present.
    for marker in ('\n## telegram_summary', '\n## brief_summary'):
        idx = report_md.find(marker)
        if idx >= 0:
            trimmed = report_md[:idx].rstrip()
            if trimmed.endswith('---'):
                trimmed = trimmed[:-3].rstrip()
            report_md = trimmed
            logger.debug(f"Stripped bleeding section '{marker.strip()}' from detailed_report")

    return report_md


# ---------------------------------------------------------------------------
# Section validation and graceful degradation (REL-04, REL-05)
# ---------------------------------------------------------------------------

DEGRADATION_PLACEHOLDER = (
    "Данные для этой секции временно недоступны. "
    "Агент не смог получить информацию из источника данных. "
    "Рекомендуется проверить подключение к источникам данных "
    "и повторить генерацию отчёта."
)


def _load_required_sections(report_type: ReportType) -> List[str]:
    """Parse ## headings from the report type's template file.

    If template_path is not configured or file not found, returns empty list.
    Empty list means validate_and_degrade is a no-op and has_substantial_content
    falls back to overall length check.
    """
    config = REPORT_CONFIGS.get(report_type)
    if not config or not config.template_path:
        return []
    try:
        with open(config.template_path) as f:
            content = f.read()
        return [
            line.strip()
            for line in content.splitlines()
            if line.strip().startswith("## ")
        ]
    except FileNotFoundError:
        logger.warning(f"Template not found for {report_type.value}: {config.template_path}")
        return []
    except Exception as e:
        logger.warning(f"Failed to load template for {report_type.value}: {e}")
        return []


def validate_and_degrade(
    report_md: str,
    report_type: ReportType,
    required_sections: Optional[List[str]] = None,
) -> str:
    """Ensure all required sections exist in the report.

    For each missing required section heading, appends the section with a
    human-readable Russian placeholder (no technical error messages).

    Args:
        report_md: The report markdown to validate.
        report_type: Used to load required sections from template (if required_sections not given).
        required_sections: Override list of required section headings. If None, loads from template.

    Returns:
        Modified markdown with all required sections present.
    """
    if required_sections is None:
        required_sections = _load_required_sections(report_type)

    for heading in required_sections:
        if heading not in report_md:
            report_md += f"\n\n{heading}\n\n{DEGRADATION_PLACEHOLDER}\n"
            logger.info(f"Degraded missing section: {heading}")

    return report_md


def has_substantial_content(
    report_md: str,
    report_type: ReportType = None,
    required_sections: Optional[List[str]] = None,
) -> bool:
    """Return True if at least one section has real content (not just placeholder).

    If required_sections is empty (no template), falls back to overall length check (> 500 chars).

    Args:
        report_md: The (possibly degraded) report markdown to check.
        report_type: Used to load required sections from template (if required_sections not given).
        required_sections: Override list of required section headings.
    """
    if required_sections is None:
        required_sections = _load_required_sections(report_type) if report_type else []

    if not required_sections:
        # No template → fall back to length check
        return len(report_md) > 500

    real_count = 0
    for i, heading in enumerate(required_sections):
        idx = report_md.find(heading)
        if idx < 0:
            continue

        # Find content between this heading and the next heading (or end of document)
        content_start = idx + len(heading)
        next_heading_idx = len(report_md)
        for other_heading in required_sections:
            if other_heading == heading:
                continue
            other_idx = report_md.find(other_heading, content_start)
            if other_idx > idx and other_idx < next_heading_idx:
                next_heading_idx = other_idx

        section_content = report_md[content_start:next_heading_idx].strip()
        if section_content and DEGRADATION_PLACEHOLDER not in section_content:
            real_count += 1

    return real_count > 0


# ---------------------------------------------------------------------------
# Main pipeline entry point
# ---------------------------------------------------------------------------

async def run_report(
    report_type: ReportType,
    target_date: date,
    orchestrator,
    notion_client,
    alerter,
    gate_checker: GateChecker,
    date_from: str = None,
    date_to: str = None,
) -> ReportPipelineResult:
    """Run the full report pipeline with reliability guarantees.

    Steps:
    1. Pre-flight gate check — hard failures block the run
    2. Pre-flight Telegram notification
    3. LLM chain with retry (2 retries on empty)
    4. Section validation + graceful degradation (Russian placeholders)
    5. Empty report check — all-placeholder reports are NOT published
    6. Publish to Notion
    7. Telegram notification (failure is warning, not error — D-13)

    Args:
        report_type: Which report type to generate.
        target_date: Date for which the report is generated.
        orchestrator: OlegOrchestrator instance.
        notion_client: NotionClient instance with sync_report method.
        alerter: Alerter instance with send_alert method.
        gate_checker: GateChecker instance for pre-flight data quality checks.
        date_from: Optional date range start (ISO string). Defaults to target_date.
        date_to: Optional date range end (ISO string). Defaults to target_date.

    Returns:
        ReportPipelineResult with success/skipped/failed and reason.
    """
    config = REPORT_CONFIGS.get(report_type)
    if not config:
        return ReportPipelineResult(
            failed=True,
            reason=f"Unknown report type: {report_type}",
        )

    warnings: List[str] = []

    # ------------------------------------------------------------------
    # Step 1: Pre-flight gate check (D-01, D-02, D-03, D-04)
    # ------------------------------------------------------------------
    gate_result = None
    for mp in config.marketplaces:
        mp_gate_result = gate_checker.check_all(marketplace=mp, target_date=target_date)
        # Use last result for format_preflight_message (target_date is same for all)
        gate_result = mp_gate_result
        if not mp_gate_result.can_run:
            reason = "; ".join(g.detail for g in mp_gate_result.hard_failed)
            fail_msg = format_preflight_message(mp_gate_result, [])
            try:
                await alerter.send_alert(fail_msg)
            except Exception as e:
                logger.warning(f"Failed to send gate failure alert: {e}")
            logger.warning(
                f"Pipeline skipped for {report_type.value} on {target_date}: {reason}"
            )
            return ReportPipelineResult(skipped=True, reason=reason)

    # ------------------------------------------------------------------
    # Step 2: Pre-flight success Telegram (D-05)
    # ------------------------------------------------------------------
    if gate_result is not None:
        success_msg = format_preflight_message(gate_result, [config.display_name_ru])
        try:
            await alerter.send_alert(success_msg)
        except Exception as e:
            logger.warning(f"Pre-flight success alert failed: {e}")
            warnings.append(f"Pre-flight alert failed: {e}")

    # ------------------------------------------------------------------
    # Step 3: LLM chain with retry (D-07, D-08, REL-02)
    # ------------------------------------------------------------------
    task = (
        f"Сформируй {config.display_name_ru} за {target_date.strftime('%d.%m.%Y')}. "
        f"Период: {date_from or target_date.isoformat()} — {date_to or target_date.isoformat()}."
    )
    task_context = {
        "date_from": date_from or target_date.isoformat(),
        "date_to": date_to or target_date.isoformat(),
        "report_type": report_type.value,
        "target_date": target_date.isoformat(),
    }

    chain_result = await _run_chain_with_retry(
        orchestrator=orchestrator,
        task=task,
        task_type=report_type.value,
        context=task_context,
        max_retries=2,
    )

    if chain_result is None:
        reason = f"LLM empty after 2 retries for {report_type.value}"
        logger.error(reason)
        try:
            await alerter.send_alert(
                f"❌ Отчёт {config.display_name_ru} за {target_date.strftime('%d.%m.%Y')} "
                f"не сгенерирован после 3 попыток. Причина: пустой ответ LLM."
            )
        except Exception as e:
            logger.warning(f"Failed to send failure alert: {e}")
        return ReportPipelineResult(failed=True, reason=reason)

    report_md = _clean_report_text(chain_result.detailed or "")

    # ------------------------------------------------------------------
    # Step 4: Section validation + graceful degradation (D-09, D-10, D-11, REL-04, REL-05)
    # ------------------------------------------------------------------
    required_sections = _load_required_sections(report_type)
    validated_md = validate_and_degrade(
        report_md=report_md,
        report_type=report_type,
        required_sections=required_sections,
    )

    # ------------------------------------------------------------------
    # Step 5: Empty report check (D-13, REL-03)
    # ------------------------------------------------------------------
    if not has_substantial_content(
        report_md=validated_md,
        report_type=report_type,
        required_sections=required_sections,
    ):
        reason = f"Report is all placeholders, not publishing for {report_type.value}"
        logger.warning(reason)
        try:
            await alerter.send_alert(
                f"⚠️ Отчёт {config.display_name_ru} за {target_date.strftime('%d.%m.%Y')} "
                f"сформирован, но содержит только заглушки. Публикация отменена."
            )
        except Exception as e:
            logger.warning(f"Failed to send empty report alert: {e}")
        return ReportPipelineResult(failed=True, reason=reason)

    # ------------------------------------------------------------------
    # Step 6: Publish to Notion (REL-06 — upsert via sync_report)
    # ------------------------------------------------------------------
    date_from_str = date_from or target_date.isoformat()
    date_to_str = date_to or target_date.isoformat()

    notion_url = await notion_client.sync_report(
        start_date=date_from_str,
        end_date=date_to_str,
        report_md=validated_md,
        report_type=report_type.value,
        source="Oleg v2 (auto)",
    )

    if not notion_url:
        reason = f"Notion publish failed for {report_type.value}"
        logger.error(reason)
        return ReportPipelineResult(failed=True, reason=reason)

    logger.info(f"Report published to Notion: {notion_url}")

    # ------------------------------------------------------------------
    # Step 7: Telegram ONLY after Notion success (D-12, D-13, REL-07)
    # ------------------------------------------------------------------
    tg_message = chain_result.telegram_summary
    if tg_message:
        tg_message = tg_message.rstrip() + f"\n\n{notion_url}"
    else:
        tg_message = f"Отчёт опубликован: {notion_url}"

    try:
        await alerter.send_alert(tg_message)
    except Exception as e:
        # Notion is primary artifact — Telegram failure is warning, not error (D-13)
        logger.warning(f"Telegram notification failed (report already published): {e}")
        warnings.append(f"Telegram failed: {e}")

    return ReportPipelineResult(
        success=True,
        notion_url=notion_url,
        warnings=warnings,
    )
