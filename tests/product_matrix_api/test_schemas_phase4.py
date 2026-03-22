"""Validate Phase 4 Pydantic schemas: FieldDefinition + SavedView."""
import pytest
from pydantic import ValidationError

from services.product_matrix_api.models.schemas import (
    FieldDefinitionCreate,
    FieldDefinitionRead,
    FieldDefinitionUpdate,
    ViewConfig,
    SavedViewCreate,
    SavedViewRead,
)


# ── FieldDefinitionCreate ────────────────────────────────────────────────────

def test_field_definition_create_valid():
    fd = FieldDefinitionCreate(
        entity_type="modeli_osnova",
        field_name="custom_weight",
        display_name="Custom Weight",
        field_type="number",
    )
    assert fd.entity_type == "modeli_osnova"
    assert fd.field_name == "custom_weight"
    assert fd.field_type == "number"
    assert fd.config is None
    assert fd.sort_order == 0


def test_field_definition_create_with_select_config():
    fd = FieldDefinitionCreate(
        entity_type="artikuly",
        field_name="priority_level",
        display_name="Priority",
        field_type="select",
        config={"options": ["low", "medium", "high"]},
    )
    assert fd.field_type == "select"
    assert fd.config == {"options": ["low", "medium", "high"]}


def test_field_definition_create_invalid_type():
    with pytest.raises(ValidationError, match="field_type"):
        FieldDefinitionCreate(
            entity_type="modeli",
            field_name="bad_field",
            display_name="Bad",
            field_type="invalid_type",
        )


def test_field_definition_create_invalid_name():
    with pytest.raises(ValidationError, match="field_name"):
        FieldDefinitionCreate(
            entity_type="modeli",
            field_name="BadName!",
            display_name="Bad",
            field_type="text",
        )


def test_field_definition_create_invalid_entity_type():
    with pytest.raises(ValidationError, match="entity_type"):
        FieldDefinitionCreate(
            entity_type="nonexistent",
            field_name="ok_field",
            display_name="OK",
            field_type="text",
        )


# ── FieldDefinitionRead ──────────────────────────────────────────────────────

def test_field_definition_read():
    fd = FieldDefinitionRead(
        id=1,
        entity_type="modeli_osnova",
        field_name="custom_weight",
        display_name="Custom Weight",
        field_type="number",
        sort_order=0,
        is_system=False,
        is_visible=True,
    )
    assert fd.id == 1
    assert fd.field_name == "custom_weight"


# ── FieldDefinitionUpdate ────────────────────────────────────────────────────

def test_field_definition_update_partial():
    fd = FieldDefinitionUpdate(display_name="New Name")
    assert fd.display_name == "New Name"
    assert fd.field_type is None


# ── ViewConfig ───────────────────────────────────────────────────────────────

def test_view_config():
    vc = ViewConfig(
        columns=["kod", "nazvanie"],
        filters=[{"field": "status", "op": "eq", "value": "active"}],
        sort=[{"field": "kod", "dir": "asc"}],
    )
    assert len(vc.columns) == 2
    assert vc.group_by is None


# ── SavedViewCreate ──────────────────────────────────────────────────────────

def test_saved_view_create():
    sv = SavedViewCreate(
        entity_type="modeli_osnova",
        name="My View",
        config={"columns": ["kod"], "filters": [], "sort": []},
    )
    assert sv.entity_type == "modeli_osnova"
    assert sv.name == "My View"
    assert sv.is_default is False


def test_saved_view_create_invalid_entity():
    with pytest.raises(ValidationError, match="entity_type"):
        SavedViewCreate(
            entity_type="nonexistent",
            name="Bad View",
            config={"columns": [], "filters": [], "sort": []},
        )


# ── SavedViewRead ────────────────────────────────────────────────────────────

def test_saved_view_read():
    sv = SavedViewRead(
        id=1,
        entity_type="modeli_osnova",
        name="My View",
        config={"columns": ["kod"], "filters": [], "sort": []},
        is_default=False,
        sort_order=0,
    )
    assert sv.id == 1
    assert sv.name == "My View"
