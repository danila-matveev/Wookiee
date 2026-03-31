"""Tests for toggle heading format in all 8 templates (VER-03).

Verifies:
- Each template uses ## ▶ (U+25B6) toggle headings
- Financial templates have >= 10 toggle headings each
- No template uses wrong arrow variants (## >, ## ►, ## ▷)
"""
from pathlib import Path

import pytest

_TEMPLATES_DIR = (
    Path(__file__).resolve().parent.parent.parent.parent.parent
    / "agents" / "oleg" / "playbooks" / "templates"
)

TEMPLATE_FILES = [
    "daily.md", "weekly.md", "monthly.md",
    "marketing_weekly.md", "marketing_monthly.md",
    "funnel_weekly.md", "dds.md", "localization.md",
]

FINANCIAL_TEMPLATES = ["daily.md", "weekly.md", "monthly.md"]


def _count_toggle_headings(filename: str) -> int:
    """Count ## ▶ occurrences (U+25B6 BLACK RIGHT-POINTING TRIANGLE)."""
    content = (_TEMPLATES_DIR / filename).read_text(encoding="utf-8")
    return content.count("## \u25b6")


def _has_wrong_arrow(filename: str) -> bool:
    """Check for wrong arrow variants that should not be used."""
    content = (_TEMPLATES_DIR / filename).read_text(encoding="utf-8")
    wrong_patterns = [
        "## >",        # plain greater-than
        "## \u25ba",   # U+25BA BLACK RIGHT-POINTING POINTER (►)
        "## \u25b7",   # U+25B7 WHITE RIGHT-POINTING TRIANGLE (▷)
        "## -&gt;",    # HTML entity
    ]
    return any(p in content for p in wrong_patterns)


@pytest.mark.parametrize("filename", TEMPLATE_FILES)
def test_template_has_toggle_headings(filename):
    """Every template must have at least 3 ## ▶ headings."""
    count = _count_toggle_headings(filename)
    assert count >= 3, (
        f"{filename}: expected >= 3 '## ▶' headings, got {count}"
    )


@pytest.mark.parametrize("filename", FINANCIAL_TEMPLATES)
def test_financial_template_has_many_toggle_headings(filename):
    """Financial templates (daily/weekly/monthly) must have >= 10 ## ▶ headings."""
    count = _count_toggle_headings(filename)
    assert count >= 10, (
        f"{filename}: expected >= 10 '## ▶' headings, got {count}"
    )


@pytest.mark.parametrize("filename", TEMPLATE_FILES)
def test_no_wrong_arrow_variants(filename):
    """No template should use wrong arrow variants instead of ## ▶ (U+25B6)."""
    assert not _has_wrong_arrow(filename), (
        f"{filename}: contains wrong arrow variant (## >, ## ►, ## ▷). "
        f"Use ## ▶ (U+25B6) only."
    )


def test_all_templates_have_consistent_format():
    """All 8 templates must use the correct U+25B6 character."""
    correct_char = "\u25b6"
    for filename in TEMPLATE_FILES:
        content = (_TEMPLATES_DIR / filename).read_text(encoding="utf-8")
        assert correct_char in content, (
            f"{filename}: does not contain U+25B6 (▶) toggle heading character"
        )


def test_toggle_heading_totals():
    """Total toggle headings across all 8 templates must be substantial."""
    total = sum(_count_toggle_headings(f) for f in TEMPLATE_FILES)
    assert total >= 60, f"Total toggle headings: {total} (expected >= 60)"
