"""Pydantic schemas for the /ops/health endpoint."""
from __future__ import annotations
from typing import Optional

from datetime import datetime

from pydantic import BaseModel


class EtlLastRun(BaseModel):
    started_at: Optional[datetime] = None
    status: Optional[str] = None
    duration_ms: Optional[int] = None
    error_message: Optional[str] = None


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
    mv_age_seconds: Optional[int] = None
    retention: RetentionCounts
    cron_jobs: list[CronJobInfo]
