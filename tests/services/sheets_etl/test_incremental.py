from services.sheets_etl.incremental import filter_new_rows


def test_filter_new_rows_skips_existing():
    rows = [
        {"sheet_row_id": "a", "name": "x"},
        {"sheet_row_id": "b", "name": "y"},
        {"sheet_row_id": "c", "name": "z"},
    ]
    existing = {"a", "c"}
    out = filter_new_rows(rows, existing)
    assert out == [{"sheet_row_id": "b", "name": "y"}]


def test_filter_new_rows_passthrough_when_no_id():
    rows = [{"name": "no-id-row"}]
    existing = {"a"}
    assert filter_new_rows(rows, existing) == rows


def test_filter_new_rows_empty_existing():
    rows = [{"sheet_row_id": "a"}, {"sheet_row_id": "b"}]
    assert filter_new_rows(rows, set()) == rows
