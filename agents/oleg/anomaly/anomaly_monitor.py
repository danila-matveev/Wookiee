"""
AnomalyMonitor — periodic background check for metric anomalies.

Runs every N hours between scheduled reports. Checks yesterday's metrics
against 7-day averages. If anomaly detected, sends a brief Telegram alert.

Features:
- Day-of-week awareness: softer thresholds on weekends/Monday
- Deduplication: same anomaly not alerted twice within 12h window
- Optional LLM commentary when 2+ anomalies detected simultaneously
"""
import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

METRIC_LABELS = {
    "revenue": "Выручка",
    "margin_pct": "Маржа %",
    "drr_pct": "ДРР %",
    "orders_count": "Заказы",
}

DEDUP_STATE_KEY = "anomaly_last_alerts"
DEDUP_WINDOW_SEC = 12 * 3600  # 12 hours


@dataclass
class AnomalyAlert:
    """Single detected anomaly."""
    metric: str           # 'revenue', 'margin_pct', 'drr_pct', 'orders_count'
    channel: str          # 'wb', 'ozon'
    current_value: float
    avg_value: float
    deviation_pct: float  # how much it deviated
    direction: str        # 'up' or 'down'
    severity: str         # 'warning' or 'critical'


class AnomalyMonitor:
    """Periodically checks key metrics for anomalies."""

    DEFAULT_THRESHOLDS = {
        "revenue": {"threshold": 20.0, "direction": "both"},
        "margin_pct": {"threshold": 10.0, "direction": "both"},
        "drr_pct": {"threshold": 30.0, "direction": "up"},
        "orders_count": {"threshold": 25.0, "direction": "down"},
    }

    def __init__(
        self,
        state_store,
        alerter,
        llm_client=None,
        classify_model: str = "google/gemini-3-flash-preview",
        thresholds: Optional[Dict] = None,
        weekend_multiplier: float = 1.5,
        gate_checker=None,
    ):
        self.state_store = state_store
        self.alerter = alerter
        self.llm_client = llm_client
        self.classify_model = classify_model
        self.thresholds = thresholds or self.DEFAULT_THRESHOLDS
        self.weekend_multiplier = weekend_multiplier
        self.gate_checker = gate_checker

    async def check_and_alert(self) -> None:
        """Main entry point: check metrics for WB and OZON, detect anomalies, alert."""
        all_anomalies: List[AnomalyAlert] = []
        effective_thresholds = self._get_effective_thresholds()

        for channel in ("wb", "ozon"):
            try:
                # Skip channel if data not loaded yet (prevents false alerts on 0-revenue)
                if self.gate_checker:
                    gate_result = self.gate_checker.check_all(channel)
                    if not gate_result.can_generate:
                        failed = [g.name for g in gate_result.gates if g.is_hard and not g.passed]
                        logger.info(f"Anomaly check: skipping {channel} — hard gates failed: {failed}")
                        continue

                metrics = await self._fetch_metrics(channel)
                if not metrics:
                    logger.info(f"Anomaly check: no data for {channel}")
                    continue
                anomalies = self._detect_anomalies(metrics, channel, effective_thresholds)
                all_anomalies.extend(anomalies)
            except Exception as e:
                logger.error(f"Anomaly check failed for {channel}: {e}")

        # Filter out duplicates
        new_anomalies = [a for a in all_anomalies if not self._is_duplicate(a)]

        if not new_anomalies:
            logger.info("Anomaly check: no new anomalies detected")
            return

        # Format alert
        message = await self._format_alert_message(new_anomalies)

        # Save state BEFORE send — prevents re-sending on crash/restart
        self._save_alert_state(new_anomalies)

        await self.alerter.send_alert(message)
        logger.info(f"Anomaly alert sent: {len(new_anomalies)} anomalies")

    def _get_effective_thresholds(self) -> dict:
        """Return adjusted thresholds based on day of week (MSK)."""
        import pytz
        tz = pytz.timezone("Europe/Moscow")
        weekday = datetime.now(tz).weekday()  # 0=Mon, 5=Sat, 6=Sun

        multiplier = 1.0
        if weekday in (0, 5, 6):  # Mon, Sat, Sun — softer thresholds
            multiplier = self.weekend_multiplier
            logger.debug(
                f"Weekend/Monday detected (weekday={weekday}), "
                f"threshold multiplier={multiplier}"
            )

        return {
            k: {**v, "threshold": v["threshold"] * multiplier}
            for k, v in self.thresholds.items()
        }

    async def _fetch_metrics(self, channel: str) -> Optional[Dict]:
        """Fetch yesterday's values + 7-day averages via data_layer."""
        from shared.data_layer import get_wb_daily_series, get_ozon_daily_series
        from agents.oleg.services.time_utils import get_yesterday_msk

        yesterday = get_yesterday_msk()
        target_date = str(yesterday)

        if channel == "wb":
            series = await asyncio.to_thread(get_wb_daily_series, target_date, 7)
        else:
            series = await asyncio.to_thread(get_ozon_daily_series, target_date, 7)

        if not series or len(series) < 2:
            return None

        # Last entry = yesterday's values
        yesterday_data = series[-1]
        # Previous entries = comparison base
        prev_days = series[:-1]

        def safe_avg(key):
            values = [d.get(key, 0) for d in prev_days if d.get(key) is not None]
            return sum(values) / len(values) if values else 0

        avg_revenue = safe_avg("revenue_before_spp")
        avg_margin = safe_avg("margin")
        avg_adv = safe_avg("adv_total")
        avg_orders = safe_avg("orders_count")

        y_revenue = yesterday_data.get("revenue_before_spp", 0)
        y_margin = yesterday_data.get("margin", 0)
        y_adv = yesterday_data.get("adv_total", 0)
        y_orders = yesterday_data.get("orders_count", 0)

        return {
            "yesterday": {
                "revenue": y_revenue,
                "margin_pct": round((y_margin / y_revenue * 100) if y_revenue else 0, 1),
                "drr_pct": round((y_adv / y_revenue * 100) if y_revenue else 0, 1),
                "orders_count": y_orders,
            },
            "avg_7d": {
                "revenue": avg_revenue,
                "margin_pct": round((avg_margin / avg_revenue * 100) if avg_revenue else 0, 1),
                "drr_pct": round((avg_adv / avg_revenue * 100) if avg_revenue else 0, 1),
                "orders_count": avg_orders,
            },
        }

    def _detect_anomalies(
        self, metrics: Dict, channel: str, thresholds: Dict,
    ) -> List[AnomalyAlert]:
        """Compare current vs averages, return list of anomalies."""
        anomalies = []
        yesterday = metrics["yesterday"]
        avg = metrics["avg_7d"]

        for metric_name, cfg in thresholds.items():
            curr = yesterday.get(metric_name, 0)
            avg_val = avg.get(metric_name, 0)

            if avg_val == 0:
                continue

            # Percentage-point metrics use absolute diff, others use % change
            if metric_name.endswith("_pct"):
                deviation = curr - avg_val
            else:
                deviation = ((curr - avg_val) / abs(avg_val)) * 100

            threshold = cfg["threshold"]
            direction_filter = cfg["direction"]
            direction = "up" if deviation > 0 else "down"

            is_anomaly = False
            if direction_filter == "both" and abs(deviation) > threshold:
                is_anomaly = True
            elif direction_filter == "up" and deviation > threshold:
                is_anomaly = True
            elif direction_filter == "down" and deviation < -threshold:
                is_anomaly = True

            if is_anomaly:
                severity = "critical" if abs(deviation) > threshold * 2 else "warning"
                anomalies.append(AnomalyAlert(
                    metric=metric_name,
                    channel=channel,
                    current_value=round(curr, 1),
                    avg_value=round(avg_val, 1),
                    deviation_pct=round(deviation, 1),
                    direction=direction,
                    severity=severity,
                ))

        return anomalies

    def _is_duplicate(self, alert: AnomalyAlert) -> bool:
        """Check if this anomaly was already alerted recently."""
        raw = self.state_store.get_state(DEDUP_STATE_KEY)
        if not raw:
            return False
        try:
            prev_alerts = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return False

        key = f"{alert.channel}:{alert.metric}"
        prev = prev_alerts.get(key)
        if not prev:
            return False

        if prev.get("direction") == alert.direction:
            prev_time = datetime.fromisoformat(prev.get("timestamp", "2000-01-01"))
            if prev_time.tzinfo is None:
                prev_time = prev_time.replace(tzinfo=timezone.utc)
            if (datetime.now(timezone.utc) - prev_time).total_seconds() < DEDUP_WINDOW_SEC:
                return True
        return False

    def _save_alert_state(self, alerts: List[AnomalyAlert]) -> None:
        """Save current alerts to state store for dedup."""
        # Load existing state
        raw = self.state_store.get_state(DEDUP_STATE_KEY)
        try:
            state = json.loads(raw) if raw else {}
        except (json.JSONDecodeError, TypeError):
            state = {}

        now = datetime.now(timezone.utc).isoformat()
        for a in alerts:
            key = f"{a.channel}:{a.metric}"
            state[key] = {"direction": a.direction, "timestamp": now}

        self.state_store.set_state(DEDUP_STATE_KEY, json.dumps(state))

    async def _format_alert_message(self, alerts: List[AnomalyAlert]) -> str:
        """Format alert message. Optionally add LLM commentary for 2+ anomalies."""
        lines = ["⚡ Anomaly Monitor\n"]

        for a in alerts:
            icon = "🔴" if a.severity == "critical" else "🟡"
            arrow = "↑" if a.direction == "up" else "↓"
            name = METRIC_LABELS.get(a.metric, a.metric)

            if a.metric.endswith("_pct"):
                lines.append(
                    f"{icon} {a.channel.upper()} {name}: "
                    f"{a.current_value:.1f}% vs avg {a.avg_value:.1f}% "
                    f"({arrow}{abs(a.deviation_pct):.1f} п.п.)"
                )
            else:
                lines.append(
                    f"{icon} {a.channel.upper()} {name}: "
                    f"{a.current_value:,.0f} vs avg {a.avg_value:,.0f} "
                    f"({arrow}{abs(a.deviation_pct):.1f}%)"
                )

        base_message = "\n".join(lines)

        # Optional LLM commentary for multiple anomalies
        if self.llm_client and len(alerts) >= 2:
            try:
                prompt = (
                    f"Кратко (2-3 предложения) прокомментируй аномалии бренда Wookiee:\n"
                    f"{base_message}\n\n"
                    f"Возможные причины и связи между аномалиями. Без приветствий."
                )
                response = await self.llm_client.complete(
                    messages=[{"role": "user", "content": prompt}],
                    model=self.classify_model,
                    temperature=0.3,
                    max_tokens=300,
                )
                commentary = response.get("content", "")
                if commentary:
                    base_message += f"\n\n💡 {commentary.strip()}"
            except Exception as e:
                logger.warning(f"LLM commentary failed: {e}")

        return base_message
