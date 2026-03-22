"""Test field service — custom field validation and merge (unit test — no DB)."""
import pytest
from datetime import date

from services.product_matrix_api.services.field_service import (
    FieldService,
    MAX_CUSTOM_FIELDS,
)


# --- validate_value: text ---

def test_validate_custom_value_text():
    assert FieldService.validate_value("text", "hello") == "hello"
    assert FieldService.validate_value("text", 123) == "123"
    assert FieldService.validate_value("text", None) is None


# --- validate_value: number ---

def test_validate_custom_value_number():
    assert FieldService.validate_value("number", "42") == 42
    assert isinstance(FieldService.validate_value("number", "42"), int)
    assert FieldService.validate_value("number", "3.14") == 3.14
    assert isinstance(FieldService.validate_value("number", "3.14"), float)


def test_validate_custom_value_number_invalid():
    with pytest.raises(ValueError, match="Cannot convert"):
        FieldService.validate_value("number", "abc")


# --- validate_value: checkbox ---

def test_validate_custom_value_checkbox():
    assert FieldService.validate_value("checkbox", True) is True
    assert FieldService.validate_value("checkbox", "false") is False
    assert FieldService.validate_value("checkbox", "true") is True
    assert FieldService.validate_value("checkbox", "1") is True
    assert FieldService.validate_value("checkbox", "yes") is True


# --- validate_value: select ---

def test_validate_custom_value_select():
    config = {"options": ["red", "green", "blue"]}
    assert FieldService.validate_value("select", "red", config) == "red"
    with pytest.raises(ValueError, match="not in allowed options"):
        FieldService.validate_value("select", "yellow", config)


# --- validate_value: multi_select ---

def test_validate_custom_value_multi_select():
    config = {"options": ["a", "b", "c"]}
    assert FieldService.validate_value("multi_select", ["a", "b"], config) == ["a", "b"]
    with pytest.raises(ValueError, match="not in allowed options"):
        FieldService.validate_value("multi_select", ["a", "x"], config)
    with pytest.raises(ValueError, match="must be a list"):
        FieldService.validate_value("multi_select", "a", config)


# --- validate_value: url ---

def test_validate_custom_value_url():
    assert FieldService.validate_value("url", "https://example.com") == "https://example.com"
    assert FieldService.validate_value("url", 123) == "123"


# --- validate_value: date ---

def test_validate_custom_value_date():
    assert FieldService.validate_value("date", "2026-01-15") == "2026-01-15"
    assert FieldService.validate_value("date", date(2026, 1, 15)) == "2026-01-15"
    with pytest.raises(ValueError, match="Invalid date"):
        FieldService.validate_value("date", "not-a-date")


# --- merge_custom_fields ---

def test_merge_custom_fields():
    existing = {"color": "red", "size": "M"}
    updates = {"size": "L", "weight": 100}
    result = FieldService.merge_custom_fields(existing, updates)
    assert result == {"color": "red", "size": "L", "weight": 100}


def test_merge_custom_fields_none_removes():
    existing = {"color": "red", "size": "M"}
    updates = {"color": None}
    result = FieldService.merge_custom_fields(existing, updates)
    assert result == {"size": "M"}
    assert "color" not in result


def test_max_custom_fields_exceeded():
    existing = {f"field_{i}": i for i in range(50)}
    updates = {"field_new": "value"}
    with pytest.raises(ValueError, match="Maximum 50"):
        FieldService.merge_custom_fields(existing, updates)
