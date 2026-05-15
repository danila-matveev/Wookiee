"""Unit tests for hub_to_sheets.exporter._to_cell."""
from __future__ import annotations

from services.sheets_sync.hub_to_sheets.exporter import _to_cell


def test_to_cell_collapses_newlines():
    assert _to_cell("a\nb") == "a b"
    assert _to_cell("a\r\nb\r\nc") == "a b c"
    assert _to_cell("a\n\n\nb") == "a b"  # multiple newlines -> single space
    assert _to_cell("  leading and trailing \n  middle  \n end  ") == "leading and trailing middle end"


def test_to_cell_preserves_existing_behavior():
    assert _to_cell(None) == ""
    assert _to_cell(True) == "Да"
    assert _to_cell(False) == "Нет"
    assert _to_cell(26.0) == "26"
    assert _to_cell(26.7) == "26.7"
    assert _to_cell("plain text") == "plain text"
