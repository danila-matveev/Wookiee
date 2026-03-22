"""Archive service — soft delete (snapshot to archive_records), restore, expire."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from services.product_matrix_api.models.database import ArchiveRecord
from services.product_matrix_api.services.validation import (
    CASCADE_RULES, ARCHIVE_STATUS_ID,
    _assert_safe_identifier, _SAFE_TABLES, _SAFE_COLUMNS,
)

logger = logging.getLogger("product_matrix_api.archive")

# Table display names for messages
TABLE_LABELS: dict[str, str] = {
    "modeli_osnova": "моделей основы",
    "modeli": "подмоделей",
    "artikuly": "артикулов",
    "tovary": "SKU",
    "cveta": "цветов",
    "fabriki": "фабрик",
    "importery": "импортёров",
    "skleyki_wb": "склеек WB",
    "skleyki_ozon": "склеек Ozon",
    "sertifikaty": "сертификатов",
}


class ArchiveService:
    """Soft-delete records to archive_records, restore, expire."""

    @staticmethod
    def build_impact_message(
        strategy: str,
        children: dict[str, int],
        blocked_by: Optional[dict[str, int]] = None,
    ) -> str:
        """Build a human-readable impact message."""
        if strategy == "block_if_active" and blocked_by:
            parts = []
            for table, count in blocked_by.items():
                label = TABLE_LABELS.get(table, table)
                parts.append(f"{count} {label}")
            return f"Нельзя удалить: активные зависимости — {', '.join(parts)}"

        if strategy == "cascade_archive" and children:
            parts = []
            for table, count in children.items():
                label = TABLE_LABELS.get(table, table)
                parts.append(f"{count} {label}")
            return f"Будут архивированы: {', '.join(parts)}"

        return "Запись будет удалена (без зависимостей)"

    @staticmethod
    def compute_expires_at(now: Optional[datetime] = None, days: int = 30) -> datetime:
        """Compute expiry date from now + days."""
        base = now or datetime.utcnow()
        return base + timedelta(days=days)

    @staticmethod
    def archive_entity(
        db: Session,
        entity_type: str,
        entity_id: int,
        deleted_by: str = "anonymous",
    ) -> ArchiveRecord:
        """Archive a single entity: snapshot → archive_records, set status_id=3."""
        safe_table = _assert_safe_identifier(entity_type, _SAFE_TABLES)

        # Fetch full record as dict
        row = db.execute(
            text(f"SELECT * FROM {safe_table} WHERE id = :eid"),
            {"eid": entity_id},
        ).mappings().first()
        if not row:
            raise ValueError(f"Record {entity_type}#{entity_id} not found")

        full_record = {k: _serialize(v) for k, v in dict(row).items()}

        # Collect related records if cascade
        related_records = []
        rule = CASCADE_RULES.get(entity_type)
        if rule and rule["strategy"] == "cascade_archive":
            related_records = ArchiveService._collect_and_archive_children(
                db, rule.get("children", []), entity_id, deleted_by,
            )

        # Set status_id = ARCHIVE on main record (if column exists)
        try:
            db.execute(
                text(f"UPDATE {safe_table} SET status_id = :sid WHERE id = :eid"),
                {"sid": ARCHIVE_STATUS_ID, "eid": entity_id},
            )
        except Exception:
            pass

        # Create archive record
        expires_at = ArchiveService.compute_expires_at()
        archive = ArchiveRecord(
            original_table=entity_type,
            original_id=entity_id,
            full_record=full_record,
            related_records=related_records,
            deleted_by=deleted_by,
            expires_at=expires_at,
            restore_available=True,
        )
        db.add(archive)
        db.flush()
        db.refresh(archive)
        return archive

    @staticmethod
    def _collect_and_archive_children(
        db: Session,
        children_rules: list[dict],
        parent_id: int,
        deleted_by: str,
    ) -> list[dict]:
        """Recursively archive child records. Returns list of {table, id, record} dicts."""
        collected = []
        for child in children_rules:
            table = _assert_safe_identifier(child["table"], _SAFE_TABLES)
            fk = _assert_safe_identifier(child["fk"], _SAFE_COLUMNS)
            rows = db.execute(
                text(f"SELECT * FROM {table} WHERE {fk} = :pid"),
                {"pid": parent_id},
            ).mappings().all()

            for row in rows:
                record_dict = {k: _serialize(v) for k, v in dict(row).items()}
                child_id = record_dict["id"]
                collected.append({
                    "table": child["table"],
                    "id": child_id,
                    "record": record_dict,
                })
                # Set status_id = ARCHIVE
                try:
                    db.execute(
                        text(f"UPDATE {table} SET status_id = :sid WHERE id = :eid"),
                        {"sid": ARCHIVE_STATUS_ID, "eid": child_id},
                    )
                except Exception:
                    pass
                # Recurse
                if child.get("children"):
                    collected.extend(
                        ArchiveService._collect_and_archive_children(
                            db, child["children"], child_id, deleted_by,
                        )
                    )
        return collected

    @staticmethod
    def restore_record(db: Session, archive_id: int) -> dict[str, Any]:
        """Restore an archived record: revert status_id, restore children, remove from archive."""
        archive = db.get(ArchiveRecord, archive_id)
        if not archive:
            raise ValueError(f"Archive record #{archive_id} not found")
        if not archive.restore_available:
            raise ValueError("This record is no longer restorable")

        table = _assert_safe_identifier(archive.original_table, _SAFE_TABLES)
        eid = archive.original_id
        original = archive.full_record

        # Restore main record status
        old_status = original.get("status_id")
        restore_status = old_status if old_status and old_status != ARCHIVE_STATUS_ID else 1
        try:
            db.execute(
                text(f"UPDATE {table} SET status_id = :sid WHERE id = :eid"),
                {"sid": restore_status, "eid": eid},
            )
        except Exception:
            pass

        # Restore children
        for related in (archive.related_records or []):
            child_table = _assert_safe_identifier(related["table"], _SAFE_TABLES)
            child_id = related["id"]
            child_record = related["record"]
            child_old_status = child_record.get("status_id")
            child_restore = child_old_status if child_old_status and child_old_status != ARCHIVE_STATUS_ID else 1
            try:
                db.execute(
                    text(f"UPDATE {child_table} SET status_id = :sid WHERE id = :eid"),
                    {"sid": child_restore, "eid": child_id},
                )
            except Exception:
                pass

        # Delete archive record
        db.delete(archive)
        db.flush()

        return {"restored": True, "table": archive.original_table, "id": eid}

    @staticmethod
    def hard_delete_archived(db: Session, archive_id: int) -> dict[str, Any]:
        """Permanently delete an archived record and its children (bottom-up)."""
        archive = db.get(ArchiveRecord, archive_id)
        if not archive:
            raise ValueError(f"Archive record #{archive_id} not found")

        table = _assert_safe_identifier(archive.original_table, _SAFE_TABLES)
        eid = archive.original_id

        # Delete children bottom-up
        for related in reversed(archive.related_records or []):
            try:
                rel_table = _assert_safe_identifier(related["table"], _SAFE_TABLES)
                db.execute(
                    text(f"DELETE FROM {rel_table} WHERE id = :eid"),
                    {"eid": related["id"]},
                )
            except Exception as e:
                logger.warning("Failed to hard-delete %s#%s: %s", related["table"], related["id"], e)

        # Delete main record
        try:
            db.execute(
                text(f"DELETE FROM {table} WHERE id = :eid"),
                {"eid": eid},
            )
        except Exception as e:
            logger.warning("Failed to hard-delete %s#%s: %s", archive.original_table, eid, e)

        # Remove archive entry
        db.delete(archive)
        db.flush()

        return {"deleted": True, "table": archive.original_table, "id": eid}

    @staticmethod
    def expire_old_records(db: Session) -> int:
        """Delete archive records past their expiry date. Returns count deleted."""
        expired = db.execute(
            text("SELECT id FROM archive_records WHERE expires_at < NOW() AND restore_available = true")
        ).scalars().all()

        count = 0
        for aid in expired:
            try:
                ArchiveService.hard_delete_archived(db, aid)
                count += 1
            except Exception as e:
                logger.warning("Failed to expire archive #%s: %s", aid, e)
        return count


def _serialize(value: Any) -> Any:
    """Make a value JSON-serializable."""
    from datetime import date
    from decimal import Decimal
    from uuid import UUID

    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value
