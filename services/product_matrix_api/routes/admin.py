"""Admin routes — audit logs, DB stats, health check."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
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
                pass

            tables.append(TableStats(
                name=table_name, count=count,
                growth_week=growth_week, growth_month=growth_month,
            ))
            total_records += count
        except Exception:
            tables.append(TableStats(name=table_name, count=0))

    return DbStats(tables=tables, total_records=total_records)
