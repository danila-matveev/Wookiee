"""Test that all new SQLAlchemy models can be instantiated."""
from services.product_matrix_api.models.database import (
    FieldDefinition,
    Sertifikat,
    ModelOsnovaSertifikat,
    ArchiveRecord,
    HubUser,
    HubAuditLog,
)


def test_field_definition_instantiation():
    fd = FieldDefinition(
        entity_type="modeli_osnova",
        field_name="test_field",
        display_name="Test Field",
        field_type="text",
    )
    assert fd.entity_type == "modeli_osnova"
    assert fd.field_type == "text"
    assert fd.is_system is False
    assert fd.is_visible is True


def test_sertifikat_instantiation():
    s = Sertifikat(nazvanie="ЕАС Декларация", tip="EAC")
    assert s.nazvanie == "ЕАС Декларация"


def test_archive_record_instantiation():
    ar = ArchiveRecord(
        original_table="modeli_osnova",
        original_id=1,
        full_record={"kod": "Vuki"},
    )
    assert ar.original_table == "modeli_osnova"
    assert ar.restore_available is True


def test_hub_user_instantiation():
    u = HubUser(email="test@test.com", name="Test")
    assert u.role == "viewer"
    assert u.is_active is True


def test_hub_audit_log_instantiation():
    log = HubAuditLog(action="create", entity_type="modeli_osnova", entity_id=1)
    assert log.action == "create"
