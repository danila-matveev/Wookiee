"""Wookiee v3 — Anomaly monitor, watchdog, and circuit breaker."""
from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from agents.v3 import config
from agents.v3.delivery import messages

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Admin notification helper
# ---------------------------------------------------------------------------

_recent_messages: dict[str, float] = {}  # message_hash → timestamp
_RATE_LIMIT_SEC = 300  # Не отправлять одинаковые сообщения чаще чем раз в 5 минут


async def _send_admin(text: str) -> None:
    """Send a plain-text message to the admin Telegram chat.

    Rate-limited: identical messages suppressed within 5 minutes.
    """
    if not config.TELEGRAM_BOT_TOKEN or not config.ADMIN_CHAT_ID:
        logger.debug("_send_admin: no token/chat_id configured, skipping")
        return

    # Rate limit — подавляем дубли одинаковых сообщений
    import hashlib
    msg_hash = hashlib.md5(text.encode()).hexdigest()[:12]
    now = time.monotonic()

    last_sent = _recent_messages.get(msg_hash, 0)
    if now - last_sent < _RATE_LIMIT_SEC:
        logger.debug("_send_admin: rate-limited (same message sent %.0fs ago)", now - last_sent)
        return

    try:
        from aiogram import Bot
        bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
        try:
            await bot.send_message(config.ADMIN_CHAT_ID, text)
            _recent_messages[msg_hash] = now
        finally:
            await bot.session.close()

        # Cleanup old entries (keep dict from growing)
        stale = [k for k, v in _recent_messages.items() if now - v > _RATE_LIMIT_SEC * 2]
        for k in stale:
            del _recent_messages[k]

    except Exception as exc:
        logger.error("_send_admin failed: %s", exc)


# ---------------------------------------------------------------------------
# Connectivity checks (used by Watchdog)
# ---------------------------------------------------------------------------

async def _check_llm() -> bool:
    """Check LLM API connectivity via a minimal completion request."""
    try:
        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{config.OPENROUTER_BASE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {config.OPENROUTER_API_KEY}"},
                json={
                    "model": config.MODEL_LIGHT,
                    "messages": [{"role": "user", "content": "ping"}],
                    "max_tokens": 5,
                },
                timeout=15,
            )
            return resp.status_code == 200
    except Exception as exc:
        logger.warning("_check_llm failed: %s", exc)
        return False


async def _check_db() -> bool:
    """Check DB connectivity via a simple SELECT 1 (runs in thread to avoid blocking)."""
    try:
        import asyncio
        from shared.data_layer import _db_cursor, _get_wb_connection

        def _sync_check():
            with _db_cursor(_get_wb_connection) as (conn, cur):
                cur.execute("SELECT 1")

        await asyncio.to_thread(_sync_check)
        return True
    except Exception as exc:
        logger.warning("_check_db failed: %s", exc)
        return False


async def _check_last_run() -> bool:
    """Check whether the last orchestrator run was successful (observability log).

    Queries the orchestrator_runs table for the most recent run.
    Returns True if last run succeeded or no runs exist yet.
    """
    try:
        import asyncio
        from services.observability.logger import _get_conn

        def _sync_check():
            conn = _get_conn()
            try:
                cur = conn.cursor()
                cur.execute(
                    "SELECT status FROM orchestrator_runs "
                    "ORDER BY started_at DESC LIMIT 1"
                )
                row = cur.fetchone()
                return row[0] if row else None
            except Exception:
                # Table may not exist yet — not a failure
                return None
            finally:
                conn.close()

        status = await asyncio.to_thread(_sync_check)
        return status in ("success", "partial", None)
    except Exception as exc:
        logger.warning("_check_last_run failed: %s", exc)
        return True


# ---------------------------------------------------------------------------
# Circuit Breaker
# ---------------------------------------------------------------------------

class CircuitBreaker:
    """Per-agent circuit breaker to prevent cascading failures.

    After CB_FAILURE_THRESHOLD consecutive failures the circuit opens and the
    agent is skipped until CB_COOLDOWN_SEC seconds have elapsed.
    """

    def __init__(
        self,
        failure_threshold: int = config.CB_FAILURE_THRESHOLD,
        cooldown_sec: float = config.CB_COOLDOWN_SEC,
    ) -> None:
        self.failure_threshold = failure_threshold
        self.cooldown_sec = cooldown_sec
        # {agent_name: {"failures": int, "last_failure": float, "open_until": float}}
        self._state: dict[str, dict[str, Any]] = {}

    def _ensure(self, agent_name: str) -> None:
        if agent_name not in self._state:
            self._state[agent_name] = {
                "failures": 0,
                "last_failure": 0.0,
                "open_until": 0.0,
            }

    def is_open(self, agent_name: str) -> bool:
        """Return True if the circuit is open (agent should be skipped)."""
        self._ensure(agent_name)
        entry = self._state[agent_name]
        if entry["open_until"] == 0.0:
            return False
        if time.monotonic() >= entry["open_until"]:
            # Cooldown expired — half-open: allow one attempt
            logger.info(
                "CircuitBreaker[%s]: cooldown expired, half-open", agent_name
            )
            entry["open_until"] = 0.0
            return False
        return True

    def record_success(self, agent_name: str) -> None:
        """Reset failure counter after a successful agent run."""
        self._ensure(agent_name)
        entry = self._state[agent_name]
        if entry["failures"] > 0:
            logger.info(
                "CircuitBreaker[%s]: success — resetting %d failures",
                agent_name,
                entry["failures"],
            )
        entry["failures"] = 0
        entry["open_until"] = 0.0

    def record_failure(self, agent_name: str) -> None:
        """Increment failure counter; open circuit if threshold reached."""
        self._ensure(agent_name)
        entry = self._state[agent_name]
        entry["failures"] += 1
        entry["last_failure"] = time.monotonic()
        logger.warning(
            "CircuitBreaker[%s]: failure %d/%d",
            agent_name,
            entry["failures"],
            self.failure_threshold,
        )
        if entry["failures"] >= self.failure_threshold:
            entry["open_until"] = time.monotonic() + self.cooldown_sec
            logger.error(
                "CircuitBreaker[%s]: OPEN — skipping for %.0fs",
                agent_name,
                self.cooldown_sec,
            )


# ---------------------------------------------------------------------------
# Anomaly Monitor
# ---------------------------------------------------------------------------

class AnomalyMonitor:
    """Runs the anomaly-detector micro-agent every ANOMALY_MONITOR_INTERVAL_HOURS hours.

    Applies a weekend multiplier to thresholds and sends a Telegram alert if
    any anomalies are found.
    """

    def __init__(self) -> None:
        pass

    def _is_weekend(self) -> bool:
        """Return True if today is Saturday or Sunday (Moscow time)."""
        import pytz
        msk = pytz.timezone(config.TIMEZONE)
        now = datetime.now(msk)
        return now.weekday() >= 5  # 5=Saturday, 6=Sunday

    def _build_task(self, is_weekend: bool) -> str:
        """Build the task string for the anomaly-detector agent."""
        multiplier = config.ANOMALY_WEEKEND_MULTIPLIER if is_weekend else 1.0
        revenue_thr = config.ANOMALY_REVENUE_THRESHOLD * multiplier
        margin_thr = config.ANOMALY_MARGIN_PCT_THRESHOLD * multiplier
        drr_thr = config.ANOMALY_DRR_THRESHOLD_MONITOR * multiplier
        orders_thr = config.ANOMALY_ORDERS_THRESHOLD * multiplier

        import pytz
        msk = pytz.timezone(config.TIMEZONE)
        yesterday = (datetime.now(msk) - timedelta(days=1)).strftime("%Y-%m-%d")
        weekend_note = " (выходной — пороги увеличены в {:.1f} раз)".format(multiplier) if is_weekend else ""

        return (
            f"Запусти анализ аномалий за вчера ({yesterday}){weekend_note}.\n"
            f"Пороги: отклонение выручки>{revenue_thr:.1f}%, "
            f"маржинальности>{margin_thr:.1f}%, "
            f"ДРР>{drr_thr:.1f}%, "
            f"заказов>{orders_thr:.1f}%.\n"
            "1. Сначала search_knowledge_base — проверь известные паттерны.\n"
            "2. validate_data_quality — исключи проблемы пайплайна данных.\n"
            "3. get_brand_finance, get_daily_trend, get_channel_finance — базовые метрики.\n"
            "4. Верни JSON с anomalies и summary.\n"
            "ВАЖНО: summary_text и top_priority_anomaly — ОБЯЗАТЕЛЬНО на русском языке."
        )

    async def check_and_alert(self) -> None:
        """Main entry point: run anomaly detection and send alert if needed."""
        from agents.v3.runner import run_agent

        is_weekend = self._is_weekend()
        task = self._build_task(is_weekend)

        logger.info(
            "AnomalyMonitor: starting check (weekend=%s)", is_weekend
        )

        result = await run_agent(
            agent_name="anomaly-detector",
            task=task,
            trigger="anomaly_monitor",
            task_type="anomaly_check",
        )

        status = result.get("status")
        artifact = result.get("artifact")

        if status != "success":
            logger.warning(
                "AnomalyMonitor: agent returned status=%s — %s",
                status,
                result.get("raw_output", "")[:200],
            )
            return

        if not isinstance(artifact, dict):
            logger.warning("AnomalyMonitor: no parseable artifact in agent output")
            return

        summary = artifact.get("summary", {})
        critical_count = summary.get("critical_count", 0)
        warning_count = summary.get("warning_count", 0)
        total_actionable = critical_count + warning_count

        logger.info(
            "AnomalyMonitor: critical=%d warning=%d info=%d",
            critical_count,
            warning_count,
            summary.get("info_count", 0),
        )

        if total_actionable > 0:
            alert_text = messages.anomaly_report(artifact)
            await _send_admin(alert_text)
            logger.info("AnomalyMonitor: alert sent (%d actionable anomalies)", total_actionable)
        else:
            logger.info("AnomalyMonitor: no actionable anomalies found")


# ---------------------------------------------------------------------------
# Watchdog
# ---------------------------------------------------------------------------

class Watchdog:
    """System health watchdog — checks LLM API, DB, and last report status.

    Runs every WATCHDOG_HEARTBEAT_INTERVAL_HOURS hours.
    Smart suppression: only alerts on STATE CHANGE (was OK → now failed)
    or every Nth consecutive failure, not every heartbeat.
    """

    _FAILURE_ALERT_THRESHOLD = 3
    _REPEAT_ALERT_EVERY = 4  # Повторять алерт каждые N проверок (при persistent failure)

    def __init__(self) -> None:
        # Track consecutive report failures per report_type
        self._report_failures: dict[str, int] = {}
        # Track previous check results for state-change detection
        self._prev_checks: dict[str, bool] = {}
        # Count consecutive failures per check for suppression
        self._consecutive_failures: dict[str, int] = {}

    async def heartbeat(self) -> None:
        """Main entry point: run all health checks and alert only on state changes."""
        logger.info("Watchdog: starting heartbeat")

        llm_ok = await _check_llm()
        db_ok = await _check_db()
        last_run_ok = await _check_last_run()

        checks = {
            "llm": llm_ok,
            "db": db_ok,
            "last_run": last_run_ok,
        }
        failed = [name for name, ok in checks.items() if not ok]
        passed = [name for name, ok in checks.items() if ok]

        if not failed:
            status = "ok"
        elif len(failed) == len(checks):
            status = "critical"
        else:
            status = "warning"

        logger.info(
            "Watchdog: status=%s passed=%s failed=%s",
            status,
            passed,
            failed,
        )

        # Определяем, нужно ли слать алерт
        should_alert = False
        newly_failed = []
        recovered = []

        for name, ok in checks.items():
            prev_ok = self._prev_checks.get(name, True)  # Default: was OK
            if not ok:
                self._consecutive_failures[name] = self._consecutive_failures.get(name, 0) + 1
                if prev_ok:
                    # Было OK → стало FAIL — новый сбой
                    newly_failed.append(name)
                    should_alert = True
                elif self._consecutive_failures[name] % self._REPEAT_ALERT_EVERY == 0:
                    # Persistent failure — напоминаем каждые N проверок
                    should_alert = True
            else:
                if not prev_ok:
                    # Было FAIL → стало OK — восстановление
                    recovered.append(name)
                    should_alert = True
                self._consecutive_failures[name] = 0

            self._prev_checks[name] = ok

        if not should_alert:
            logger.info("Watchdog: no state change, suppressing alert")
            return

        # Отправляем восстановление отдельно
        if recovered and not failed:
            check_descriptions = {
                "llm": "Нейросеть (OpenRouter)",
                "db": "База данных аналитики",
                "last_run": "Последний запуск",
            }
            names = ", ".join(check_descriptions.get(n, n) for n in recovered)
            await _send_admin(f"✅ Восстановлено: {names}")
            return

        if status == "ok":
            return

        msg = messages.watchdog_alert(status, failed, passed)
        await _send_admin(msg)
        logger.warning("Watchdog: alert sent (status=%s, failed=%s)", status, failed)

    async def on_report_success(self, report_type: str) -> None:
        """Reset failure counter for a report type after successful delivery."""
        prev = self._report_failures.get(report_type, 0)
        if prev > 0:
            logger.info(
                "Watchdog: %s recovered after %d failure(s)", report_type, prev
            )
        self._report_failures[report_type] = 0

    async def on_report_failure(self, report_type: str) -> None:
        """Increment failure counter; send alert if threshold reached."""
        count = self._report_failures.get(report_type, 0) + 1
        self._report_failures[report_type] = count
        logger.warning(
            "Watchdog: %s failure %d/%d",
            report_type,
            count,
            self._FAILURE_ALERT_THRESHOLD,
        )

        if count >= self._FAILURE_ALERT_THRESHOLD:
            msg = messages.watchdog_repeated_failures(report_type, count)
            await _send_admin(msg)


# ---------------------------------------------------------------------------
# Singleton instances (shared across scheduler jobs)
# ---------------------------------------------------------------------------

_anomaly_monitor: AnomalyMonitor | None = None
_watchdog: Watchdog | None = None
_circuit_breaker: CircuitBreaker | None = None


def get_anomaly_monitor() -> AnomalyMonitor:
    global _anomaly_monitor
    if _anomaly_monitor is None:
        _anomaly_monitor = AnomalyMonitor()
    return _anomaly_monitor


def get_watchdog() -> Watchdog:
    global _watchdog
    if _watchdog is None:
        _watchdog = Watchdog()
    return _watchdog


def get_circuit_breaker() -> CircuitBreaker:
    global _circuit_breaker
    if _circuit_breaker is None:
        _circuit_breaker = CircuitBreaker()
    return _circuit_breaker
