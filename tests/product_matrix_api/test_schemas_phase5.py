"""Tests for Phase 5 Pydantic schemas (delete, archive, admin)."""
import pytest
from pydantic import ValidationError

from services.product_matrix_api.models.schemas import (
    DeleteImpact,
    DeleteChallenge,
    ArchiveRecordRead,
    DbStats,
    TableStats,
)


def test_delete_impact_valid():
    impact = DeleteImpact(
        entity_type="modeli_osnova",
        entity_id=1,
        entity_name="WK-001",
        strategy="cascade_archive",
        children={"modeli": 4, "artikuly": 52, "tovary": 208},
        message="Будут архивированы: 4 подмодели, 52 артикула, 208 SKU",
    )
    assert impact.children["modeli"] == 4
    assert impact.strategy == "cascade_archive"


def test_delete_impact_block_strategy():
    impact = DeleteImpact(
        entity_type="cveta",
        entity_id=5,
        entity_name="Чёрный",
        strategy="block_if_active",
        children={},
        blocked_by={"artikuly": 12},
        message="Нельзя удалить: 12 активных артикулов используют этот цвет",
    )
    assert impact.blocked_by["artikuly"] == 12


def test_delete_challenge():
    challenge = DeleteChallenge(
        requires_confirmation=True,
        challenge="27 × 3",
        expected_hash="abc123",
        impact=DeleteImpact(
            entity_type="modeli_osnova",
            entity_id=1,
            entity_name="WK-001",
            strategy="cascade_archive",
            children={"modeli": 2},
            message="Будут архивированы: 2 подмодели",
        ),
    )
    assert challenge.requires_confirmation is True
    assert challenge.challenge == "27 × 3"


def test_archive_record_read():
    rec = ArchiveRecordRead(
        id=1,
        original_table="modeli_osnova",
        original_id=42,
        full_record={"kod": "WK-001"},
        related_records=[],
        deleted_by="user@test.com",
        deleted_at="2026-03-21T12:00:00",
        expires_at="2026-04-20T12:00:00",
        restore_available=True,
    )
    assert rec.original_table == "modeli_osnova"
    assert rec.restore_available is True


def test_db_stats():
    stats = DbStats(
        tables=[
            TableStats(name="modeli_osnova", count=150, growth_week=5, growth_month=20),
            TableStats(name="tovary", count=3200, growth_week=100, growth_month=350),
        ],
        total_records=5000,
    )
    assert len(stats.tables) == 2
    assert stats.total_records == 5000
