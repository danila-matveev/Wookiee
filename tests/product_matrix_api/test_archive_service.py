"""Tests for archive service — snapshot creation, message formatting."""
from datetime import datetime, timedelta

from services.product_matrix_api.services.archive_service import ArchiveService


def test_build_impact_message_cascade():
    children = {"modeli": 4, "artikuly": 52, "tovary": 208}
    msg = ArchiveService.build_impact_message("cascade_archive", children)
    assert "4" in msg
    assert "52" in msg
    assert "208" in msg


def test_build_impact_message_simple():
    msg = ArchiveService.build_impact_message("simple", {})
    assert "без зависимостей" in msg.lower() or "удалена" in msg.lower()


def test_build_impact_message_blocked():
    msg = ArchiveService.build_impact_message(
        "block_if_active", {}, blocked_by={"artikuly": 12}
    )
    assert "12" in msg
    assert "артикул" in msg.lower() or "artikul" in msg.lower()


def test_compute_expires_at():
    now = datetime(2026, 3, 21, 12, 0, 0)
    expires = ArchiveService.compute_expires_at(now, days=30)
    assert expires == datetime(2026, 4, 20, 12, 0, 0)


def test_compute_expires_at_default():
    now = datetime(2026, 1, 1)
    expires = ArchiveService.compute_expires_at(now)
    assert expires == datetime(2026, 1, 31)
