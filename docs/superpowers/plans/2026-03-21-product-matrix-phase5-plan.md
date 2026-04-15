# Product Matrix Phase 5: Safety & Admin — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add two-step delete with math challenge, cascade archive logic, archive CRUD, and an admin panel (Schema Explorer, API Explorer, Audit Logs, Archive Manager, DB Stats).

**Architecture:** Three layers — (1) Backend: `validation.py` service with CASCADE_RULES, `archive_service.py` for soft-delete/restore/expire, archive + admin routes; (2) API contract: DELETE returns 428 with impact preview, second call with `X-Confirm-Challenge` header archives the record; (3) Frontend: `DeleteConfirmDialog` + `DeleteChallengeDialog` for two-step delete, 5 admin pages under `/system/matrix-admin/*`.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic v2, React 19, Zustand, TypeScript, Tailwind, shadcn/ui

**Note:** SchemaExplorerPage and ApiExplorerPage are delivered as stubs in this phase (navigation + placeholder). Full implementations are deferred to Phase 6. Auto-expire cron for archive records is also deferred (the `expire_old_records()` method exists but needs a scheduler — Phase 6 or ops task).

---

## File Structure

### Backend (new files)

| File | Responsibility |
|------|----------------|
| `services/product_matrix_api/services/validation.py` | CASCADE_RULES dict, `check_delete_impact()` — counts affected children, `can_delete()` — block_if_active check |
| `services/product_matrix_api/services/archive_service.py` | `archive_record()` — snapshot + status→3, `cascade_archive()` — recursive, `restore_record()`, `hard_delete()`, `expire_old()` |
| `services/product_matrix_api/routes/archive.py` | `/api/matrix/archive` — list, restore, hard-delete |
| `services/product_matrix_api/routes/admin.py` | `/api/matrix/admin` — audit logs, db stats, health |
| `services/product_matrix_api/routes/delete.py` | `/api/matrix/{entity_type}/{id}` DELETE — two-step with challenge |
| `tests/product_matrix_api/test_validation.py` | Tests for CASCADE_RULES and impact checking |
| `tests/product_matrix_api/test_archive_service.py` | Tests for archive/restore/expire logic |
| `tests/product_matrix_api/test_delete_routes.py` | Tests for two-step delete flow |
| `tests/product_matrix_api/test_archive_routes.py` | Tests for archive CRUD routes |
| `tests/product_matrix_api/test_admin_routes.py` | Tests for admin endpoints |

### Backend (modified files)

| File | Changes |
|------|---------|
| `services/product_matrix_api/models/schemas.py` | Add `DeleteImpact`, `DeleteChallenge`, `ArchiveRecordRead`, `AuditLogFilter`, `DbStats` schemas |
| `services/product_matrix_api/app.py` | Register archive, admin, delete routers |

### Frontend (new files)

| File | Responsibility |
|------|----------------|
| `wookiee-hub/src/components/matrix/delete-confirm-dialog.tsx` | Step 1: shows impact preview, asks "are you sure?" |
| `wookiee-hub/src/components/matrix/delete-challenge-dialog.tsx` | Step 2: math challenge input, sends DELETE with X-Confirm-Challenge |
| `wookiee-hub/src/pages/system/matrix-admin-layout.tsx` | Admin layout with sidebar nav (Schema, API, Logs, Archive, Stats) |
| `wookiee-hub/src/pages/system/schema-explorer-page.tsx` | Tables, columns, types, relations browser |
| `wookiee-hub/src/pages/system/api-explorer-page.tsx` | Endpoint list with descriptions and test requests |
| `wookiee-hub/src/pages/system/audit-log-page.tsx` | Audit log table with filters |
| `wookiee-hub/src/pages/system/archive-manager-page.tsx` | Deleted records list, restore/hard-delete actions |
| `wookiee-hub/src/pages/system/db-stats-page.tsx` | Table record counts, growth metrics |

### Frontend (modified files)

| File | Changes |
|------|---------|
| `wookiee-hub/src/lib/matrix-api.ts` | Add delete, archive, admin API methods |
| `wookiee-hub/src/lib/api-client.ts` | Add `httpDeleteWithHeaders()` for custom headers, `httpDeleteJson()` for JSON response |
| `wookiee-hub/src/router.tsx` | Add `/system/matrix-admin/*` routes |
| `wookiee-hub/src/stores/navigation.ts` | Add admin nav items under System section |

---

## Task 1: Pydantic Schemas for Phase 5

**Files:**
- Modify: `services/product_matrix_api/models/schemas.py`
- Test: `tests/product_matrix_api/test_schemas_phase5.py`

- [ ] **Step 1: Write tests for new schemas**

Create `tests/product_matrix_api/test_schemas_phase5.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee && python3 -m pytest tests/product_matrix_api/test_schemas_phase5.py -v`
Expected: FAIL with ImportError (schemas not yet defined)

- [ ] **Step 3: Add schemas to schemas.py**

Append to `services/product_matrix_api/models/schemas.py` (after `SavedViewRead`):

```python
# ── Phase 5: Delete / Archive / Admin ────────────────────────────────────────

class DeleteImpact(BaseModel):
    entity_type: str
    entity_id: int
    entity_name: str
    strategy: str  # "cascade_archive" | "block_if_active" | "simple"
    children: dict[str, int] = {}
    blocked_by: Optional[dict[str, int]] = None
    message: str


class DeleteChallenge(BaseModel):
    requires_confirmation: bool = True
    challenge: str  # e.g. "27 × 3"
    expected_hash: str  # sha256(answer + salt)
    impact: DeleteImpact


class ArchiveRecordRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    original_table: str
    original_id: int
    full_record: dict
    related_records: Optional[list] = None
    deleted_by: Optional[str] = None
    deleted_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    restore_available: bool = True


class TableStats(BaseModel):
    name: str
    count: int
    growth_week: int = 0
    growth_month: int = 0


class DbStats(BaseModel):
    tables: list[TableStats]
    total_records: int
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee && python3 -m pytest tests/product_matrix_api/test_schemas_phase5.py -v`
Expected: all 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add services/product_matrix_api/models/schemas.py tests/product_matrix_api/test_schemas_phase5.py
git commit -m "feat(matrix-api): add Phase 5 Pydantic schemas (delete, archive, admin)"
```

---

## Task 2: Validation Service (CASCADE_RULES + Impact Check)

**Files:**
- Create: `services/product_matrix_api/services/validation.py`
- Test: `tests/product_matrix_api/test_validation.py`

- [ ] **Step 1: Write tests for validation service**

Create `tests/product_matrix_api/test_validation.py`:

```python
"""Tests for cascade validation rules and impact checking."""
import pytest

from services.product_matrix_api.services.validation import (
    CASCADE_RULES,
    ValidationService,
)


def test_cascade_rules_has_modeli_osnova():
    assert "modeli_osnova" in CASCADE_RULES
    assert CASCADE_RULES["modeli_osnova"]["strategy"] == "cascade_archive"


def test_cascade_rules_has_cveta():
    assert "cveta" in CASCADE_RULES
    assert CASCADE_RULES["cveta"]["strategy"] == "block_if_active"


def test_cascade_rules_has_fabriki():
    assert "fabriki" in CASCADE_RULES
    assert CASCADE_RULES["fabriki"]["strategy"] == "block_if_active"


def test_simple_entity_returns_simple():
    """Entities not in CASCADE_RULES default to 'simple' strategy."""
    strategy = ValidationService.get_strategy("sertifikaty")
    assert strategy == "simple"


def test_cascade_entity_returns_cascade():
    strategy = ValidationService.get_strategy("modeli_osnova")
    assert strategy == "cascade_archive"


def test_block_entity_returns_block():
    strategy = ValidationService.get_strategy("cveta")
    assert strategy == "block_if_active"


def test_generate_challenge():
    """Challenge generates a math problem and correct answer hash."""
    challenge_text, expected_hash, salt = ValidationService.generate_challenge()
    # Challenge should be in format "X × Y"
    assert "×" in challenge_text
    parts = challenge_text.split("×")
    a, b = int(parts[0].strip()), int(parts[1].strip())
    answer = str(a * b)
    # Hash should be sha256(answer + salt)
    import hashlib
    expected = hashlib.sha256(f"{answer}{salt}".encode()).hexdigest()
    assert expected_hash == expected


def test_verify_challenge_correct():
    challenge_text, expected_hash, salt = ValidationService.generate_challenge()
    parts = challenge_text.split("×")
    a, b = int(parts[0].strip()), int(parts[1].strip())
    answer = str(a * b)
    assert ValidationService.verify_challenge(answer, expected_hash, salt) is True


def test_verify_challenge_wrong():
    _, expected_hash, salt = ValidationService.generate_challenge()
    assert ValidationService.verify_challenge("99999", expected_hash, salt) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee && python3 -m pytest tests/product_matrix_api/test_validation.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Implement validation service**

Create `services/product_matrix_api/services/validation.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee && python3 -m pytest tests/product_matrix_api/test_validation.py -v`
Expected: all 8 tests PASS

- [ ] **Step 5: Commit**

```bash
git add services/product_matrix_api/services/validation.py tests/product_matrix_api/test_validation.py
git commit -m "feat(matrix-api): add validation service with CASCADE_RULES and math challenge"
```

---

## Task 3: Archive Service (Soft Delete + Restore + Expire)

**Files:**
- Create: `services/product_matrix_api/services/archive_service.py`
- Test: `tests/product_matrix_api/test_archive_service.py`

- [ ] **Step 1: Write tests for archive service**

Create `tests/product_matrix_api/test_archive_service.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee && python3 -m pytest tests/product_matrix_api/test_archive_service.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Implement archive service**

Create `services/product_matrix_api/services/archive_service.py`:

```python
"""Archive service — soft delete (snapshot to archive_records), restore, expire."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from services.product_matrix_api.models.database import ArchiveRecord
from services.product_matrix_api.services.validation import (
    CASCADE_RULES, ARCHIVE_STATUS_ID, ValidationService,
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
        # Fetch full record as dict
        safe_table = _assert_safe_identifier(entity_type, _SAFE_TABLES)
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
            # Some tables may not have status_id — that's fine
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
                    "table": table,
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

        return {"restored": True, "table": table, "id": eid}

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
            logger.warning("Failed to hard-delete %s#%s: %s", table, eid, e)

        # Remove archive entry
        db.delete(archive)
        db.flush()

        return {"deleted": True, "table": table, "id": eid}

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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee && python3 -m pytest tests/product_matrix_api/test_archive_service.py -v`
Expected: all 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add services/product_matrix_api/services/archive_service.py tests/product_matrix_api/test_archive_service.py
git commit -m "feat(matrix-api): add archive service for soft delete, restore, and expiry"
```

---

## Task 4: Delete Route (Two-Step with Math Challenge)

**Files:**
- Create: `services/product_matrix_api/routes/delete.py`
- Test: `tests/product_matrix_api/test_delete_routes.py`

- [ ] **Step 1: Write tests for delete route**

Create `tests/product_matrix_api/test_delete_routes.py`:

```python
"""Tests for two-step delete route (428 challenge → archive)."""
import json
import hashlib
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from services.product_matrix_api.app import app

client = TestClient(app)


def test_delete_without_challenge_returns_428():
    """Step 1: DELETE without X-Confirm-Challenge returns 428 with challenge."""
    with patch("services.product_matrix_api.routes.delete.get_db") as mock_db, \
         patch("services.product_matrix_api.routes.delete.ValidationService") as mock_vs, \
         patch("services.product_matrix_api.routes.delete.ArchiveService") as mock_as:

        # Mock: record exists
        mock_session = MagicMock()
        mock_db.return_value = iter([mock_session])
        mock_session.execute.return_value.mappings.return_value.first.return_value = {
            "id": 1, "kod": "WK-001"
        }

        # Mock: impact check
        mock_vs.check_delete_impact.return_value = {
            "strategy": "cascade_archive",
            "children": {"modeli": 2},
            "blocked_by": None,
        }
        mock_vs.generate_challenge.return_value = ("5 × 3", "hash123", "salt123")
        mock_as.build_impact_message.return_value = "Будут архивированы: 2 подмоделей"

        resp = client.delete("/api/matrix/modeli_osnova/1")
        assert resp.status_code == 428
        data = resp.json()
        assert data["requires_confirmation"] is True
        assert "challenge" in data
        assert "impact" in data


def test_delete_blocked_returns_409():
    """block_if_active entities return 409 Conflict."""
    with patch("services.product_matrix_api.routes.delete.get_db") as mock_db, \
         patch("services.product_matrix_api.routes.delete.ValidationService") as mock_vs, \
         patch("services.product_matrix_api.routes.delete.ArchiveService") as mock_as:

        mock_session = MagicMock()
        mock_db.return_value = iter([mock_session])
        mock_session.execute.return_value.mappings.return_value.first.return_value = {
            "id": 5, "color_code": "BLK"
        }

        mock_vs.check_delete_impact.return_value = {
            "strategy": "block_if_active",
            "children": {},
            "blocked_by": {"artikuly": 12},
        }
        mock_as.build_impact_message.return_value = "Нельзя удалить"

        resp = client.delete("/api/matrix/cveta/5")
        assert resp.status_code == 409


def test_delete_not_found_returns_404():
    """DELETE on non-existent record returns 404."""
    with patch("services.product_matrix_api.routes.delete.get_db") as mock_db:
        mock_session = MagicMock()
        mock_db.return_value = iter([mock_session])
        mock_session.execute.return_value.mappings.return_value.first.return_value = None

        resp = client.delete("/api/matrix/modeli_osnova/99999")
        assert resp.status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee && python3 -m pytest tests/product_matrix_api/test_delete_routes.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Implement delete route**

Create `services/product_matrix_api/routes/delete.py`:

```python
"""Two-step delete route: 428 challenge → archive on confirmation."""
from __future__ import annotations

import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from services.product_matrix_api.config import get_db
from services.product_matrix_api.dependencies import CurrentUser, get_current_user
from services.product_matrix_api.models.schemas import (
    VALID_ENTITY_TYPES, DeleteChallenge, DeleteImpact,
)
from services.product_matrix_api.services.validation import ValidationService
from services.product_matrix_api.services.archive_service import ArchiveService
from services.product_matrix_api.services.audit_service import AuditService

logger = logging.getLogger("product_matrix_api.routes.delete")

router = APIRouter(prefix="/api/matrix", tags=["delete"])

# Name fields per entity (for display)
ENTITY_NAME_FIELDS: dict[str, str] = {
    "modeli_osnova": "kod",
    "modeli": "kod",
    "artikuly": "artikul",
    "tovary": "barkod",
    "cveta": "color_code",
    "fabriki": "nazvanie",
    "importery": "nazvanie",
    "skleyki_wb": "nazvanie",
    "skleyki_ozon": "nazvanie",
    "sertifikaty": "nazvanie",
}


@router.delete("/{entity_type}/{entity_id}")
def delete_entity(
    entity_type: str,
    entity_id: int,
    x_confirm_challenge: Optional[str] = Header(None),
    x_challenge_hash: Optional[str] = Header(None),
    x_challenge_salt: Optional[str] = Header(None),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """Two-step delete: first call returns 428 with challenge, second with answer archives."""
    if entity_type not in VALID_ENTITY_TYPES:
        raise HTTPException(404, f"Unknown entity type: {entity_type}")

    # Check record exists
    row = db.execute(
        text(f"SELECT * FROM {entity_type} WHERE id = :eid"),
        {"eid": entity_id},
    ).mappings().first()
    if not row:
        raise HTTPException(404, f"{entity_type}#{entity_id} not found")

    name_field = ENTITY_NAME_FIELDS.get(entity_type, "id")
    entity_name = str(dict(row).get(name_field, entity_id))

    # Check impact
    impact_data = ValidationService.check_delete_impact(db, entity_type, entity_id)
    strategy = impact_data["strategy"]
    children = impact_data["children"]
    blocked_by = impact_data["blocked_by"]

    # Block if active dependents
    if strategy == "block_if_active" and blocked_by:
        message = ArchiveService.build_impact_message(strategy, children, blocked_by)
        return JSONResponse(status_code=409, content={
            "error": "blocked",
            "impact": {
                "entity_type": entity_type,
                "entity_id": entity_id,
                "entity_name": entity_name,
                "strategy": strategy,
                "children": children,
                "blocked_by": blocked_by,
                "message": message,
            },
        })

    # Step 1: No challenge header → return 428 with challenge
    if not x_confirm_challenge:
        message = ArchiveService.build_impact_message(strategy, children, blocked_by)
        challenge_text, expected_hash, salt = ValidationService.generate_challenge()

        return JSONResponse(status_code=428, content={
            "requires_confirmation": True,
            "challenge": challenge_text,
            "expected_hash": expected_hash,
            "salt": salt,
            "impact": {
                "entity_type": entity_type,
                "entity_id": entity_id,
                "entity_name": entity_name,
                "strategy": strategy,
                "children": children,
                "blocked_by": blocked_by,
                "message": message,
            },
        })

    # Step 2: Verify challenge answer
    if not x_challenge_hash or not x_challenge_salt:
        raise HTTPException(400, "Missing X-Challenge-Hash or X-Challenge-Salt headers")

    if not ValidationService.verify_challenge(x_confirm_challenge, x_challenge_hash, x_challenge_salt):
        raise HTTPException(403, "Incorrect challenge answer")

    # Archive the record
    archive = ArchiveService.archive_entity(db, entity_type, entity_id, deleted_by=user.email)

    AuditService.log(
        db,
        action="delete",
        entity_type=entity_type,
        entity_id=entity_id,
        entity_name=entity_name,
        changes={"archived": True, "children": children},
        user_email=user.email,
    )
    db.commit()

    return {
        "archived": True,
        "archive_id": archive.id,
        "expires_at": archive.expires_at.isoformat() if archive.expires_at else None,
    }
```

- [ ] **Step 4: Register delete router in app.py**

Add to `services/product_matrix_api/app.py` after the views_router import:

```python
from services.product_matrix_api.routes.delete import router as delete_router
```

And after `app.include_router(views_router)`:

```python
app.include_router(delete_router)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee && python3 -m pytest tests/product_matrix_api/test_delete_routes.py -v`
Expected: all 3 tests PASS

- [ ] **Step 6: Run full test suite to verify no regressions**

Run: `cd /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee && python3 -m pytest tests/product_matrix_api/ -v`
Expected: all tests PASS

- [ ] **Step 7: Commit**

```bash
git add services/product_matrix_api/routes/delete.py services/product_matrix_api/app.py tests/product_matrix_api/test_delete_routes.py
git commit -m "feat(matrix-api): add two-step delete route with math challenge (428 → archive)"
```

---

## Task 5: Archive Routes (List, Restore, Hard Delete)

**Files:**
- Create: `services/product_matrix_api/routes/archive.py`
- Test: `tests/product_matrix_api/test_archive_routes.py`

- [ ] **Step 1: Write tests for archive routes**

Create `tests/product_matrix_api/test_archive_routes.py`:

```python
"""Tests for archive CRUD routes."""
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from services.product_matrix_api.app import app

client = TestClient(app)


def test_list_archive_returns_200():
    """GET /api/matrix/archive returns paginated list."""
    with patch("services.product_matrix_api.routes.archive.get_db") as mock_db:
        mock_session = MagicMock()
        mock_db.return_value = iter([mock_session])

        # Mock: count returns 0
        mock_session.execute.return_value.scalar.return_value = 0
        mock_session.execute.return_value.scalars.return_value.all.return_value = []

        resp = client.get("/api/matrix/archive")
        assert resp.status_code == 200


def test_restore_not_found_returns_404():
    """POST /api/matrix/archive/99999/restore returns 404 for missing archive."""
    with patch("services.product_matrix_api.routes.archive.get_db") as mock_db, \
         patch("services.product_matrix_api.routes.archive.ArchiveService") as mock_as:

        mock_session = MagicMock()
        mock_db.return_value = iter([mock_session])
        mock_as.restore_record.side_effect = ValueError("Archive record #99999 not found")

        resp = client.post("/api/matrix/archive/99999/restore")
        assert resp.status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee && python3 -m pytest tests/product_matrix_api/test_archive_routes.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Implement archive routes**

Create `services/product_matrix_api/routes/archive.py`:

```python
"""Archive CRUD routes — list, restore, hard-delete archived records."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, text
from sqlalchemy.orm import Session

from services.product_matrix_api.config import get_db
from services.product_matrix_api.dependencies import CurrentUser, get_current_user
from services.product_matrix_api.models.database import ArchiveRecord
from services.product_matrix_api.models.schemas import ArchiveRecordRead, PaginatedResponse
from services.product_matrix_api.services.archive_service import ArchiveService
from services.product_matrix_api.services.audit_service import AuditService

router = APIRouter(prefix="/api/matrix/archive", tags=["archive"])


@router.get("", response_model=PaginatedResponse)
def list_archive(
    entity_type: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """List archived records with optional entity_type filter."""
    query = select(ArchiveRecord)
    count_query = select(func.count()).select_from(ArchiveRecord)

    if entity_type:
        query = query.where(ArchiveRecord.original_table == entity_type)
        count_query = count_query.where(ArchiveRecord.original_table == entity_type)

    query = query.order_by(ArchiveRecord.deleted_at.desc())

    total = db.execute(count_query).scalar() or 0
    offset = (page - 1) * per_page
    items = list(db.execute(query.offset(offset).limit(per_page)).scalars().all())
    pages = (total + per_page - 1) // per_page if per_page > 0 else 1

    return PaginatedResponse(
        items=[ArchiveRecordRead.model_validate(a) for a in items],
        total=total, page=page, per_page=per_page, pages=pages,
    )


@router.post("/{archive_id}/restore")
def restore_archive(
    archive_id: int,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """Restore an archived record and its children."""
    try:
        result = ArchiveService.restore_record(db, archive_id)
    except ValueError as e:
        raise HTTPException(404, str(e))

    AuditService.log(
        db,
        action="restore",
        entity_type=result["table"],
        entity_id=result["id"],
        user_email=user.email,
    )
    db.commit()
    return result


@router.delete("/{archive_id}")
def hard_delete_archive(
    archive_id: int,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """Permanently delete an archived record (admin only)."""
    try:
        result = ArchiveService.hard_delete_archived(db, archive_id)
    except ValueError as e:
        raise HTTPException(404, str(e))

    AuditService.log(
        db,
        action="delete",
        entity_type=result["table"],
        entity_id=result["id"],
        changes={"hard_delete": True},
        user_email=user.email,
    )
    db.commit()
    return result
```

- [ ] **Step 4: Register archive router in app.py**

Add to `services/product_matrix_api/app.py`:

```python
from services.product_matrix_api.routes.archive import router as archive_router
```

And:

```python
app.include_router(archive_router)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee && python3 -m pytest tests/product_matrix_api/test_archive_routes.py -v`
Expected: all 2 tests PASS

- [ ] **Step 6: Commit**

```bash
git add services/product_matrix_api/routes/archive.py services/product_matrix_api/app.py tests/product_matrix_api/test_archive_routes.py
git commit -m "feat(matrix-api): add archive routes (list, restore, hard-delete)"
```

---

## Task 6: Admin Routes (Audit Logs, DB Stats, Health)

**Files:**
- Create: `services/product_matrix_api/routes/admin.py`
- Test: `tests/product_matrix_api/test_admin_routes.py`

- [ ] **Step 1: Write tests for admin routes**

Create `tests/product_matrix_api/test_admin_routes.py`:

```python
"""Tests for admin routes (logs, stats, health)."""
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from services.product_matrix_api.app import app

client = TestClient(app)


def test_admin_health_returns_ok():
    """GET /api/matrix/admin/health returns ok."""
    with patch("services.product_matrix_api.routes.admin.get_db") as mock_db:
        mock_session = MagicMock()
        mock_db.return_value = iter([mock_session])
        mock_session.execute.return_value.scalar.return_value = 1

        resp = client.get("/api/matrix/admin/health")
        assert resp.status_code == 200
        assert resp.json()["ok"] is True


def test_admin_logs_returns_200():
    """GET /api/matrix/admin/logs returns paginated audit log."""
    with patch("services.product_matrix_api.routes.admin.get_db") as mock_db:
        mock_session = MagicMock()
        mock_db.return_value = iter([mock_session])
        mock_session.execute.return_value.scalar.return_value = 0
        mock_session.execute.return_value.scalars.return_value.all.return_value = []

        resp = client.get("/api/matrix/admin/logs")
        assert resp.status_code == 200


def test_admin_stats_returns_200():
    """GET /api/matrix/admin/stats returns DB statistics."""
    with patch("services.product_matrix_api.routes.admin.get_db") as mock_db:
        mock_session = MagicMock()
        mock_db.return_value = iter([mock_session])
        # Mock: table counts
        mock_session.execute.return_value.fetchall.return_value = []

        resp = client.get("/api/matrix/admin/stats")
        assert resp.status_code == 200
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee && python3 -m pytest tests/product_matrix_api/test_admin_routes.py -v`
Expected: FAIL

- [ ] **Step 3: Implement admin routes**

Create `services/product_matrix_api/routes/admin.py`:

```python
"""Admin routes — audit logs, DB stats, health check."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, text
from sqlalchemy.orm import Session

from services.product_matrix_api.config import get_db
from services.product_matrix_api.models.database import HubAuditLog
from services.product_matrix_api.models.schemas import (
    AuditLogRead, PaginatedResponse, DbStats, TableStats,
)

router = APIRouter(prefix="/api/matrix/admin", tags=["admin"])

# Tables to include in stats
STATS_TABLES = [
    "modeli_osnova", "modeli", "artikuly", "tovary", "cveta",
    "fabriki", "importery", "skleyki_wb", "skleyki_ozon",
    "sertifikaty", "archive_records",
]


@router.get("/health")
def health_check(db: Session = Depends(get_db)):
    """Check database connectivity."""
    try:
        result = db.execute(text("SELECT 1")).scalar()
        return {"ok": result == 1}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.get("/logs", response_model=PaginatedResponse)
def list_audit_logs(
    entity_type: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    user_email: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """List audit log entries with optional filters."""
    query = select(HubAuditLog)
    count_query = select(func.count()).select_from(HubAuditLog)

    if entity_type:
        query = query.where(HubAuditLog.entity_type == entity_type)
        count_query = count_query.where(HubAuditLog.entity_type == entity_type)
    if action:
        query = query.where(HubAuditLog.action == action)
        count_query = count_query.where(HubAuditLog.action == action)
    if user_email:
        query = query.where(HubAuditLog.user_email == user_email)
        count_query = count_query.where(HubAuditLog.user_email == user_email)

    query = query.order_by(HubAuditLog.timestamp.desc())

    total = db.execute(count_query).scalar() or 0
    offset = (page - 1) * per_page
    items = list(db.execute(query.offset(offset).limit(per_page)).scalars().all())
    pages = (total + per_page - 1) // per_page if per_page > 0 else 1

    return PaginatedResponse(
        items=[AuditLogRead.model_validate(log) for log in items],
        total=total, page=page, per_page=per_page, pages=pages,
    )


@router.get("/stats", response_model=DbStats)
def db_stats(db: Session = Depends(get_db)):
    """Get record counts and growth metrics for all entity tables."""
    tables = []
    total_records = 0

    for table_name in STATS_TABLES:
        try:
            count = db.execute(
                text(f"SELECT COUNT(*) FROM {table_name}")
            ).scalar() or 0

            # Growth: records created in last 7 days
            growth_week = 0
            growth_month = 0
            try:
                growth_week = db.execute(
                    text(
                        f"SELECT COUNT(*) FROM {table_name} "
                        f"WHERE created_at >= NOW() - INTERVAL '7 days'"
                    )
                ).scalar() or 0
                growth_month = db.execute(
                    text(
                        f"SELECT COUNT(*) FROM {table_name} "
                        f"WHERE created_at >= NOW() - INTERVAL '30 days'"
                    )
                ).scalar() or 0
            except Exception:
                pass  # Some tables might not have created_at

            tables.append(TableStats(
                name=table_name, count=count,
                growth_week=growth_week, growth_month=growth_month,
            ))
            total_records += count
        except Exception:
            tables.append(TableStats(name=table_name, count=0))

    return DbStats(tables=tables, total_records=total_records)
```

- [ ] **Step 4: Register admin router in app.py**

Add to `services/product_matrix_api/app.py`:

```python
from services.product_matrix_api.routes.admin import router as admin_router
```

And:

```python
app.include_router(admin_router)
```

- [ ] **Step 5: Run tests and full suite**

Run: `cd /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee && python3 -m pytest tests/product_matrix_api/test_admin_routes.py -v && python3 -m pytest tests/product_matrix_api/ -v`
Expected: all tests PASS

- [ ] **Step 6: Commit**

```bash
git add services/product_matrix_api/routes/admin.py services/product_matrix_api/app.py tests/product_matrix_api/test_admin_routes.py
git commit -m "feat(matrix-api): add admin routes (audit logs, DB stats, health)"
```

---

## Task 7: Frontend — API Client Extensions + Delete Types

**Files:**
- Modify: `wookiee-hub/src/lib/api-client.ts`
- Modify: `wookiee-hub/src/lib/matrix-api.ts`

- [ ] **Step 1: Add httpDeleteJson to api-client.ts**

Add after `httpDelete` function in `wookiee-hub/src/lib/api-client.ts`:

```typescript
/**
 * DELETE with custom headers and JSON response.
 * Used for two-step delete with math challenge.
 */
export async function httpDeleteJson<T>(
  path: string,
  headers?: Record<string, string>,
  signal?: AbortSignal,
): Promise<{ status: number; data: T }> {
  const url = new URL(path, BASE_URL || window.location.origin)
  const res = await fetch(url.toString(), {
    method: "DELETE",
    headers: {
      "Content-Type": "application/json",
      ...headers,
    },
    signal,
  })

  const data = await res.json() as T
  return { status: res.status, data }
}
```

- [ ] **Step 2: Add delete/archive/admin API methods to matrix-api.ts**

Add types and methods to `wookiee-hub/src/lib/matrix-api.ts`:

```typescript
// After existing types, add:

export interface DeleteImpact {
  entity_type: string
  entity_id: number
  entity_name: string
  strategy: string
  children: Record<string, number>
  blocked_by: Record<string, number> | null
  message: string
}

export interface DeleteChallengeResponse {
  requires_confirmation: boolean
  challenge: string
  expected_hash: string
  salt: string
  impact: DeleteImpact
}

export interface DeleteConfirmResponse {
  archived: boolean
  archive_id: number
  expires_at: string | null
}

export interface ArchiveRecord {
  id: number
  original_table: string
  original_id: number
  full_record: Record<string, unknown>
  related_records: Array<{ table: string; id: number; record: Record<string, unknown> }>
  deleted_by: string | null
  deleted_at: string | null
  expires_at: string | null
  restore_available: boolean
}

export interface AuditLogEntry {
  id: number
  timestamp: string | null
  user_email: string | null
  action: string
  entity_type: string | null
  entity_id: number | null
  entity_name: string | null
  changes: Record<string, unknown> | null
}

export interface TableStatsEntry {
  name: string
  count: number
  growth_week: number
  growth_month: number
}

export interface DbStatsResponse {
  tables: TableStatsEntry[]
  total_records: number
}
```

And add API methods inside the `matrixApi` object:

```typescript
  // Delete (two-step)
  deleteEntity: (entityType: string, entityId: number) =>
    httpDeleteJson<DeleteChallengeResponse | DeleteConfirmResponse>(
      `/api/matrix/${entityType}/${entityId}`,
    ),

  confirmDelete: (
    entityType: string,
    entityId: number,
    answer: string,
    hash: string,
    salt: string,
  ) =>
    httpDeleteJson<DeleteConfirmResponse>(
      `/api/matrix/${entityType}/${entityId}`,
      {
        "X-Confirm-Challenge": answer,
        "X-Challenge-Hash": hash,
        "X-Challenge-Salt": salt,
      },
    ),

  // Archive
  listArchive: (params?: Record<string, string | number | undefined>) =>
    get<PaginatedResponse<ArchiveRecord>>("/api/matrix/archive", params),

  restoreArchive: (archiveId: number) =>
    post<{ restored: boolean; table: string; id: number }>(
      `/api/matrix/archive/${archiveId}/restore`, {},
    ),

  hardDeleteArchive: (archiveId: number) =>
    httpDelete(`/api/matrix/archive/${archiveId}`),

  // Admin
  getAdminHealth: () =>
    get<{ ok: boolean; error?: string }>("/api/matrix/admin/health"),

  listAuditLogs: (params?: Record<string, string | number | undefined>) =>
    get<PaginatedResponse<AuditLogEntry>>("/api/matrix/admin/logs", params),

  getDbStats: () =>
    get<DbStatsResponse>("/api/matrix/admin/stats"),
```

- [ ] **Step 3: Verify TypeScript compiles**

Run: `cd /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee/wookiee-hub && npx tsc --noEmit`
Expected: no errors

- [ ] **Step 4: Commit**

```bash
cd /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee/wookiee-hub
git add src/lib/api-client.ts src/lib/matrix-api.ts
git commit -m "feat(matrix): add delete/archive/admin API client methods"
```

---

## Task 8: Frontend — DeleteConfirmDialog + DeleteChallengeDialog

**Files:**
- Create: `wookiee-hub/src/components/matrix/delete-confirm-dialog.tsx`
- Create: `wookiee-hub/src/components/matrix/delete-challenge-dialog.tsx`

- [ ] **Step 1: Create DeleteConfirmDialog**

Create `wookiee-hub/src/components/matrix/delete-confirm-dialog.tsx`:

```tsx
import { type DeleteImpact } from "@/lib/matrix-api"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"

interface Props {
  open: boolean
  onOpenChange: (open: boolean) => void
  impact: DeleteImpact | null
  onConfirm: () => void
}

export function DeleteConfirmDialog({ open, onOpenChange, impact, onConfirm }: Props) {
  if (!impact) return null

  const hasChildren = Object.keys(impact.children).length > 0

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Удалить {impact.entity_name}?</AlertDialogTitle>
          <AlertDialogDescription asChild>
            <div className="space-y-3">
              <p>{impact.message}</p>
              {hasChildren && (
                <div className="rounded-md bg-amber-50 dark:bg-amber-950/30 p-3 text-sm">
                  <p className="font-medium text-amber-800 dark:text-amber-200 mb-1">
                    Будут затронуты:
                  </p>
                  <ul className="list-disc list-inside text-amber-700 dark:text-amber-300">
                    {Object.entries(impact.children).map(([table, count]) => (
                      <li key={table}>
                        {table}: {count} записей
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              <p className="text-xs text-muted-foreground">
                Запись будет перемещена в архив на 30 дней, затем удалена автоматически.
              </p>
            </div>
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Отмена</AlertDialogCancel>
          <AlertDialogAction
            onClick={onConfirm}
            className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
          >
            Продолжить удаление
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
```

- [ ] **Step 2: Create DeleteChallengeDialog**

Create `wookiee-hub/src/components/matrix/delete-challenge-dialog.tsx`:

```tsx
import { useState } from "react"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"

interface Props {
  open: boolean
  onOpenChange: (open: boolean) => void
  challenge: string
  onSubmit: (answer: string) => void
  loading?: boolean
  error?: string | null
}

export function DeleteChallengeDialog({
  open,
  onOpenChange,
  challenge,
  onSubmit,
  loading,
  error,
}: Props) {
  const [answer, setAnswer] = useState("")

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (answer.trim()) {
      onSubmit(answer.trim())
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Подтверждение удаления</DialogTitle>
          <DialogDescription>
            Для подтверждения решите пример:
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit}>
          <div className="space-y-4">
            <div className="text-center">
              <span className="text-3xl font-mono font-bold tracking-wider">
                {challenge} = ?
              </span>
            </div>
            <Input
              type="number"
              placeholder="Ответ"
              value={answer}
              onChange={(e) => setAnswer(e.target.value)}
              autoFocus
              className="text-center text-lg"
            />
            {error && (
              <p className="text-sm text-destructive text-center">{error}</p>
            )}
          </div>
          <DialogFooter className="mt-4">
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
            >
              Отмена
            </Button>
            <Button
              type="submit"
              variant="destructive"
              disabled={!answer.trim() || loading}
            >
              {loading ? "Удаление..." : "Удалить"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
```

- [ ] **Step 3: Verify TypeScript compiles**

Run: `cd /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee/wookiee-hub && npx tsc --noEmit`
Expected: no errors

- [ ] **Step 4: Commit**

```bash
cd /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee/wookiee-hub
git add src/components/matrix/delete-confirm-dialog.tsx src/components/matrix/delete-challenge-dialog.tsx
git commit -m "feat(matrix): add DeleteConfirmDialog and DeleteChallengeDialog components"
```

---

## Task 9: Frontend — Admin Layout + Routes

**Files:**
- Create: `wookiee-hub/src/pages/system/matrix-admin-layout.tsx`
- Modify: `wookiee-hub/src/router.tsx`
- Modify: `wookiee-hub/src/stores/navigation.ts`

- [ ] **Step 1: Create admin layout**

Create the `system/` directory if needed, then create `wookiee-hub/src/pages/system/matrix-admin-layout.tsx`:

```tsx
import { NavLink, Outlet } from "react-router-dom"
import { cn } from "@/lib/utils"
import {
  Database,
  Globe,
  FileText,
  Archive,
  BarChart3,
} from "lucide-react"

const adminNav = [
  { to: "/system/matrix-admin/schema", label: "Схема", icon: Database },
  { to: "/system/matrix-admin/api", label: "API", icon: Globe },
  { to: "/system/matrix-admin/logs", label: "Логи", icon: FileText },
  { to: "/system/matrix-admin/archive", label: "Архив", icon: Archive },
  { to: "/system/matrix-admin/stats", label: "Статистика", icon: BarChart3 },
]

export function MatrixAdminLayout() {
  return (
    <div className="flex h-full">
      <nav className="w-52 border-r bg-muted/30 p-3 space-y-1">
        <h2 className="px-2 mb-3 text-sm font-semibold text-muted-foreground uppercase tracking-wider">
          Admin Panel
        </h2>
        {adminNav.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              cn(
                "flex items-center gap-2 px-2 py-1.5 rounded-md text-sm transition-colors",
                isActive
                  ? "bg-primary/10 text-primary font-medium"
                  : "text-muted-foreground hover:text-foreground hover:bg-muted"
              )
            }
          >
            <Icon className="h-4 w-4" />
            {label}
          </NavLink>
        ))}
      </nav>
      <div className="flex-1 p-6 overflow-auto">
        <Outlet />
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Add placeholder admin pages**

Create 5 stub pages (one per admin section). Each follows the same pattern — create these files:

`wookiee-hub/src/pages/system/schema-explorer-page.tsx`:
```tsx
export function SchemaExplorerPage() {
  return (
    <div>
      <h1 className="text-2xl font-bold mb-4">Schema Explorer</h1>
      <p className="text-muted-foreground">Структура таблиц и полей — в разработке.</p>
    </div>
  )
}
```

`wookiee-hub/src/pages/system/api-explorer-page.tsx`:
```tsx
export function ApiExplorerPage() {
  return (
    <div>
      <h1 className="text-2xl font-bold mb-4">API Explorer</h1>
      <p className="text-muted-foreground">Список эндпоинтов — в разработке.</p>
    </div>
  )
}
```

`wookiee-hub/src/pages/system/audit-log-page.tsx`:
```tsx
import { useEffect, useState } from "react"
import { matrixApi, type AuditLogEntry, type PaginatedResponse } from "@/lib/matrix-api"

export function AuditLogPage() {
  const [data, setData] = useState<PaginatedResponse<AuditLogEntry> | null>(null)
  const [page, setPage] = useState(1)
  const [entityFilter, setEntityFilter] = useState("")
  const [actionFilter, setActionFilter] = useState("")

  useEffect(() => {
    const params: Record<string, string | number> = { page, per_page: 50 }
    if (entityFilter) params.entity_type = entityFilter
    if (actionFilter) params.action = actionFilter
    matrixApi.listAuditLogs(params).then(setData)
  }, [page, entityFilter, actionFilter])

  return (
    <div>
      <h1 className="text-2xl font-bold mb-4">Audit Log</h1>

      <div className="flex gap-2 mb-4">
        <select
          className="border rounded px-2 py-1 text-sm bg-background"
          value={entityFilter}
          onChange={(e) => { setEntityFilter(e.target.value); setPage(1) }}
        >
          <option value="">Все сущности</option>
          {["modeli_osnova","modeli","artikuly","tovary","cveta","fabriki","importery"].map(t => (
            <option key={t} value={t}>{t}</option>
          ))}
        </select>
        <select
          className="border rounded px-2 py-1 text-sm bg-background"
          value={actionFilter}
          onChange={(e) => { setActionFilter(e.target.value); setPage(1) }}
        >
          <option value="">Все действия</option>
          {["create","update","delete","bulk_update","restore"].map(a => (
            <option key={a} value={a}>{a}</option>
          ))}
        </select>
      </div>

      <div className="border rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-muted/50">
            <tr>
              <th className="text-left p-2">Время</th>
              <th className="text-left p-2">Пользователь</th>
              <th className="text-left p-2">Действие</th>
              <th className="text-left p-2">Сущность</th>
              <th className="text-left p-2">ID</th>
              <th className="text-left p-2">Название</th>
              <th className="text-left p-2">Изменения</th>
            </tr>
          </thead>
          <tbody>
            {data?.items.map((log) => (
              <tr key={log.id} className="border-t hover:bg-muted/30">
                <td className="p-2 font-mono text-xs">
                  {log.timestamp ? new Date(log.timestamp).toLocaleString("ru") : "—"}
                </td>
                <td className="p-2">{log.user_email ?? "—"}</td>
                <td className="p-2">
                  <span className={`inline-block px-1.5 py-0.5 rounded text-xs font-medium ${
                    log.action === "delete" ? "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400" :
                    log.action === "create" ? "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400" :
                    "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400"
                  }`}>
                    {log.action}
                  </span>
                </td>
                <td className="p-2">{log.entity_type ?? "—"}</td>
                <td className="p-2 font-mono">{log.entity_id ?? "—"}</td>
                <td className="p-2">{log.entity_name ?? "—"}</td>
                <td className="p-2 max-w-xs truncate text-xs text-muted-foreground">
                  {log.changes ? JSON.stringify(log.changes) : "—"}
                </td>
              </tr>
            ))}
            {(!data || data.items.length === 0) && (
              <tr><td colSpan={7} className="p-4 text-center text-muted-foreground">Нет записей</td></tr>
            )}
          </tbody>
        </table>
      </div>

      {data && data.pages > 1 && (
        <div className="flex gap-2 mt-3 justify-center">
          <button
            className="px-3 py-1 border rounded text-sm disabled:opacity-50"
            disabled={page <= 1}
            onClick={() => setPage(p => p - 1)}
          >
            ← Назад
          </button>
          <span className="px-3 py-1 text-sm text-muted-foreground">
            {page} / {data.pages}
          </span>
          <button
            className="px-3 py-1 border rounded text-sm disabled:opacity-50"
            disabled={page >= data.pages}
            onClick={() => setPage(p => p + 1)}
          >
            Вперёд →
          </button>
        </div>
      )}
    </div>
  )
}
```

`wookiee-hub/src/pages/system/archive-manager-page.tsx`:
```tsx
import { useEffect, useState } from "react"
import { matrixApi, type ArchiveRecord, type PaginatedResponse } from "@/lib/matrix-api"

export function ArchiveManagerPage() {
  const [data, setData] = useState<PaginatedResponse<ArchiveRecord> | null>(null)
  const [page, setPage] = useState(1)
  const [entityFilter, setEntityFilter] = useState("")

  const load = () => {
    const params: Record<string, string | number> = { page, per_page: 50 }
    if (entityFilter) params.entity_type = entityFilter
    matrixApi.listArchive(params).then(setData)
  }

  useEffect(load, [page, entityFilter])

  const handleRestore = async (id: number) => {
    await matrixApi.restoreArchive(id)
    load()
  }

  const handleHardDelete = async (id: number) => {
    if (!confirm("Удалить навсегда? Это действие необратимо.")) return
    await matrixApi.hardDeleteArchive(id)
    load()
  }

  return (
    <div>
      <h1 className="text-2xl font-bold mb-4">Архив</h1>

      <div className="mb-4">
        <select
          className="border rounded px-2 py-1 text-sm bg-background"
          value={entityFilter}
          onChange={(e) => { setEntityFilter(e.target.value); setPage(1) }}
        >
          <option value="">Все сущности</option>
          {["modeli_osnova","modeli","artikuly","tovary","cveta","fabriki","importery"].map(t => (
            <option key={t} value={t}>{t}</option>
          ))}
        </select>
      </div>

      <div className="border rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-muted/50">
            <tr>
              <th className="text-left p-2">Таблица</th>
              <th className="text-left p-2">ID</th>
              <th className="text-left p-2">Удалено</th>
              <th className="text-left p-2">Кем</th>
              <th className="text-left p-2">Истекает</th>
              <th className="text-left p-2">Связанных</th>
              <th className="text-left p-2">Действия</th>
            </tr>
          </thead>
          <tbody>
            {data?.items.map((rec) => (
              <tr key={rec.id} className="border-t hover:bg-muted/30">
                <td className="p-2 font-medium">{rec.original_table}</td>
                <td className="p-2 font-mono">{rec.original_id}</td>
                <td className="p-2 text-xs">
                  {rec.deleted_at ? new Date(rec.deleted_at).toLocaleString("ru") : "—"}
                </td>
                <td className="p-2">{rec.deleted_by ?? "—"}</td>
                <td className="p-2 text-xs">
                  {rec.expires_at ? new Date(rec.expires_at).toLocaleDateString("ru") : "—"}
                </td>
                <td className="p-2 text-center">{rec.related_records?.length ?? 0}</td>
                <td className="p-2">
                  <div className="flex gap-1">
                    {rec.restore_available && (
                      <button
                        className="px-2 py-0.5 rounded text-xs bg-green-100 text-green-700 hover:bg-green-200 dark:bg-green-900/30 dark:text-green-400"
                        onClick={() => handleRestore(rec.id)}
                      >
                        Восстановить
                      </button>
                    )}
                    <button
                      className="px-2 py-0.5 rounded text-xs bg-red-100 text-red-700 hover:bg-red-200 dark:bg-red-900/30 dark:text-red-400"
                      onClick={() => handleHardDelete(rec.id)}
                    >
                      Удалить
                    </button>
                  </div>
                </td>
              </tr>
            ))}
            {(!data || data.items.length === 0) && (
              <tr><td colSpan={7} className="p-4 text-center text-muted-foreground">Архив пуст</td></tr>
            )}
          </tbody>
        </table>
      </div>

      {data && data.pages > 1 && (
        <div className="flex gap-2 mt-3 justify-center">
          <button
            className="px-3 py-1 border rounded text-sm disabled:opacity-50"
            disabled={page <= 1}
            onClick={() => setPage(p => p - 1)}
          >
            ← Назад
          </button>
          <span className="px-3 py-1 text-sm text-muted-foreground">
            {page} / {data.pages}
          </span>
          <button
            className="px-3 py-1 border rounded text-sm disabled:opacity-50"
            disabled={page >= data.pages}
            onClick={() => setPage(p => p + 1)}
          >
            Вперёд →
          </button>
        </div>
      )}
    </div>
  )
}
```

`wookiee-hub/src/pages/system/db-stats-page.tsx`:
```tsx
import { useEffect, useState } from "react"
import { matrixApi, type DbStatsResponse } from "@/lib/matrix-api"

export function DbStatsPage() {
  const [stats, setStats] = useState<DbStatsResponse | null>(null)
  const [health, setHealth] = useState<{ ok: boolean } | null>(null)

  useEffect(() => {
    matrixApi.getDbStats().then(setStats)
    matrixApi.getAdminHealth().then(setHealth)
  }, [])

  return (
    <div>
      <h1 className="text-2xl font-bold mb-4">Статистика БД</h1>

      <div className="flex gap-4 mb-6">
        <div className="border rounded-lg p-4 min-w-[160px]">
          <p className="text-sm text-muted-foreground">Статус БД</p>
          <p className={`text-2xl font-bold ${health?.ok ? "text-green-600" : "text-red-600"}`}>
            {health?.ok ? "OK" : "Error"}
          </p>
        </div>
        <div className="border rounded-lg p-4 min-w-[160px]">
          <p className="text-sm text-muted-foreground">Всего записей</p>
          <p className="text-2xl font-bold">
            {stats?.total_records.toLocaleString("ru") ?? "—"}
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {stats?.tables.map((t) => (
          <div key={t.name} className="border rounded-lg p-4">
            <p className="font-medium mb-1">{t.name}</p>
            <p className="text-2xl font-bold">{t.count.toLocaleString("ru")}</p>
            <div className="flex gap-3 mt-1 text-xs text-muted-foreground">
              <span className={t.growth_week > 0 ? "text-green-600" : ""}>
                +{t.growth_week} / нед
              </span>
              <span className={t.growth_month > 0 ? "text-green-600" : ""}>
                +{t.growth_month} / мес
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
```

- [ ] **Step 3: Add admin routes to router.tsx**

Modify `wookiee-hub/src/router.tsx` — add imports and routes:

```tsx
// Add imports:
import { MatrixAdminLayout } from "@/pages/system/matrix-admin-layout"
import { SchemaExplorerPage } from "@/pages/system/schema-explorer-page"
import { ApiExplorerPage } from "@/pages/system/api-explorer-page"
import { AuditLogPage } from "@/pages/system/audit-log-page"
import { ArchiveManagerPage } from "@/pages/system/archive-manager-page"
import { DbStatsPage } from "@/pages/system/db-stats-page"
```

Add routes inside the `children` array (after the System section):

```tsx
      // Matrix Admin
      {
        path: "/system/matrix-admin",
        element: <MatrixAdminLayout />,
        children: [
          { index: true, element: <Navigate to="/system/matrix-admin/schema" replace /> },
          { path: "schema", element: <SchemaExplorerPage /> },
          { path: "api", element: <ApiExplorerPage /> },
          { path: "logs", element: <AuditLogPage /> },
          { path: "archive", element: <ArchiveManagerPage /> },
          { path: "stats", element: <DbStatsPage /> },
        ],
      },
```

- [ ] **Step 4: Add admin nav to navigation store**

Read `wookiee-hub/src/stores/navigation.ts` and add a nav entry for "Matrix Admin" under the System section, linking to `/system/matrix-admin`.

- [ ] **Step 5: Verify TypeScript compiles**

Run: `cd /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee/wookiee-hub && npx tsc --noEmit`
Expected: no errors

- [ ] **Step 6: Commit**

```bash
cd /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee/wookiee-hub
git add src/pages/system/ src/router.tsx src/stores/navigation.ts
git commit -m "feat(matrix): add admin panel layout with 5 admin pages (schema, API, logs, archive, stats)"
```

---

## Task 10: Final Verification + Full Test Suite

**Files:** None (verification only)

- [ ] **Step 1: Run full backend test suite**

Run: `cd /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee && python3 -m pytest tests/product_matrix_api/ -v`
Expected: all tests PASS (87 existing + ~23 new ≈ 110 tests)

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee/wookiee-hub && npx tsc --noEmit`
Expected: no errors

- [ ] **Step 3: Verify no regressions in existing routes**

Quick smoke test: routes that existed before (models, articles, etc.) should still work.
Run: `cd /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee && python3 -m pytest tests/product_matrix_api/test_routes_models.py tests/product_matrix_api/test_integration.py -v`
Expected: all PASS

- [ ] **Step 4: Verify app starts**

Run: `cd /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee && python3 -c "from services.product_matrix_api.app import app; print('App loaded OK, routers:', len(app.routes))"`
Expected: prints OK with increased router count (15+ routes)

---

## Phase 6 Prompt (for next chat)

```
PIM — Product Matrix Editor, Phase 6: Integration & Polish

Выполни Phase 6 из спеки: docs/superpowers/specs/2026-03-20-product-matrix-editor-design.md

Спек: docs/superpowers/specs/2026-03-20-product-matrix-editor-design.md (секция "Phase 6: Integration & Polish")
Phase 5 план (для контекста): docs/superpowers/plans/2026-03-21-product-matrix-phase5-plan.md

## Что уже сделано (Phase 1-5)

Phase 1 — Backend Foundation:
- FastAPI сервис на порту 8002 (services/product_matrix_api/)
- SQLAlchemy модели + Supabase PostgreSQL
- Generic CRUD service, audit logging в hub.audit_log

Phase 2 — Frontend Core:
- wookiee-hub/ (ОТДЕЛЬНЫЙ git репо!) — React 19 + TypeScript + Tailwind + shadcn/ui
- MatrixShell: sidebar + topbar + detail panel
- DataTable с inline editing, ViewTabs, expand/collapse

Phase 3 — All Entities CRUD:
- Backend: CRUD для всех 10 сущностей + глобальный поиск + bulk operations
- Frontend: 9 страниц-таблиц, Cmd+K поиск, mass edit bar

Phase 4 — Views & Fields:
- Backend: field_definitions CRUD, saved views CRUD
- Frontend: ViewTabs с 4 built-in видами + saved views, ManageFieldsDialog, SaveViewDialog

Phase 5 — Safety & Admin:
- Backend: ValidationService с CASCADE_RULES, ArchiveService (soft delete + restore + expire)
- Backend: Two-step delete route (428 challenge → archive), archive routes, admin routes (logs, stats, health)
- Frontend: DeleteConfirmDialog + DeleteChallengeDialog, admin panel с 5 страницами
- ~110 backend тестов проходят, TypeScript компилируется без ошибок

## Что нужно сделать (Phase 6)

Из спеки, секция "Phase 6: Integration & Polish":
- Подтягивание данных из WB/Ozon (склад, финансы, рейтинг)
- Полная страница записи с табами
- Аутентификация через Telegram (часть общего Wookiee Hub auth)
- Export (CSV, Excel)

## Формат работы

1. Сначала напиши план (Phase 6 plan) в docs/superpowers/plans/
2. После моего ОК — выполни план
3. Закоммить всё (backend в основном репо, frontend в wookiee-hub/ репо)

## Важно

- wookiee-hub/ — ОТДЕЛЬНЫЙ git-репозиторий, коммитить frontend нужно cd wookiee-hub && git add/commit
- БД: Supabase PostgreSQL, подключение через services/product_matrix_api/config.py
- Тесты: python3 -m pytest tests/product_matrix_api/ -v
- TypeScript: cd wookiee-hub && npx tsc --noEmit
```
