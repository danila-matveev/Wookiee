# agents/reporter/validator.py
"""Deterministic report validator — no LLM, just checks."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

from agents.reporter.analyst.schemas import ReportInsights
from agents.reporter.config import (
    MIN_CONFIDENCE,
    MIN_REPORT_LENGTH,
    MIN_TOGGLE_SECTIONS,
    MAX_PLACEHOLDERS,
)


@dataclass
class ValidationResult:
    verdict: Literal["PASS", "RETRY", "FAIL"]
    issues: list[str] = field(default_factory=list)


def validate(report_md: str, insights: ReportInsights) -> ValidationResult:
    """Validate report quality. Returns PASS/RETRY/FAIL."""
    issues: list[str] = []

    # 1. Minimum sections
    toggle_count = report_md.count("## ▶")
    if toggle_count < MIN_TOGGLE_SECTIONS:
        issues.append(f"Only {toggle_count} sections, need ≥{MIN_TOGGLE_SECTIONS}")

    # 2. Russian text present
    russian_chars = len(re.findall(r"[а-яА-ЯёЁ]", report_md))
    total_chars = max(len(report_md), 1)
    if russian_chars / total_chars < 0.1:
        issues.append("Low Russian text ratio")

    # 3. No raw JSON leak
    stripped = report_md.strip()
    if stripped.startswith("{") or stripped.startswith("```json") or stripped.startswith('"detailed'):
        issues.append("Raw JSON detected in report")

    # 4. Confidence threshold
    if insights.overall_confidence < MIN_CONFIDENCE:
        issues.append(f"Low confidence: {insights.overall_confidence:.2f}")

    # 5. Placeholder check
    placeholders = ["Н/Д", "Данные отсутствуют", "TODO", "TBD", "N/A"]
    placeholder_count = sum(report_md.count(p) for p in placeholders)
    if placeholder_count > MAX_PLACEHOLDERS:
        issues.append(f"Too many placeholders: {placeholder_count}")

    # 6. Minimum length
    if len(report_md) < MIN_REPORT_LENGTH:
        issues.append(f"Report too short: {len(report_md)} chars")

    # Determine verdict
    has_critical = any(
        "Raw JSON" in i or "sections" in i.lower() or "too short" in i.lower()
        for i in issues
    )
    if has_critical:
        return ValidationResult(verdict="RETRY", issues=issues)
    if len(issues) > 3:
        return ValidationResult(verdict="FAIL", issues=issues)
    return ValidationResult(verdict="PASS", issues=issues)
