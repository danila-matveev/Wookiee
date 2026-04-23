"""Тесты reference_sheet writer."""
from unittest.mock import MagicMock
import pytest


def test_reference_sheet_name_constant():
    from services.wb_localization.sheets_export.reference_sheet import REFERENCE_SHEET_NAME
    assert REFERENCE_SHEET_NAME == "Справочник"


def test_write_reference_sheet_calls_clear_and_write():
    from services.wb_localization.sheets_export.reference_sheet import write_reference_sheet
    from services.wb_localization.calculators.reference_builder import build_reference_content

    mock_spreadsheet = MagicMock()
    mock_worksheet = MagicMock()
    mock_worksheet.id = 42
    mock_spreadsheet.worksheet.return_value = mock_worksheet

    content = build_reference_content()
    write_reference_sheet(mock_spreadsheet, content)

    mock_worksheet.clear.assert_called_once()
    assert mock_worksheet.update.call_count >= 1
    assert mock_spreadsheet.batch_update.call_count >= 1


def test_write_reference_creates_sheet_if_missing():
    from gspread.exceptions import WorksheetNotFound
    from services.wb_localization.sheets_export.reference_sheet import write_reference_sheet
    from services.wb_localization.calculators.reference_builder import build_reference_content

    mock_spreadsheet = MagicMock()
    mock_spreadsheet.worksheet.side_effect = WorksheetNotFound()
    new_worksheet = MagicMock()
    new_worksheet.id = 99
    mock_spreadsheet.add_worksheet.return_value = new_worksheet

    content = build_reference_content()
    write_reference_sheet(mock_spreadsheet, content)

    mock_spreadsheet.add_worksheet.assert_called_once()
