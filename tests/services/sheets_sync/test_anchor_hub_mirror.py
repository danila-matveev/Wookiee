"""Unit tests for services/sheets_sync/hub_to_sheets/anchor.py."""
from __future__ import annotations

import pytest

from services.sheets_sync.hub_to_sheets.anchor import (
    build_anchor_index,
    db_row_anchor,
)


def test_simple_anchor_index_one_column() -> None:
    cols = ["Артикул", "Модель"]
    rows = [
        ["wendy/black", "Wendy"],
        ["wendy/white", "Wendy"],
    ]
    idx = build_anchor_index(cols, rows, ["Артикул"])
    assert idx[("wendy/black",)] == 2
    assert idx[("wendy/white",)] == 3


def test_composite_anchor_index() -> None:
    cols = ["Название склейки", "БАРКОД", "Артикул"]
    rows = [
        ["WB-A", "1234567890", "wendy/black"],
        ["WB-A", "1234567891", "wendy/white"],
    ]
    idx = build_anchor_index(cols, rows, ["Название склейки", "БАРКОД"])
    assert idx[("wb-a", "1234567890")] == 2
    assert idx[("wb-a", "1234567891")] == 3


def test_empty_anchor_rows_are_skipped() -> None:
    cols = ["Артикул", "Модель"]
    rows = [
        ["wendy/black", "Wendy"],
        ["", ""],  # totally empty — skipped
        ["", "Wendy"],  # anchor-empty even if other cols present — skipped
    ]
    idx = build_anchor_index(cols, rows, ["Артикул"])
    assert idx == {("wendy/black",): 2}


def test_anchor_index_keeps_first_duplicate() -> None:
    cols = ["Артикул"]
    rows = [
        ["wendy/black"],
        ["wendy/black"],
    ]
    idx = build_anchor_index(cols, rows, ["Артикул"])
    assert idx == {("wendy/black",): 2}


def test_anchor_index_case_insensitive() -> None:
    cols = ["Артикул"]
    rows = [["Wendy/Black"]]
    idx = build_anchor_index(cols, rows, ["Артикул"])
    assert idx[("wendy/black",)] == 2


def test_anchor_index_missing_column_raises() -> None:
    cols = ["Модель"]
    rows = [["Wendy"]]
    with pytest.raises(KeyError):
        build_anchor_index(cols, rows, ["Артикул"])


def test_db_row_anchor_composite_normalises() -> None:
    cols = ["Артикул", "Название склейки", "БАРКОД"]
    row = ["wendy/black", "WB-A", "  1234567890  "]
    assert db_row_anchor(cols, row, ["Название склейки", "БАРКОД"]) == ("wb-a", "1234567890")


def test_anchor_index_respects_header_row_offset() -> None:
    cols = ["Артикул"]
    rows = [["wendy/black"]]
    # If the header is actually on row 2 of the sheet, the data row is row 3.
    idx = build_anchor_index(cols, rows, ["Артикул"], header_row=2)
    assert idx == {("wendy/black",): 3}
