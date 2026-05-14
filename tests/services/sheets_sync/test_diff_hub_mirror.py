"""Unit tests for services/sheets_sync/hub_to_sheets/diff.py."""
from __future__ import annotations

from services.sheets_sync.hub_to_sheets.diff import diff_sheet


def _ids_kwargs(**overrides):
    """Common defaults shared by most tests."""
    base = dict(
        sheet_name="Все артикулы",
        anchor_cols=("Артикул",),
        status_col="Статус",
        archive_value="Архив",
        header_row=1,
    )
    base.update(overrides)
    return base


def test_noop_when_sheet_matches_db() -> None:
    db_cols = ["Артикул", "Модель", "Статус"]
    db_rows = [["wendy/black", "Wendy", "Продается"]]
    sh_cols = ["Артикул", "Модель", "Статус"]
    sh_rows = [["wendy/black", "Wendy", "Продается"]]
    diff = diff_sheet(
        db_columns=db_cols, db_rows=db_rows,
        sheet_columns=sh_cols, sheet_rows=sh_rows,
        **_ids_kwargs(),
    )
    assert diff.cell_updates == []
    assert diff.row_appends == []
    assert diff.row_deletes == []


def test_new_row_appended() -> None:
    db_cols = ["Артикул", "Модель", "Статус"]
    db_rows = [
        ["wendy/black", "Wendy", "Продается"],
        ["wendy/white", "Wendy", "Продается"],
    ]
    sh_cols = ["Артикул", "Модель", "Статус"]
    sh_rows = [["wendy/black", "Wendy", "Продается"]]
    diff = diff_sheet(
        db_columns=db_cols, db_rows=db_rows,
        sheet_columns=sh_cols, sheet_rows=sh_rows,
        **_ids_kwargs(),
    )
    assert diff.cell_updates == []
    assert len(diff.row_appends) == 1
    assert diff.row_appends[0].values == ("wendy/white", "Wendy", "Продается")


def test_changed_value_produces_cell_update() -> None:
    db_cols = ["Артикул", "Модель", "Статус"]
    db_rows = [["wendy/black", "Wendy", "Выводим"]]
    sh_cols = ["Артикул", "Модель", "Статус"]
    sh_rows = [["wendy/black", "Wendy", "Продается"]]
    diff = diff_sheet(
        db_columns=db_cols, db_rows=db_rows,
        sheet_columns=sh_cols, sheet_rows=sh_rows,
        **_ids_kwargs(),
    )
    assert len(diff.cell_updates) == 1
    u = diff.cell_updates[0]
    assert (u.sheet_name, u.row, u.col, u.value) == ("Все артикулы", 2, 3, "Выводим")


def test_db_empty_does_not_overwrite_sheet() -> None:
    """Rule #2: blank DB cells preserve historical notes in the sheet."""
    db_cols = ["Артикул", "Модель", "Статус"]
    db_rows = [["wendy/black", "Wendy", ""]]  # status blank in DB
    sh_cols = ["Артикул", "Модель", "Статус"]
    sh_rows = [["wendy/black", "Wendy", "Продается"]]  # status present in sheet
    diff = diff_sheet(
        db_columns=db_cols, db_rows=db_rows,
        sheet_columns=sh_cols, sheet_rows=sh_rows,
        **_ids_kwargs(),
    )
    assert diff.cell_updates == []
    assert diff.row_appends == []


def test_missing_in_db_archives_row() -> None:
    db_cols = ["Артикул", "Модель", "Статус"]
    db_rows: list[list[str]] = []
    sh_cols = ["Артикул", "Модель", "Статус"]
    sh_rows = [["wendy/black", "Wendy", "Продается"]]
    diff = diff_sheet(
        db_columns=db_cols, db_rows=db_rows,
        sheet_columns=sh_cols, sheet_rows=sh_rows,
        **_ids_kwargs(),
    )
    assert diff.row_deletes == []
    assert len(diff.cell_updates) == 1
    u = diff.cell_updates[0]
    assert (u.row, u.col, u.value) == (2, 3, "Архив")
    assert diff.archived == 1


def test_already_archived_is_idempotent() -> None:
    db_cols = ["Артикул", "Модель", "Статус"]
    db_rows: list[list[str]] = []
    sh_cols = ["Артикул", "Модель", "Статус"]
    sh_rows = [["wendy/black", "Wendy", "Архив"]]
    diff = diff_sheet(
        db_columns=db_cols, db_rows=db_rows,
        sheet_columns=sh_cols, sheet_rows=sh_rows,
        **_ids_kwargs(),
    )
    assert diff.cell_updates == []
    assert diff.archived == 0


def test_skleyki_missing_in_db_deletes_row() -> None:
    db_cols = ["Название склейки", "БАРКОД", "Артикул"]
    db_rows = [["WB-A", "1111111111", "wendy/black"]]
    sh_cols = ["Название склейки", "БАРКОД", "Артикул"]
    sh_rows = [
        ["WB-A", "1111111111", "wendy/black"],
        ["WB-A", "2222222222", "wendy/white"],  # only in sheet — must delete
    ]
    diff = diff_sheet(
        sheet_name="Склейки WB",
        anchor_cols=("Название склейки", "БАРКОД"),
        status_col=None,
        archive_value="Архив",
        db_columns=db_cols, db_rows=db_rows,
        sheet_columns=sh_cols, sheet_rows=sh_rows,
    )
    assert len(diff.row_deletes) == 1
    assert diff.row_deletes[0].row == 3
    assert diff.deleted == 1


def test_case_insensitive_anchor_match() -> None:
    db_cols = ["Артикул", "Модель", "Статус"]
    db_rows = [["Wendy/Black", "Wendy", "Продается"]]
    sh_cols = ["Артикул", "Модель", "Статус"]
    sh_rows = [["wendy/black", "Wendy", "Продается"]]
    diff = diff_sheet(
        db_columns=db_cols, db_rows=db_rows,
        sheet_columns=sh_cols, sheet_rows=sh_rows,
        **_ids_kwargs(),
    )
    # DB casing differs from sheet; we must update only when the *content*
    # changed, not when only casing differs at the anchor level. Here values
    # match → no updates.
    # However the "Артикул" column itself differs in casing — that produces
    # a CellUpdate (DB value overwrites sheet for non-empty cells).
    upd_for_anchor = [u for u in diff.cell_updates if u.col == 1]
    assert len(upd_for_anchor) == 1
    assert upd_for_anchor[0].value == "Wendy/Black"


def test_view_extra_columns_ignored() -> None:
    """Sheet missing some DB columns: the diff only touches shared ones."""
    db_cols = ["Артикул", "Модель", "Статус", "Внутренний комментарий"]
    db_rows = [["wendy/black", "Wendy", "Продается", "do not push"]]
    sh_cols = ["Артикул", "Модель", "Статус"]
    sh_rows = [["wendy/black", "Wendy", "Продается"]]
    diff = diff_sheet(
        db_columns=db_cols, db_rows=db_rows,
        sheet_columns=sh_cols, sheet_rows=sh_rows,
        **_ids_kwargs(),
    )
    assert diff.cell_updates == []
    assert diff.row_appends == []
