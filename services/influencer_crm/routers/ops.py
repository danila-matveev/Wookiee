"""Ops health endpoint — single source of truth for the dashboard.

Read-only. Reads from crm.etl_runs (migration 012), cron.job, and crm.*
retention sources. X-API-Key gate inherited from the rest of the BFF
(router-level dependency).

Each sub-source is wrapped in try/except: a missing schema (e.g. pg_cron not
installed in the test DB, or crm.etl_runs not yet migrated) must not crash
the endpoint — it degrades to empty defaults instead.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from services.influencer_crm.deps import get_session, verify_api_key
from services.influencer_crm.schemas.ops import (
    CronJobInfo,
    EtlCounts,
    EtlLastRun,
    OpsHealth,
    RetentionCounts,
)

router = APIRouter(
    prefix="/ops",
    tags=["ops"],
    dependencies=[Depends(verify_api_key)],
)

logger = logging.getLogger("influencer_crm.ops")

ETL_AGENT_NAME = "crm-sheets-etl"


def _fetch_etl_last_run(session: Session) -> EtlLastRun:
    try:
        row = session.execute(
            text(
                """
                SELECT started_at, status, duration_ms, error_message
                FROM crm.etl_runs
                WHERE agent = :name
                ORDER BY started_at DESC
                LIMIT 1
                """
            ),
            {"name": ETL_AGENT_NAME},
        ).first()
    except Exception as e:
        logger.warning("ops.health: crm.etl_runs lookup failed: %s", e)
        session.rollback()
        return EtlLastRun()
    if row is None:
        return EtlLastRun()
    return EtlLastRun(
        started_at=row.started_at,
        status=row.status,
        duration_ms=row.duration_ms,
        error_message=row.error_message,
    )


def _fetch_etl_counts(session: Session) -> EtlCounts:
    try:
        row = session.execute(
            text(
                """
                SELECT
                    COUNT(*) FILTER (WHERE status='success') AS ok,
                    COUNT(*) FILTER (WHERE status='failed')  AS failed
                FROM crm.etl_runs
                WHERE agent = :name
                  AND started_at > now() - INTERVAL '24 hours'
                """
            ),
            {"name": ETL_AGENT_NAME},
        ).first()
    except Exception as e:
        logger.warning("ops.health: crm.etl_runs counts failed: %s", e)
        session.rollback()
        return EtlCounts()
    if row is None:
        return EtlCounts()
    return EtlCounts(success=row.ok or 0, failed=row.failed or 0)


def _fetch_mv_age(session: Session) -> int | None:
    try:
        row = session.execute(
            text(
                """
                SELECT EXTRACT(EPOCH FROM (
                    now() - GREATEST(
                        COALESCE(last_analyze, last_autoanalyze, now() - INTERVAL '1 day'),
                        now() - INTERVAL '1 day'
                    )
                ))::int AS age
                FROM pg_stat_user_tables
                WHERE schemaname = 'crm' AND relname = 'v_blogger_totals'
                """
            )
        ).first()
    except Exception as e:
        logger.warning("ops.health: mv age lookup failed: %s", e)
        session.rollback()
        return None
    if row is None or row.age is None:
        return None
    return int(row.age)


def _fetch_retention(session: Session) -> RetentionCounts:
    try:
        row = session.execute(
            text(
                """
                SELECT
                    (SELECT COUNT(*) FROM crm.audit_log
                       WHERE created_at < now() - INTERVAL '90 days')  AS audit_count,
                    (SELECT COUNT(*) FROM crm.integration_metrics_snapshots
                       WHERE captured_at < now() - INTERVAL '365 days') AS snap_count
                """
            )
        ).first()
    except Exception as e:
        logger.warning("ops.health: retention lookup failed: %s", e)
        session.rollback()
        return RetentionCounts()
    if row is None:
        return RetentionCounts()
    return RetentionCounts(
        audit_log_eligible_for_delete=row.audit_count or 0,
        snapshots_eligible_for_delete=row.snap_count or 0,
    )


def _fetch_cron_jobs(session: Session) -> list[CronJobInfo]:
    try:
        rows = session.execute(
            text(
                """
                SELECT jobname, schedule, active
                FROM cron.job
                WHERE jobname LIKE 'crm_%'
                ORDER BY jobname
                """
            )
        ).all()
    except Exception as e:
        logger.warning("ops.health: cron.job lookup failed: %s", e)
        session.rollback()
        return []
    return [
        CronJobInfo(jobname=r.jobname, schedule=r.schedule, active=r.active)
        for r in rows
    ]


@router.get("/health", response_model=OpsHealth)
def get_health(session: Session = Depends(get_session)) -> OpsHealth:
    return OpsHealth(
        etl_last_run=_fetch_etl_last_run(session),
        etl_last_24h=_fetch_etl_counts(session),
        mv_age_seconds=_fetch_mv_age(session),
        retention=_fetch_retention(session),
        cron_jobs=_fetch_cron_jobs(session),
    )
