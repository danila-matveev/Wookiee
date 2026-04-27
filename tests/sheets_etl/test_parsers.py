from decimal import Decimal
from datetime import date

from services.sheets_etl.parsers import parse_bool, parse_date, parse_decimal, parse_int


def test_parse_int_handles_russian_thousands_separators():
    assert parse_int("1 286") == 1286
    assert parse_int("1\xa0286") == 1286
    assert parse_int("1 286") == 1286


def test_parse_int_returns_none_for_empty_or_dash():
    assert parse_int("") is None
    assert parse_int("—") is None
    assert parse_int(None) is None


def test_parse_decimal_comma_as_decimal_separator():
    assert parse_decimal("419,68") == Decimal("419.68")


def test_parse_decimal_strips_percent():
    assert parse_decimal("12%") == Decimal("12")


def test_parse_date_supports_dotted_ru_format():
    assert parse_date("01.09.2025") == date(2025, 9, 1)
    assert parse_date("01.09.25") == date(2025, 9, 1)


def test_parse_date_returns_none_for_garbage():
    assert parse_date("not a date") is None


def test_parse_bool_russian():
    assert parse_bool("да") is True
    assert parse_bool("нет") is False
    assert parse_bool("✓") is True
    assert parse_bool("") is None
