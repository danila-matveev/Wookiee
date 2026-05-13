"""Tests for the DB→Sheets bridge in search-queries sync (Task B.1.1)."""
from __future__ import annotations

from unittest.mock import MagicMock

from services.sheets_sync.sync.search_queries.bridge import (
    ensure_db_words_in_sheets,
    parse_section_dividers,
    plan_inserts,
)


# ----------------------------------------------------------------------------
# parse_section_dividers
# ----------------------------------------------------------------------------


def test_parse_section_dividers_finds_known_markers():
    """All four divider headers must be located and sections sized correctly."""
    col_a = [
        "Аналитика по запросам",  # row 1 — header
        "",                       # row 2 — dates
        "wooki",                  # row 3 — brand
        "Вуки",                   # row 4 — brand
        "Артикулы внешний лид",   # row 5 — divider
        "163151603",              # row 6 — external
        "Креаторы общие:",        # row 7 — divider
        "WW121749",               # row 8 — cr_general
        "Креаторы личные:",       # row 9 — divider
        "WW113490",               # row 10 — cr_personal
        "Соцсети:",               # row 11 — divider
        "WW140475",               # row 12 — social
    ]
    sections = parse_section_dividers(col_a)
    # insert row = the divider row of the NEXT section (or len+1 for the last)
    assert sections["brand_end"] == 5      # before "Артикулы внешний лид"
    assert sections["external_end"] == 7   # before "Креаторы общие:"
    assert sections["cr_general_end"] == 9 # before "Креаторы личные:"
    assert sections["cr_personal_end"] == 11  # before "Соцсети:"
    assert sections["social_end"] == 13    # bottom of sheet (len+1)


def test_parse_section_dividers_falls_back_to_bottom_when_all_markers_missing():
    """Missing all dividers → every section appends to the bottom of the sheet."""
    col_a = [
        "Аналитика по запросам",
        "",
        "wooki",
        "Вуки",
        # No section dividers at all — pure brand-list sheet.
        "Audrey",
    ]
    sections = parse_section_dividers(col_a)
    fallback = len(col_a) + 1
    assert sections["brand_end"] == fallback
    assert sections["external_end"] == fallback
    assert sections["cr_general_end"] == fallback
    assert sections["cr_personal_end"] == fallback
    assert sections["social_end"] == fallback


def test_parse_section_dividers_partial_markers_use_next_present_divider():
    """If 'Артикулы внешний лид' is missing but 'Креаторы общие:' present,
    brand_end falls through to the next present divider (cr_general's row).

    Rationale: keeps brand inserts ABOVE the first real section divider rather
    than appending past creator/social blocks. This mirrors how the live sheet
    actually evolved historically (some sheets are missing the external block).
    """
    col_a = [
        "Аналитика по запросам",
        "",
        "wooki",
        "Вуки",
        # No "Артикулы внешний лид" — skipped section.
        "Креаторы общие:",
        "WW121749",
    ]
    sections = parse_section_dividers(col_a)
    fallback = len(col_a) + 1
    # external_end marker absent → brand_end falls back to bottom
    assert sections["brand_end"] == fallback
    assert sections["external_end"] == 5  # cr_general marker row
    # cr_general_end marker present, cr_personal_end absent → falls back
    assert sections["cr_general_end"] == fallback
    assert sections["social_end"] == fallback


# ----------------------------------------------------------------------------
# plan_inserts
# ----------------------------------------------------------------------------


def test_plan_inserts_skips_existing():
    """Words already in Sheets must not be re-inserted."""
    sheet_words = {"wooki", "163151603", "WW121749"}
    db_words = [
        ("wooki", "brand", None),       # exists — skip
        ("Audrey", "brand", None),      # new → brand section
        ("WW999999", "creators", None), # new → cr_general (no personal prefix)
        ("163151603", "yandex", None),  # exists — skip
    ]
    sections = {
        "brand_end": 5,
        "external_end": 7,
        "cr_general_end": 9,
        "cr_personal_end": 11,
        "social_end": 13,
    }
    inserts = plan_inserts(db_words, sheet_words, sections)
    assert len(inserts) == 2
    assert ("Audrey", 5) in inserts
    assert ("WW999999", 9) in inserts


def test_plan_inserts_routes_personal_creator_by_campaign():
    """campaign_name 'креатор_*' routes the WW code to the personal-creator section."""
    sheet_words: set[str] = set()
    db_words = [("WW113490", "creators", "креатор_Шматов")]
    sections = {
        "brand_end": 3,
        "external_end": 5,
        "cr_general_end": 7,
        "cr_personal_end": 9,
        "social_end": 11,
    }
    inserts = plan_inserts(db_words, sheet_words, sections)
    assert inserts == [("WW113490", 9)]


def test_plan_inserts_routes_external_purposes():
    """yandex / vk_target / adblogger / other → external section."""
    sheet_words: set[str] = set()
    sections = {
        "brand_end": 3, "external_end": 5, "cr_general_end": 7,
        "cr_personal_end": 9, "social_end": 11,
    }
    db_words = [
        ("123", "yandex", None),
        ("456", "vk_target", None),
        ("789", "adblogger", None),
        ("000", "other", None),
        ("smm1", "social", None),
    ]
    inserts = plan_inserts(db_words, sheet_words, sections)
    assert ("123", 5) in inserts
    assert ("456", 5) in inserts
    assert ("789", 5) in inserts
    assert ("000", 5) in inserts
    assert ("smm1", 11) in inserts  # social → social_end


def test_plan_inserts_handles_two_tuple_entries():
    """Bridge accepts (word, purpose) without explicit campaign_name."""
    sheet_words: set[str] = set()
    sections = {
        "brand_end": 3, "external_end": 5, "cr_general_end": 7,
        "cr_personal_end": 9, "social_end": 11,
    }
    inserts = plan_inserts([("Audrey", "brand")], sheet_words, sections)
    assert inserts == [("Audrey", 3)]


# ----------------------------------------------------------------------------
# ensure_db_words_in_sheets — end-to-end wiring (with mocks)
# ----------------------------------------------------------------------------


def test_ensure_db_words_in_sheets_inserts_in_descending_row_order():
    """Multiple inserts must go bottom-up so later insert row numbers stay valid."""
    ws = MagicMock()
    ws.col_values.return_value = [
        "Аналитика по запросам",
        "",
        "wooki",
        "Артикулы внешний лид",
        "Креаторы общие:",
        "Креаторы личные:",
        "Соцсети:",
    ]
    db_words = [
        ("Audrey", "brand", None),         # → brand_end = row 4
        ("WW777", "creators", None),       # → cr_general_end = row 6
        ("smm_1", "social", None),         # → social_end = row 8 (len+1)
    ]
    inserted = ensure_db_words_in_sheets(ws, db_words=db_words)
    assert inserted == 3

    # The first insert call must target the bottom-most row, not the top one.
    call_rows = [call.args[1] for call in ws.insert_row.call_args_list]
    assert call_rows == sorted(call_rows, reverse=True), (
        f"Expected descending row order, got {call_rows}"
    )


def test_ensure_db_words_in_sheets_no_op_when_all_present():
    """Returns 0 and does not call insert_row when DB and Sheets agree."""
    ws = MagicMock()
    ws.col_values.return_value = [
        "Аналитика по запросам",
        "",
        "wooki",
        "Артикулы внешний лид",
        "WW111",
        "Креаторы общие:",
        "Креаторы личные:",
        "Соцсети:",
    ]
    db_words = [
        ("wooki", "brand", None),
        ("WW111", "yandex", None),
    ]
    inserted = ensure_db_words_in_sheets(ws, db_words=db_words)
    assert inserted == 0
    ws.insert_row.assert_not_called()
