"""Cascade validation rules and impact analysis for soft delete."""
from __future__ import annotations

import hashlib
import random
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session


# Whitelist of safe table/column names for SQL interpolation.
# NEVER use user input in SQL — only values from this whitelist.
_SAFE_TABLES = {
    "modeli_osnova", "modeli", "artikuly", "tovary", "cveta",
    "fabriki", "importery", "skleyki_wb", "skleyki_ozon", "sertifikaty",
}
_SAFE_COLUMNS = {
    "model_osnova_id", "model_id", "artikul_id", "cvet_id",
    "fabrika_id", "importer_id", "id", "status_id",
}


def _assert_safe_identifier(name: str, whitelist: set[str]) -> str:
    """Validate that a SQL identifier is in the whitelist. Raises ValueError if not."""
    if name not in whitelist:
        raise ValueError(f"Unsafe SQL identifier: {name!r}")
    return name


CASCADE_RULES: dict[str, dict[str, Any]] = {
    "modeli_osnova": {
        "strategy": "cascade_archive",
        "children": [
            {
                "table": "modeli",
                "fk": "model_osnova_id",
                "children": [
                    {
                        "table": "artikuly",
                        "fk": "model_id",
                        "children": [
                            {"table": "tovary", "fk": "artikul_id"},
                        ],
                    },
                ],
            },
        ],
    },
    "modeli": {
        "strategy": "cascade_archive",
        "children": [
            {
                "table": "artikuly",
                "fk": "model_id",
                "children": [
                    {"table": "tovary", "fk": "artikul_id"},
                ],
            },
        ],
    },
    "artikuly": {
        "strategy": "cascade_archive",
        "children": [
            {"table": "tovary", "fk": "artikul_id"},
        ],
    },
    "cveta": {
        "strategy": "block_if_active",
        "dependents": [
            {"table": "artikuly", "fk": "cvet_id", "active_check": "status_id != 3"},
        ],
    },
    "fabriki": {
        "strategy": "block_if_active",
        "dependents": [
            {"table": "modeli_osnova", "fk": "fabrika_id", "active_check": "status_id IS NULL OR status_id != 3"},
        ],
    },
}

# Archive status ID (from statusy table)
ARCHIVE_STATUS_ID = 3


class ValidationService:
    """Cascade validation and math challenge generation."""

    @staticmethod
    def get_strategy(entity_type: str) -> str:
        """Return the delete strategy for an entity type."""
        rule = CASCADE_RULES.get(entity_type)
        if rule:
            return rule["strategy"]
        return "simple"

    @staticmethod
    def check_delete_impact(
        db: Session, entity_type: str, entity_id: int,
    ) -> dict[str, Any]:
        """Recursively count how many records would be affected by archiving."""
        rule = CASCADE_RULES.get(entity_type)
        if not rule:
            return {"strategy": "simple", "children": {}, "blocked_by": None}

        strategy = rule["strategy"]

        if strategy == "block_if_active":
            blocked_by: dict[str, int] = {}
            for dep in rule.get("dependents", []):
                tbl = _assert_safe_identifier(dep["table"], _SAFE_TABLES)
                fk = _assert_safe_identifier(dep["fk"], _SAFE_COLUMNS)
                # active_check is from hardcoded CASCADE_RULES only
                count = db.execute(
                    text(
                        f"SELECT COUNT(*) FROM {tbl} "
                        f"WHERE {fk} = :eid AND ({dep['active_check']})"
                    ),
                    {"eid": entity_id},
                ).scalar() or 0
                if count > 0:
                    blocked_by[dep["table"]] = count
            return {"strategy": strategy, "children": {}, "blocked_by": blocked_by or None}

        if strategy == "cascade_archive":
            children: dict[str, int] = {}
            ValidationService._count_children(db, rule.get("children", []), entity_id, children)
            return {"strategy": strategy, "children": children, "blocked_by": None}

        return {"strategy": "simple", "children": {}, "blocked_by": None}

    @staticmethod
    def _count_children(
        db: Session,
        children_rules: list[dict],
        parent_id: int,
        result: dict[str, int],
    ) -> None:
        """Recursively count child records."""
        for child in children_rules:
            table = _assert_safe_identifier(child["table"], _SAFE_TABLES)
            fk = _assert_safe_identifier(child["fk"], _SAFE_COLUMNS)
            # Count direct children
            count = db.execute(
                text(f"SELECT COUNT(*) FROM {table} WHERE {fk} = :pid"),
                {"pid": parent_id},
            ).scalar() or 0
            result[table] = result.get(table, 0) + count

            # If there are grandchildren, get child IDs and recurse
            if child.get("children") and count > 0:
                child_ids = db.execute(
                    text(f"SELECT id FROM {table} WHERE {fk} = :pid"),
                    {"pid": parent_id},
                ).scalars().all()
                for cid in child_ids:
                    ValidationService._count_children(
                        db, child["children"], cid, result,
                    )

    @staticmethod
    def generate_challenge() -> tuple[str, str, str]:
        """Generate a math challenge. Returns (challenge_text, expected_hash, salt)."""
        a = random.randint(2, 30)
        b = random.randint(2, 9)
        answer = str(a * b)
        salt = hashlib.sha256(random.randbytes(16)).hexdigest()[:16]
        expected_hash = hashlib.sha256(f"{answer}{salt}".encode()).hexdigest()
        return f"{a} × {b}", expected_hash, salt

    @staticmethod
    def verify_challenge(answer: str, expected_hash: str, salt: str) -> bool:
        """Verify a math challenge answer against the expected hash."""
        computed = hashlib.sha256(f"{answer}{salt}".encode()).hexdigest()
        return computed == expected_hash
