from services.sheets_etl.hash import sheet_row_id


def test_idempotent_same_inputs_same_hash():
    assert sheet_row_id(["a", "b"]) == sheet_row_id(["a", "b"])


def test_normalization_is_case_and_whitespace_insensitive():
    assert sheet_row_id(["Foo "]) == sheet_row_id(["foo"])


def test_different_inputs_different_hash():
    assert sheet_row_id(["a", "b"]) != sheet_row_id(["a", "c"])


def test_hash_is_32_chars_hex():
    h = sheet_row_id(["x"])
    assert len(h) == 32
    int(h, 16)


def test_none_treated_as_empty_string():
    assert sheet_row_id([None, "x"]) == sheet_row_id(["", "x"])
