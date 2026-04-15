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


def test_compute_diff_insert():
    from scripts.sync_sheets_to_supabase import compute_diff

    sheets = [{"key": "a", "name": "Alice"}, {"key": "b", "name": "Bob"}]
    supabase = [{"key": "a", "name": "Alice"}]
    result = compute_diff(
        sheets_records=sheets,
        supabase_records=supabase,
        key_field="key",
        compare_fields=["name"],
    )
    assert len(result["to_insert"]) == 1
    assert result["to_insert"][0]["key"] == "b"
    assert len(result["to_update"]) == 0
    assert len(result["to_soft_delete"]) == 0


def test_compute_diff_update():
    from scripts.sync_sheets_to_supabase import compute_diff

    sheets = [{"key": "a", "name": "Alice Updated"}]
    supabase = [{"key": "a", "name": "Alice", "id": 1}]
    result = compute_diff(
        sheets_records=sheets,
        supabase_records=supabase,
        key_field="key",
        compare_fields=["name"],
    )
    assert len(result["to_insert"]) == 0
    assert len(result["to_update"]) == 1
    assert result["to_update"][0]["sheets"]["name"] == "Alice Updated"
    assert result["to_update"][0]["supabase"]["name"] == "Alice"


def test_compute_diff_soft_delete():
    from scripts.sync_sheets_to_supabase import compute_diff

    sheets = []
    supabase = [{"key": "a", "name": "Alice", "id": 1}]
    result = compute_diff(
        sheets_records=sheets,
        supabase_records=supabase,
        key_field="key",
        compare_fields=["name"],
    )
    assert len(result["to_soft_delete"]) == 1
    assert result["to_soft_delete"][0]["key"] == "a"


def test_compute_diff_unchanged():
    from scripts.sync_sheets_to_supabase import compute_diff

    sheets = [{"key": "a", "name": "Alice"}]
    supabase = [{"key": "a", "name": "Alice", "id": 1}]
    result = compute_diff(
        sheets_records=sheets,
        supabase_records=supabase,
        key_field="key",
        compare_fields=["name"],
    )
    assert len(result["to_insert"]) == 0
    assert len(result["to_update"]) == 0
    assert len(result["to_soft_delete"]) == 0
    assert result["unchanged"] == 1


def test_compute_diff_normalize():
    """Keys are normalized (lowercased, trimmed)."""
    from scripts.sync_sheets_to_supabase import compute_diff

    sheets = [{"key": "Vuki/", "name": "Vuki"}]
    supabase = [{"key": "vuki", "name": "Vuki", "id": 1}]
    result = compute_diff(
        sheets_records=sheets,
        supabase_records=supabase,
        key_field="key",
        compare_fields=["name"],
    )
    assert result["unchanged"] == 1
    assert len(result["to_insert"]) == 0
