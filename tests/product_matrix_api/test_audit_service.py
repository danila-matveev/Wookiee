"""Test audit service (unit test — no DB)."""
from services.product_matrix_api.services.audit_service import AuditService


def test_diff_changes():
    old = {"kod": "Vuki", "material": "Cotton"}
    new = {"kod": "Vuki", "material": "Silk"}
    diff = AuditService.diff_changes(old, new)
    assert diff == {"material": {"old": "Cotton", "new": "Silk"}}


def test_diff_changes_no_change():
    old = {"kod": "Vuki"}
    new = {"kod": "Vuki"}
    diff = AuditService.diff_changes(old, new)
    assert diff == {}


def test_diff_changes_ignores_none_to_none():
    old = {"kod": "Vuki", "material": None}
    new = {"kod": "Vuki", "material": None}
    diff = AuditService.diff_changes(old, new)
    assert diff == {}
