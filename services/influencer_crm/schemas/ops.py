"""Pydantic schemas for the /ops/health endpoint."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class EtlLastRun(BaseModel):
    started_at: datetime | None = None
    status: str | None = None
    duration_ms: int | None = None
    error_message: str | None = None


class EtlCounts(BaseModel):
    success: int = 0
    failed: int = 0
    running: int = 0
    stale_running: int = 0  # running > 1h, treated as stuck


class CronJobInfo(BaseModel):
    jobname: str
    schedule: str
    active: bool


class RetentionCounts(BaseModel):
    audit_log_eligible_for_delete: int = 0
    snapshots_eligible_for_delete: int = 0


class OpsHealth(BaseModel):
    etl_last_run: EtlLastRun
    etl_last_24h: EtlCounts
    mv_age_seconds: int | None = None
    retention: RetentionCounts
    cron_jobs: list[CronJobInfo]
