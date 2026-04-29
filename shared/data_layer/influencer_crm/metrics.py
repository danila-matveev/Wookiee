from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from services.influencer_crm.schemas.metrics import MetricsSnapshotOut


def insert_snapshot(
    session: Session,
    integration_id: int,
    payload: dict[str, Any],
) -> MetricsSnapshotOut | None:
    # Verify FK exists
    exists = session.execute(
        text(
            "SELECT 1 FROM crm.integrations "
            "WHERE id = :id AND archived_at IS NULL"
        ),
        {"id": integration_id},
    ).first()
    if not exists:
        return None

    # DB column is `source` (NOT NULL, CHECK IN ('manual','api','import','sheets'), default 'manual').
    # API accepts optional `note` (free text) which has no direct DB column — ignored on insert.
    # Let the DB default ('manual') handle source.

    fields: dict[str, Any] = {
        "integration_id": integration_id,
        "fact_views": payload.get("fact_views"),
        "fact_clicks": payload.get("fact_clicks"),
        "fact_ctr": payload.get("fact_ctr"),
        "fact_cpm": payload.get("fact_cpm"),
        "fact_carts": payload.get("fact_carts"),
        "fact_orders": payload.get("fact_orders"),
        "fact_revenue": payload.get("fact_revenue"),
    }

    new_id = session.execute(
        text(
            "INSERT INTO crm.integration_metrics_snapshots ("
            "  integration_id, fact_views, fact_clicks, fact_ctr, fact_cpm, "
            "  fact_carts, fact_orders, fact_revenue"
            ") VALUES ("
            "  :integration_id, :fact_views, :fact_clicks, :fact_ctr, :fact_cpm, "
            "  :fact_carts, :fact_orders, :fact_revenue"
            ") RETURNING id"
        ),
        fields,
    ).scalar_one()

    row = session.execute(
        text(
            "SELECT id, integration_id, captured_at, "
            "       fact_views, fact_clicks, fact_ctr, fact_cpm, fact_carts, fact_orders, "
            "       fact_revenue, source AS note "
            "FROM crm.integration_metrics_snapshots WHERE id = :id"
        ),
        {"id": new_id},
    ).mappings().first()
    return MetricsSnapshotOut(**dict(row))
