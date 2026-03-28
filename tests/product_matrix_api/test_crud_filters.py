# tests/product_matrix_api/test_crud_filters.py
"""Unit tests for CrudService._build_filters — IN-clause and scalar equality."""
from unittest.mock import MagicMock, patch

import pytest

from services.product_matrix_api.services.crud import CrudService


# ── Fake SQLAlchemy model for testing ────────────────────────────────────────

class _FakeCol:
    """Minimal column mock that supports == and in_()."""

    def __init__(self, name: str):
        self.name = name
        self._eq_value = None
        self._in_values = None

    def __eq__(self, other):  # noqa: D105
        sentinel = MagicMock()
        sentinel._type = "eq"
        sentinel._value = other
        return sentinel

    def in_(self, values):
        sentinel = MagicMock()
        sentinel._type = "in"
        sentinel._values = list(values)
        return sentinel


class FakeMapper:
    """Mimics inspect(model).column_attrs."""

    def __init__(self, cols):
        self.column_attrs = [type("CA", (), {"key": c})() for c in cols]


class FakeORM:
    """Mimics a SQLAlchemy ORM model with __mapper__."""

    __mapper__ = True

    kategoriya_id = _FakeCol("kategoriya_id")
    status_id = _FakeCol("status_id")
    kod = _FakeCol("kod")


# ── Tests ─────────────────────────────────────────────────────────────────────

def _build(filters: dict):
    """Helper: call _build_filters with FakeORM and return conditions."""
    fake_mapper = FakeMapper(["kategoriya_id", "status_id", "kod"])
    with patch("services.product_matrix_api.services.crud.inspect", return_value=fake_mapper):
        return CrudService._build_filters(FakeORM, filters)


def test_build_filters_scalar_equality():
    """Single integer value should produce == condition (not in_())."""
    conditions = _build({"status_id": 1})
    assert len(conditions) == 1
    # The condition came from __eq__ (scalar path), not in_()
    cond = conditions[0]
    # MagicMock from __eq__ has _type attribute set to "eq"
    assert cond._value == 1


def test_build_filters_list_in_clause():
    """List value should produce in_() condition."""
    conditions = _build({"kategoriya_id": [1, 5]})
    assert len(conditions) == 1
    cond = conditions[0]
    assert cond._type == "in"
    assert cond._values == [1, 5]


def test_build_filters_empty_list_skipped():
    """Empty list should produce no condition (skipped entirely)."""
    conditions = _build({"kategoriya_id": []})
    assert len(conditions) == 0


def test_build_filters_ignores_unknown_field():
    """Unknown field name (not in column_attrs) should be silently skipped."""
    conditions = _build({"nonexistent_field": 99})
    assert len(conditions) == 0


def test_build_filters_none_value_skipped():
    """None value should be skipped regardless of field type."""
    conditions = _build({"status_id": None})
    assert len(conditions) == 0


def test_build_filters_multiple_scalars():
    """Multiple scalar filters should all produce == conditions."""
    conditions = _build({"status_id": 2, "kod": "abc"})
    assert len(conditions) == 2


def test_build_filters_mixed_scalar_and_list():
    """Mix of scalar and list should produce == and in_() respectively."""
    conditions = _build({"status_id": 3, "kategoriya_id": [1, 2, 3]})
    assert len(conditions) == 2
    types = {c._type for c in conditions}
    assert "in" in types
    # scalar yields _value attribute (from __eq__)
    eq_conds = [c for c in conditions if not hasattr(c, "_type") or c._type != "in"]
    assert len(eq_conds) == 1
