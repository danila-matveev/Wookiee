"""Audit logging service — writes entries to hub.audit_log."""
from __future__ import annotations

import logging
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger("product_matrix_api.audit")


class AuditService:
    """Writes audit log entries to hub.audit_log table."""

    @staticmethod
    def diff_changes(
        old: dict[str, Any], new: dict[str, Any]
    ) -> dict[str, dict[str, Any]]:
        """Compare two dicts, return {field: {old, new}} for changed fields."""
        changes = {}
        for key in new:
            old_val = old.get(key)
            new_val = new.get(key)
            if old_val != new_val:
                changes[key] = {"old": old_val, "new": new_val}
        return changes

    @staticmethod
    def log(
        db: Session,
        *,
        action: str,
        entity_type: str,
        entity_id: Optional[int] = None,
        entity_name: Optional[str] = None,
        changes: Optional[dict] = None,
        user_email: str = "anonymous",
        request_id: Optional[str] = None,
    ) -> None:
        """Insert an audit log entry into hub.audit_log."""
        import json

        db.execute(
            text("""
                INSERT INTO hub.audit_log
                    (user_email, action, entity_type, entity_id, entity_name, changes, request_id)
                VALUES
                    (:user_email, :action, :entity_type, :entity_id, :entity_name,
                     :changes::jsonb, :request_id)
            """),
            {
                "user_email": user_email,
                "action": action,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "entity_name": entity_name,
                "changes": json.dumps(changes) if changes else None,
                "request_id": request_id,
            },
        )
