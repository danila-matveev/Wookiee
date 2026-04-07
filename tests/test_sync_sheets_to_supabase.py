"""Unit tests for sync_sheets_to_supabase diff engine."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_normalize_key():
    from scripts.sync_sheets_to_supabase import normalize_key

    assert normalize_key("Vuki/") == "vuki"
    assert normalize_key("  Moon  ") == "moon"
    assert normalize_key("Ruby") == "ruby"
    assert normalize_key("") == ""
    assert normalize_key("Set Vuki/") == "set vuki"


def test_clean_barcode():
    from scripts.sync_sheets_to_supabase import clean_barcode

    assert clean_barcode("2000989123456") == "2000989123456"
    assert clean_barcode("2000989123456.0") == "2000989123456"
    assert clean_barcode("123") is None  # too short
    assert clean_barcode("") is None
    assert clean_barcode("abc") is None


def test_clean_string():
    from scripts.sync_sheets_to_supabase import clean_string

    assert clean_string("  hello  ") == "hello"
    assert clean_string("") is None
    assert clean_string("nan") is None


def test_clean_numeric():
    from scripts.sync_sheets_to_supabase import clean_numeric

    assert clean_numeric("3.14") == 3.14
    assert clean_numeric("1 234,56") == 1234.56
    assert clean_numeric("") is None
    assert clean_numeric("abc") is None
