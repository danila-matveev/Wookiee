# agents/reporter/state.py
"""Supabase state management for report runs, notifications, and playbook."""
from __future__ import annotations

import json
import logging
from datetime import date, datetime
from typing import Any, Optional

from agents.reporter.types import ReportScope

logger = logging.getLogger(__name__)


class ReporterState:
    """Supabase-backed state for Reporter V4.

    Tables: report_runs, notification_log, analytics_rules
    """

    def __init__(self, client: Any):
        self._sb = client

    def create_run(self, scope: ReportScope) -> str:
        """Upsert a report run. Returns scope_hash as run ID."""
        row = {
            "report_date": scope.period_from.isoformat(),
            "report_type": scope.report_type.value,
            "scope_hash": scope.scope_hash,
            "scope_json": scope.to_dict(),
            "status": "pending",
            "attempt": 1,
            "updated_at": datetime.utcnow().isoformat(),
        }
        self._sb.table("report_runs").upsert(
            row, on_conflict="report_date,report_type,scope_hash"
        ).execute()
        return scope.scope_hash

    def update_run(
        self,
        scope: ReportScope,
        *,
        status: str,
        notion_url: Optional[str] = None,
        telegram_message_id: Optional[int] = None,
        confidence: Optional[float] = None,
        cost_usd: Optional[float] = None,
        duration_sec: Optional[float] = None,
        issues: Optional[list[str]] = None,
        error: Optional[str] = None,
        llm_model: Optional[str] = None,
        llm_tokens_in: Optional[int] = None,
        llm_tokens_out: Optional[int] = None,
    ) -> None:
        row: dict[str, Any] = {
            "status": status,
            "updated_at": datetime.utcnow().isoformat(),
        }
        if notion_url is not None:
            row["notion_url"] = notion_url
        if telegram_message_id is not None:
            row["telegram_message_id"] = telegram_message_id
        if confidence is not None:
            row["confidence"] = confidence
        if cost_usd is not None:
            row["cost_usd"] = cost_usd
        if duration_sec is not None:
            row["duration_sec"] = duration_sec
        if issues is not None:
            row["issues"] = issues
        if error is not None:
            row["error"] = error
        if llm_model is not None:
            row["llm_model"] = llm_model
        if llm_tokens_in is not None:
            row["llm_tokens_in"] = llm_tokens_in
        if llm_tokens_out is not None:
            row["llm_tokens_out"] = llm_tokens_out

        self._sb.table("report_runs").update(row).eq(
            "report_date", scope.period_from.isoformat()
        ).eq("report_type", scope.report_type.value).eq(
            "scope_hash", scope.scope_hash
        ).execute()

    def increment_attempt(self, scope: ReportScope) -> None:
        """Increment attempt counter for a run."""
        resp = (
            self._sb.table("report_runs")
            .select("attempt")
            .eq("report_date", scope.period_from.isoformat())
            .eq("report_type", scope.report_type.value)
            .eq("scope_hash", scope.scope_hash)
            .execute()
        )
        current = resp.data[0]["attempt"] if resp.data else 0
        self._sb.table("report_runs").update(
            {"attempt": current + 1, "status": "pending",
             "updated_at": datetime.utcnow().isoformat()}
        ).eq("report_date", scope.period_from.isoformat()).eq(
            "report_type", scope.report_type.value
        ).eq("scope_hash", scope.scope_hash).execute()

    def get_successful_today(self, today: date) -> set[str]:
        """Return set of report_type values with status='success' for today."""
        resp = (
            self._sb.table("report_runs")
            .select("report_type")
            .eq("report_date", today.isoformat())
            .eq("status", "success")
            .execute()
        )
        return {row["report_type"] for row in resp.data}

    def get_attempt_count(self, scope: ReportScope) -> int:
        resp = (
            self._sb.table("report_runs")
            .select("attempt")
            .eq("report_date", scope.period_from.isoformat())
            .eq("report_type", scope.report_type.value)
            .eq("scope_hash", scope.scope_hash)
            .execute()
        )
        return resp.data[0]["attempt"] if resp.data else 0

    def get_telegram_message_id(self, scope: ReportScope) -> Optional[int]:
        resp = (
            self._sb.table("report_runs")
            .select("telegram_message_id")
            .eq("report_date", scope.period_from.isoformat())
            .eq("report_type", scope.report_type.value)
            .eq("scope_hash", scope.scope_hash)
            .execute()
        )
        if resp.data and resp.data[0].get("telegram_message_id"):
            return resp.data[0]["telegram_message_id"]
        return None

    # ── Notification dedup ─────────────────────────────────────────────────

    def was_notified(self, key: str) -> bool:
        resp = (
            self._sb.table("notification_log")
            .select("id")
            .eq("notification_key", key)
            .execute()
        )
        return len(resp.data) > 0

    def mark_notified(self, key: str, telegram_message_id: Optional[int] = None) -> None:
        row = {"notification_key": key}
        if telegram_message_id:
            row["telegram_message_id"] = telegram_message_id
        self._sb.table("notification_log").upsert(
            row, on_conflict="notification_key"
        ).execute()

    # ── Playbook rules ─────────────────────────────────────────────────────

    def get_active_rules(self, report_type: Optional[str] = None) -> list[dict]:
        q = (
            self._sb.table("analytics_rules")
            .select("*")
            .eq("status", "active")
        )
        if report_type:
            q = q.contains("report_types", [report_type])
        return q.execute().data

    def save_pending_pattern(self, pattern: dict) -> None:
        self._sb.table("analytics_rules").insert(pattern).execute()

    def update_rule_status(self, rule_id: str, status: str) -> None:
        self._sb.table("analytics_rules").update(
            {"status": status, "reviewed_at": datetime.utcnow().isoformat()}
        ).eq("id", rule_id).execute()

    # ── Status summary ─────────────────────────────────────────────────────

    def get_today_status(self, today: date) -> list[dict]:
        """All runs for today with their statuses."""
        return (
            self._sb.table("report_runs")
            .select("report_type,status,attempt,confidence,notion_url,error,updated_at")
            .eq("report_date", today.isoformat())
            .execute()
            .data
        )
