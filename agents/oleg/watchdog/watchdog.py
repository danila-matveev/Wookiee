"""
Watchdog — health monitoring, dead man's switch, escalation.

Timeline on report failure:
- 09:00 MSK: Attempt #1 → report not created (no message yet)
- 12:00 MSK: Attempt #2 → "Report not created. Running diagnostics."
- 12:05 MSK: Diagnostics complete → "Found issue: {details}. Fix: {steps}."
- 16:00 MSK: Deadline → "Report not created by deadline. Needs your attention."

Multi-day failures: escalating severity on consecutive days.
"""
import logging
import time
from datetime import datetime
from typing import Optional

from agents.oleg.watchdog.diagnostic import DiagnosticRunner
from agents.oleg.watchdog.alerter import Alerter

logger = logging.getLogger(__name__)


class Watchdog:
    """Health monitoring with self-diagnostics and escalation."""

    def __init__(
        self,
        gate_checker=None,
        state_store=None,
        llm_client=None,
        alerter: Optional[Alerter] = None,
        heartbeat_interval_hours: int = 6,
    ):
        self.diagnostic_runner = DiagnosticRunner(
            gate_checker=gate_checker,
            state_store=state_store,
            llm_client=llm_client,
        )
        self.state_store = state_store
        self.alerter = alerter or Alerter()
        self.heartbeat_interval_hours = heartbeat_interval_hours
        self._last_heartbeat: Optional[float] = None

    async def on_report_failure(
        self, report_type: str, marketplace: str = "wb",
    ) -> None:
        """Called when a report fails to generate."""
        logger.warning(f"Report failure detected: {report_type}")

        # Check consecutive failures
        consecutive = 1
        if self.state_store:
            consecutive = self.state_store.get_consecutive_failures(marketplace) + 1

        # Run diagnostics
        diagnostic = await self.diagnostic_runner.diagnose(report_type, marketplace=marketplace)

        # Log
        if self.state_store:
            self.state_store.log_report(
                report_type=report_type,
                agent="watchdog",
                status="failure_detected",
                error=diagnostic.primary_issue.detail if diagnostic.primary_issue else "unknown",
            )

        # Send alert
        await self.alerter.send_report_failure_alert(
            report_type=report_type,
            consecutive_failures=consecutive,
            diagnostic=diagnostic,
        )

    async def on_report_success(self, report_type: str, cost_usd: float = 0.0) -> None:
        """Called when a report is generated successfully."""
        if self.state_store:
            self.state_store.log_report(
                report_type=report_type,
                agent="orchestrator",
                status="success",
                cost_usd=cost_usd,
            )

    async def heartbeat(self) -> None:
        """Send periodic heartbeat."""
        self._last_heartbeat = time.time()
        if self.state_store:
            self.state_store.set_state(
                "last_heartbeat",
                datetime.utcnow().isoformat(),
            )
        logger.info("Watchdog heartbeat")

    async def check_health(self) -> dict:
        """Run a quick health check and return status."""
        diagnostic = await self.diagnostic_runner.diagnose()
        return {
            "healthy": not diagnostic.has_failures,
            "checks": [
                {"component": c.component, "status": c.status, "detail": c.detail}
                for c in diagnostic.checks
            ],
            "last_heartbeat": self._last_heartbeat,
        }
