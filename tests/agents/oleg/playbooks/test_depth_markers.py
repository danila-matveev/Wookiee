"""Tests for depth marker conventions in templates (PLAY-03).

Verifies:
- Financial templates (daily/weekly/monthly) have correct depth markers
- Data-driven templates (dds/localization) have NO depth markers
"""
from pathlib import Path

import pytest

_TEMPLATES_DIR = (
    Path(__file__).resolve().parent.parent.parent.parent.parent
    / "agents" / "oleg" / "playbooks" / "templates"
)


def _count_depth_marker(filename: str, depth: str) -> int:
    content = (_TEMPLATES_DIR / filename).read_text(encoding="utf-8")
    return content.count(f"[depth: {depth}]")


def _count_any_depth_marker(filename: str) -> int:
    content = (_TEMPLATES_DIR / filename).read_text(encoding="utf-8")
    return content.count("[depth:")


# --- Financial LLM templates: must have depth markers ---

def test_daily_has_brief_markers():
    count = _count_depth_marker("daily.md", "brief")
    assert count >= 5, f"daily.md: expected >= 5 [depth: brief] markers, got {count}"


def test_weekly_has_deep_markers():
    count = _count_depth_marker("weekly.md", "deep")
    assert count >= 5, f"weekly.md: expected >= 5 [depth: deep] markers, got {count}"


def test_monthly_has_max_markers():
    count = _count_depth_marker("monthly.md", "max")
    assert count >= 5, f"monthly.md: expected >= 5 [depth: max] markers, got {count}"


def test_daily_does_not_have_deep_or_max_markers():
    deep = _count_depth_marker("daily.md", "deep")
    max_ = _count_depth_marker("daily.md", "max")
    assert deep == 0, f"daily.md should not have [depth: deep] markers, found {deep}"
    assert max_ == 0, f"daily.md should not have [depth: max] markers, found {max_}"


def test_weekly_does_not_have_brief_or_max_markers():
    brief = _count_depth_marker("weekly.md", "brief")
    max_ = _count_depth_marker("weekly.md", "max")
    assert brief == 0, f"weekly.md should not have [depth: brief] markers, found {brief}"
    assert max_ == 0, f"weekly.md should not have [depth: max] markers, found {max_}"


def test_monthly_does_not_have_brief_or_deep_markers():
    brief = _count_depth_marker("monthly.md", "brief")
    deep = _count_depth_marker("monthly.md", "deep")
    assert brief == 0, f"monthly.md should not have [depth: brief] markers, found {brief}"
    assert deep == 0, f"monthly.md should not have [depth: deep] markers, found {deep}"


# --- Data-driven templates: must have NO depth markers (D-09) ---

def test_dds_has_no_depth_markers():
    count = _count_any_depth_marker("dds.md")
    assert count == 0, (
        f"dds.md is data-driven (D-09) and must have 0 depth markers, found {count}"
    )


def test_localization_has_no_depth_markers():
    count = _count_any_depth_marker("localization.md")
    assert count == 0, (
        f"localization.md is data-driven (D-09) and must have 0 depth markers, found {count}"
    )


# --- Depth marker counts are substantial for financial templates ---

def test_daily_has_substantial_brief_markers():
    count = _count_depth_marker("daily.md", "brief")
    assert count >= 10, f"daily.md expected >= 10 [depth: brief] markers, got {count}"


def test_weekly_has_substantial_deep_markers():
    count = _count_depth_marker("weekly.md", "deep")
    assert count >= 10, f"weekly.md expected >= 10 [depth: deep] markers, got {count}"


def test_monthly_has_substantial_max_markers():
    count = _count_depth_marker("monthly.md", "max")
    assert count >= 10, f"monthly.md expected >= 10 [depth: max] markers, got {count}"
