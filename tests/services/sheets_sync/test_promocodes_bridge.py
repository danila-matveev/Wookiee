"""Tests for the DB→Sheets bridge in wb-promocodes sync (Task B.1.2)."""
from __future__ import annotations

from unittest.mock import MagicMock

from services.sheets_sync.sync.promocodes.bridge import (
    ensure_db_promos_in_sheets,
    plan_promo_inserts,
)
from services.sheets_sync.sync.promocodes.sheet_layout import (
    DATA_START_ROW,
    STATUS_NEW,
)


# ----------------------------------------------------------------------------
# plan_promo_inserts
# ----------------------------------------------------------------------------


def test_plan_promo_inserts_skips_codes_already_in_sheet():
    """Codes already present in the sheet must not be re-inserted."""
    sheet_codes = {"CHARLOTTE10", "MAYA15", "wendy20"}
    db_codes = [
        "CHARLOTTE10",  # exists — skip
        "NEW_PROMO",    # new
        "MAYA15",       # exists — skip
        "AUTUMN5",      # new
    ]
    inserts = plan_promo_inserts(db_codes, sheet_codes)
    assert inserts == ["NEW_PROMO", "AUTUMN5"]


def test_plan_promo_inserts_case_insensitive_match():
    """Sheet has 'wendy20' lowercase — DB code 'WENDY20' should be deduped."""
    sheet_codes = {"wendy20"}
    db_codes = ["WENDY20", "NEW_ONE"]
    inserts = plan_promo_inserts(db_codes, sheet_codes)
    assert inserts == ["NEW_ONE"]


def test_plan_promo_inserts_no_op_when_in_sync():
    """When DB and Sheets agree, no inserts are produced."""
    sheet_codes = {"A", "B", "C"}
    db_codes = ["A", "B", "C"]
    assert plan_promo_inserts(db_codes, sheet_codes) == []


def test_plan_promo_inserts_empty_db_returns_empty_list():
    """Empty DB must yield no inserts regardless of sheet contents."""
    assert plan_promo_inserts([], {"X", "Y"}) == []
    assert plan_promo_inserts([], set()) == []


def test_plan_promo_inserts_filters_blank_and_dedupes():
    """Blank / whitespace-only codes are dropped; duplicates within db_codes collapse."""
    sheet_codes: set[str] = set()
    db_codes = ["", "  ", "CODE1", "CODE1", "code1", "CODE2"]
    inserts = plan_promo_inserts(db_codes, sheet_codes)
    # CODE1 dedupes against itself (case-insensitive), CODE2 stays.
    assert inserts == ["CODE1", "CODE2"]


# ----------------------------------------------------------------------------
# ensure_db_promos_in_sheets — end-to-end wiring (with mocks)
# ----------------------------------------------------------------------------


def _build_col_a(dict_codes: list[str]) -> list[str]:
    """Build a synthetic col-A list with header padding above DATA_START_ROW."""
    # Rows 1..DATA_START_ROW-1 are dashboard / header text; data lives at 11+.
    header_pad = [""] * (DATA_START_ROW - 1)
    header_pad[0] = "Промокоды_аналитика"  # row 1 — sheet title
    return header_pad + dict_codes


def test_ensure_db_promos_in_sheets_inserts_missing_codes():
    """Missing DB codes get appended; existing ones are skipped."""
    ws = MagicMock()
    ws.col_values.return_value = _build_col_a(["CHARLOTTE10", "MAYA15"])
    db_codes = ["CHARLOTTE10", "NEW1", "NEW2"]

    inserted = ensure_db_promos_in_sheets(ws, db_codes=db_codes)
    assert inserted == 2

    # Two append_row calls in sorted order: NEW1, NEW2
    appended_codes = [call.args[0][0] for call in ws.append_row.call_args_list]
    assert appended_codes == ["NEW1", "NEW2"]
    # Each row has 5 cols (FIXED_NCOLS), col E = STATUS_NEW
    for call in ws.append_row.call_args_list:
        row = call.args[0]
        assert len(row) == 5
        assert row[4] == STATUS_NEW


def test_ensure_db_promos_in_sheets_no_op_when_all_present():
    """Returns 0 and does not call append_row when DB and Sheets agree."""
    ws = MagicMock()
    ws.col_values.return_value = _build_col_a(["CHARLOTTE10", "MAYA15"])
    db_codes = ["CHARLOTTE10", "MAYA15"]

    inserted = ensure_db_promos_in_sheets(ws, db_codes=db_codes)
    assert inserted == 0
    ws.append_row.assert_not_called()


def test_ensure_db_promos_in_sheets_empty_db_no_inserts():
    """Empty DB → no inserts, no errors."""
    ws = MagicMock()
    ws.col_values.return_value = _build_col_a(["CHARLOTTE10"])
    inserted = ensure_db_promos_in_sheets(ws, db_codes=[])
    assert inserted == 0
    ws.append_row.assert_not_called()


def test_ensure_db_promos_in_sheets_appends_in_sorted_order():
    """Multiple inserts must be appended in lexicographic order for determinism."""
    ws = MagicMock()
    ws.col_values.return_value = _build_col_a([])
    db_codes = ["ZETA", "ALPHA", "MIKE", "BRAVO"]

    inserted = ensure_db_promos_in_sheets(ws, db_codes=db_codes)
    assert inserted == 4

    appended_codes = [call.args[0][0] for call in ws.append_row.call_args_list]
    assert appended_codes == ["ALPHA", "BRAVO", "MIKE", "ZETA"]


def test_ensure_db_promos_in_sheets_ignores_dashboard_header_rows():
    """Codes that happen to appear in dashboard rows (1..10) must NOT be treated
    as existing dictionary entries — only rows >= DATA_START_ROW count."""
    ws = MagicMock()
    # Place a code-like string in a header row (row 3 = idx 2) — must be ignored.
    col_a = [""] * (DATA_START_ROW - 1)
    col_a[2] = "CHARLOTTE10"  # row 3, header zone
    col_a += ["MAYA15"]       # row 11, real dictionary entry
    ws.col_values.return_value = col_a

    db_codes = ["CHARLOTTE10", "MAYA15"]
    inserted = ensure_db_promos_in_sheets(ws, db_codes=db_codes)
    # CHARLOTTE10 should be inserted (header zone doesn't count); MAYA15 skipped.
    assert inserted == 1
    appended_codes = [call.args[0][0] for call in ws.append_row.call_args_list]
    assert appended_codes == ["CHARLOTTE10"]
