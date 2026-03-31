"""Tests that all 19 playbook section content is preserved across modules (PLAY-01).

Verifies that no playbook section from the original playbook_ARCHIVE.md
was lost during modularization — key phrases from each section exist in
at least one of: core.md, rules.md, or templates/*.md
"""
from pathlib import Path

import pytest

_PLAYBOOKS_DIR = Path(__file__).resolve().parent.parent.parent.parent.parent / "agents" / "oleg" / "playbooks"


def _read_all_modules() -> str:
    """Read all module files and concatenate into one string for searching."""
    parts = []
    parts.append((_PLAYBOOKS_DIR / "core.md").read_text(encoding="utf-8"))
    parts.append((_PLAYBOOKS_DIR / "rules.md").read_text(encoding="utf-8"))
    for template_file in sorted((_PLAYBOOKS_DIR / "templates").glob("*.md")):
        parts.append(template_file.read_text(encoding="utf-8"))
    return "\n".join(parts)


@pytest.fixture(scope="module")
def all_modules_content():
    return _read_all_modules()


# Key phrases from each of 19 original playbook sections
# Each entry: (section_name, phrase_to_find)
SECTION_PHRASES = [
    ("Section 1 - Business Context", "Бизнес-контекст"),
    ("Section 2 - 5 Levers", "5 рычагов"),
    ("Section 3 - Glossary", "Глоссарий"),
    ("Section 4 - Margin Delta", "ΔМаржи"),
    ("Section 5 - Data Quality", "Data Quality"),
    ("Section 6 - Formulas", "верифицированн"),
    ("Section 7 - P&L", "ОПИУ"),
    ("Section 8 - Report Passport", "Паспорт отчёта"),
    ("Section 9 - Daily Template", "Ежедневный"),
    ("Section 10 - Advertising", "ДРР"),
    ("Section 11 - Diagnostics", "диагностик"),
    ("Section 12 - Report Principles", "Принципы"),
    ("Section 13 - Price Analysis", "Ценовой анализ"),
    ("Section 14 - Action List", "Action list"),
    ("Section 15 - Feedback", "Обратная связь"),
    ("Section 16 - Toggle Format", "▶"),
    ("Section 17 - Plan vs Fact", "План-факт"),
    ("Section 18 - MoySklad", "МойСклад"),
    ("Section 19 - Buyout Lag", "выкуп"),
]


@pytest.mark.parametrize("section_name,phrase", SECTION_PHRASES)
def test_section_phrase_exists_in_modules(all_modules_content, section_name, phrase):
    """Each section's key phrase must exist in at least one module file."""
    assert phrase in all_modules_content, (
        f"{section_name}: phrase '{phrase}' not found in any module file "
        f"(core.md, rules.md, or templates/*.md)"
    )


def test_minimum_phrase_count(all_modules_content):
    """At least 15 of 19 key phrases should be present (allowing minor wording variations)."""
    found = sum(1 for _, phrase in SECTION_PHRASES if phrase in all_modules_content)
    assert found >= 15, f"Only {found}/19 section phrases found in modules"


def test_core_md_exists_and_nonempty():
    core = _PLAYBOOKS_DIR / "core.md"
    assert core.exists(), "core.md does not exist"
    content = core.read_text(encoding="utf-8")
    assert len(content) > 1000, f"core.md too short: {len(content)} chars"


def test_rules_md_exists_and_nonempty():
    rules = _PLAYBOOKS_DIR / "rules.md"
    assert rules.exists(), "rules.md does not exist"
    content = rules.read_text(encoding="utf-8")
    assert len(content) > 500, f"rules.md too short: {len(content)} chars"


def test_all_8_templates_exist():
    templates_dir = _PLAYBOOKS_DIR / "templates"
    expected = [
        "daily.md", "weekly.md", "monthly.md",
        "marketing_weekly.md", "marketing_monthly.md",
        "funnel_weekly.md", "dds.md", "localization.md",
    ]
    for name in expected:
        f = templates_dir / name
        assert f.exists(), f"Template {name} does not exist"
        assert f.stat().st_size > 100, f"Template {name} is too small"
