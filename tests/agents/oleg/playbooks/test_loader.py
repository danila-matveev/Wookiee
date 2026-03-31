"""Tests for PlaybookLoader (PLAY-02)."""
import pytest
from agents.oleg.playbooks.loader import load, TEMPLATE_MAP

TASK_TYPES = [
    "daily", "weekly", "monthly", "marketing_weekly",
    "marketing_monthly", "funnel_weekly", "dds", "localization",
]


@pytest.mark.parametrize("task_type", TASK_TYPES)
def test_load_returns_nonempty(task_type):
    result = load(task_type)
    assert len(result) > 100, f"load('{task_type}') returned only {len(result)} chars"


@pytest.mark.parametrize("task_type", TASK_TYPES)
def test_load_contains_separator(task_type):
    result = load(task_type)
    assert result.count("---") >= 2, (
        f"Expected at least 2 '---' separators in load('{task_type}'), "
        f"got {result.count('---')}"
    )


def test_template_map_covers_all_types():
    for tt in TASK_TYPES:
        assert tt in TEMPLATE_MAP, f"TEMPLATE_MAP missing '{tt}'"


def test_unknown_type_falls_back_to_weekly():
    weekly = load("weekly")
    unknown = load("totally_unknown_type")
    # Both use weekly.md template — content should be identical
    assert unknown == weekly, "Unknown task_type should fall back to weekly.md content"


def test_custom_maps_to_weekly():
    assert TEMPLATE_MAP["custom"] == "weekly.md"


def test_template_map_has_9_entries():
    """8 task types + 1 custom fallback = 9 entries."""
    assert len(TEMPLATE_MAP) >= 9, f"Expected >= 9 TEMPLATE_MAP entries, got {len(TEMPLATE_MAP)}"


def test_load_returns_all_three_sections():
    """load() result must contain content from core, template, and rules."""
    result = load("weekly")
    # core.md starts with "# Ядро базы знаний"
    assert "Ядро базы знаний" in result or "Бизнес-контекст" in result, \
        "core.md content not found in assembled prompt"
    # rules.md starts with "# Правила и стратегии"
    assert "Правила и стратегии" in result or "ДРР" in result, \
        "rules.md content not found in assembled prompt"
    # weekly.md contains the weekly template marker
    assert "weekly" in result.lower() or "недельн" in result.lower(), \
        "weekly template content not found"
