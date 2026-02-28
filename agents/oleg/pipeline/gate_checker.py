"""
GateChecker — data quality gates with graceful degradation.

Hard gates (must pass): data must exist.
Soft gates (may fail): report generated with caveat.

v1 had 6 hard gates → all-or-nothing → silent death.
v2 has 3 hard + 3 soft → graceful degradation.
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional

from agents.oleg.services.time_utils import get_today_msk, get_yesterday_msk

logger = logging.getLogger(__name__)


_MONTH_NAMES_RU = {
    1: "января", 2: "февраля", 3: "марта", 4: "апреля",
    5: "мая", 6: "июня", 7: "июля", 8: "августа",
    9: "сентября", 10: "октября", 11: "ноября", 12: "декабря",
}


def _format_date_ru(d: date) -> str:
    """'2026-02-25' → '25 февраля'."""
    return f"{d.day} {_MONTH_NAMES_RU[d.month]}"


@dataclass
class GateResult:
    """Result of a single gate check."""
    name: str
    passed: bool
    is_hard: bool
    value: Optional[float] = None
    threshold: Optional[float] = None
    detail: str = ""
    extra: Dict = field(default_factory=dict)

    @property
    def severity(self) -> str:
        if self.passed:
            return "OK"
        return "BLOCK" if self.is_hard else "WARN"


@dataclass
class GateCheckResult:
    """Aggregate result of all gate checks."""
    gates: List[GateResult]
    can_generate: bool       # True if all hard gates passed
    has_caveats: bool        # True if any soft gate failed
    caveats: List[str]       # Warning messages for soft gate failures

    @property
    def hard_passed(self) -> int:
        return sum(1 for g in self.gates if g.is_hard and g.passed)

    @property
    def hard_total(self) -> int:
        return sum(1 for g in self.gates if g.is_hard)

    @property
    def soft_passed(self) -> int:
        return sum(1 for g in self.gates if not g.is_hard and g.passed)

    @property
    def soft_total(self) -> int:
        return sum(1 for g in self.gates if not g.is_hard)

    def format_status_message(self, target_date: str = "", marketplace: str = "") -> str:
        """Format gate check results as a compact, human-readable Telegram message."""
        # Parse target_date for nice formatting
        try:
            d = date.fromisoformat(target_date) if target_date else None
            date_label = _format_date_ru(d) if d else target_date
        except ValueError:
            date_label = target_date

        mp_label = f" ({marketplace.upper()})" if marketplace else ""

        # Gate lookup by name
        gate_map = {g.name: g for g in self.gates}

        if self.can_generate:
            lines = [f"✅ Данные за {date_label} готовы{mp_label}"]
        else:
            lines = [f"❌ Данные за {date_label} не готовы{mp_label}"]

        lines.append("")  # blank line

        # --- ETL update time ---
        etl = gate_map.get("ETL ran today")
        if etl:
            update_time = etl.extra.get("update_time")
            if etl.passed and update_time:
                lines.append(f"Обновлено в {update_time} МСК")
            elif not etl.passed:
                last = etl.extra.get("last_update_label", "неизвестно")
                lines.append(f"⏳ Данные не обновлены (последнее: {last})")

        # --- Source orders ---
        src = gate_map.get("Source data loaded today")
        if src and not src.passed:
            ratio = src.extra.get("ratio_pct")
            count = src.extra.get("order_count", 0)
            if ratio is not None and count > 0:
                lines.append(f"⚠️ Частичная загрузка: {count} ({ratio:.0f}% от нормы)")
            else:
                lines.append("⚠️ Нет заказов за вчера")

        # --- Logistics ---
        logi = gate_map.get("Logistics > 0")
        if logi and not logi.passed:
            lines.append("⚠️ Нет данных по логистике")

        # --- Orders volume ---
        orders = gate_map.get("Orders volume vs avg")
        if orders and orders.extra:
            count = orders.extra.get("count", "?")
            ratio = orders.extra.get("ratio")
            if orders.passed:
                lines.append(f"Заказов: {count} (норма)")
            else:
                lines.append(f"⚠️ Заказов: {count} ({ratio:.0f}% от нормы)")

        # --- Revenue ---
        rev = gate_map.get("Revenue vs 7-day avg")
        if rev and rev.extra:
            ratio = rev.extra.get("ratio")
            if rev.passed:
                lines.append(f"Выручка: {ratio:.0f}% от нормы")
            else:
                lines.append(f"⚠️ Выручка: {ratio:.0f}% от нормы")

        # --- Margin ---
        margin = gate_map.get("Margin fill")
        if margin and margin.extra:
            pct = margin.extra.get("pct")
            if margin.passed:
                lines.append(f"Маржа: у {pct:.0f}% артикулов")
            else:
                lines.append(f"⚠️ Маржа: только у {pct:.0f}% артикулов")

        return "\n".join(lines)


class GateChecker:
    """
    Check data quality gates before report generation.

    Hard gates (data must exist):
    1. ETL ran today — abc_date updated today
    2. Source data present — orders for yesterday exist and volume is sufficient
    3. Logistics > 0 — logistics data present

    Soft gates (report with caveat if failed):
    4. Orders volume vs 7-day avg — ≥ 70%
    5. Revenue vs 7-day avg — ≥ 70%
    6. Margin fill — ≥ 50% of articles have margin data
    """

    # Column name mapping: WB and Ozon abc_date have different schemas
    _COLUMN_MAP = {
        "wb": {
            "dateupdate": "dateupdate",
            "logistics": "logist",
            "revenue": "revenue",
            "marga": "marga",
        },
        "ozon": {
            "dateupdate": "date_update",
            "logistics": "logist_end",
            "revenue": "price_end",
            "marga": "marga",
        },
    }

    # Orders table config per marketplace
    _ORDERS_CONFIG = {
        "wb": {"table": "orders", "date_col": "date::date"},
        "ozon": {"table": "orders", "date_col": "in_process_at::date"},
    }

    def __init__(self):
        self._gates: List[GateResult] = []

    def _col(self, marketplace: str, logical_name: str) -> str:
        """Resolve logical column name to marketplace-specific column."""
        return self._COLUMN_MAP[marketplace][logical_name]

    def check_all(self, marketplace: str = "wb") -> GateCheckResult:
        """Run all gates for a marketplace."""
        self._gates = []

        # Hard gates
        self._check_etl_ran_today(marketplace)
        self._check_source_loaded_today(marketplace)
        self._check_logistics_present(marketplace)

        # Soft gates
        self._check_orders_volume(marketplace)
        self._check_revenue_vs_avg(marketplace)
        self._check_margin_fill(marketplace)

        all_hard_passed = all(g.passed for g in self._gates if g.is_hard)
        soft_failures = [g for g in self._gates if not g.is_hard and not g.passed]
        caveats = [g.detail for g in soft_failures]

        result = GateCheckResult(
            gates=list(self._gates),
            can_generate=all_hard_passed,
            has_caveats=bool(caveats),
            caveats=caveats,
        )

        logger.info(
            f"GateCheck[{marketplace}]: "
            f"hard={result.hard_passed}/{result.hard_total}, "
            f"soft={result.soft_passed}/{result.soft_total}, "
            f"can_generate={result.can_generate}"
        )

        return result

    def _check_etl_ran_today(self, marketplace: str) -> None:
        """Hard gate 1: ETL ran today (yesterday's abc_date updated today)."""
        try:
            from shared.data_layer import _get_wb_connection, _get_ozon_connection, _db_cursor

            conn_factory = _get_wb_connection if marketplace == "wb" else _get_ozon_connection
            col = self._col(marketplace, "dateupdate")
            yesterday = get_yesterday_msk()
            with _db_cursor(conn_factory) as (conn, cur):
                cur.execute(
                    f"SELECT MAX({col}) FROM abc_date WHERE date = %s",
                    (yesterday,),
                )
                row = cur.fetchone()
                last_update = row[0] if row else None

            today = get_today_msk()
            # Normalize: datetime → date for safe comparison
            try:
                update_date = last_update.date()  # works for datetime objects
            except AttributeError:
                update_date = last_update          # already a date object
            passed = update_date is not None and update_date == today

            # Extra for human-friendly formatting
            extra = {}
            if last_update and isinstance(last_update, datetime):
                extra["update_time"] = last_update.strftime("%H:%M")
            if update_date and update_date != today:
                extra["last_update_label"] = _format_date_ru(update_date)

            self._gates.append(GateResult(
                name="ETL ran today",
                passed=passed,
                is_hard=True,
                detail=f"Last ETL update: {last_update}, today: {today}",
                extra=extra,
            ))
        except Exception as e:
            self._gates.append(GateResult(
                name="ETL ran today",
                passed=False,
                is_hard=True,
                detail=f"Check failed: {e}",
            ))

    def _check_source_loaded_today(self, marketplace: str) -> None:
        """Hard gate 2: Orders for yesterday exist and volume is sufficient.

        Requires order count >= 30% of 7-day average to catch missing data.
        Falls back to count > 0 if no historical data available.
        ETL freshness is already checked by gate 1 (abc_date dateupdate).
        """
        MIN_RATIO_PCT = 30

        try:
            from shared.data_layer import _get_wb_connection, _get_ozon_connection, _db_cursor

            conn_factory = _get_wb_connection if marketplace == "wb" else _get_ozon_connection
            cfg = self._ORDERS_CONFIG[marketplace]
            yesterday = get_yesterday_msk()
            today = get_today_msk()
            week_ago = today - timedelta(days=8)

            with _db_cursor(conn_factory) as (conn, cur):
                # Count all orders for yesterday
                cur.execute(
                    f"SELECT COUNT(*) FROM {cfg['table']} "
                    f"WHERE {cfg['date_col']} = %s",
                    (yesterday,),
                )
                row = cur.fetchone()
                count = int(row[0]) if row else 0

                # 7-day average order count for volume comparison
                cur.execute(
                    f"SELECT COALESCE(AVG(cnt), 0) FROM ("
                    f"  SELECT COUNT(*) as cnt FROM {cfg['table']} "
                    f"  WHERE {cfg['date_col']} >= %s AND {cfg['date_col']} < %s "
                    f"  GROUP BY {cfg['date_col']}"
                    f") sub",
                    (week_ago, yesterday),
                )
                avg_row = cur.fetchone()
                avg_count = float(avg_row[0]) if avg_row else 0

            # Determine pass criteria
            if avg_count > 0:
                ratio = count / avg_count * 100
                passed = ratio >= MIN_RATIO_PCT
                detail = (
                    f"Orders for {yesterday}: {count} rows "
                    f"({ratio:.0f}% of 7d avg {avg_count:.0f})"
                    if passed else
                    f"Low volume for {yesterday}: {count} rows = "
                    f"{ratio:.0f}% of 7d avg {avg_count:.0f} (need ≥{MIN_RATIO_PCT}%)"
                )
            else:
                # No historical data — fall back to simple count > 0
                ratio = 100.0 if count > 0 else 0.0
                passed = count > 0
                detail = (
                    f"Orders for {yesterday}: {count} rows "
                    f"(no 7d history for comparison)"
                )

            self._gates.append(GateResult(
                name="Source data loaded today",
                passed=passed,
                is_hard=True,
                value=count,
                threshold=MIN_RATIO_PCT,
                detail=detail,
                extra={
                    "order_count": count,
                    "avg_7d": avg_count,
                    "ratio_pct": round(ratio, 1),
                },
            ))
        except Exception as e:
            self._gates.append(GateResult(
                name="Source data loaded today",
                passed=False,
                is_hard=True,
                detail=f"Check failed: {e}",
            ))

    def _check_logistics_present(self, marketplace: str) -> None:
        """Hard gate 3: Logistics data > 0."""
        try:
            from shared.data_layer import _get_wb_connection, _get_ozon_connection, _db_cursor

            conn_factory = _get_wb_connection if marketplace == "wb" else _get_ozon_connection
            yesterday = get_yesterday_msk()
            col = self._col(marketplace, "logistics")

            with _db_cursor(conn_factory) as (conn, cur):
                cur.execute(
                    f"SELECT COALESCE(SUM(ABS({col})), 0) FROM abc_date WHERE date = %s",
                    (yesterday,),
                )
                row = cur.fetchone()
                total_logistics = float(row[0]) if row else 0

            passed = total_logistics > 0

            self._gates.append(GateResult(
                name="Logistics > 0",
                passed=passed,
                is_hard=True,
                value=total_logistics,
                detail=f"Logistics sum for {yesterday}: {total_logistics}",
                extra={"logistics_sum": total_logistics},
            ))
        except Exception as e:
            self._gates.append(GateResult(
                name="Logistics > 0",
                passed=False,
                is_hard=True,
                detail=f"Check failed: {e}",
            ))

    def _check_orders_volume(self, marketplace: str) -> None:
        """Soft gate 4: Orders volume vs 7-day avg ≥ 70%."""
        try:
            from shared.data_layer import _get_wb_connection, _get_ozon_connection, _db_cursor

            conn_factory = _get_wb_connection if marketplace == "wb" else _get_ozon_connection
            yesterday = get_yesterday_msk()
            week_ago = get_today_msk() - timedelta(days=8)

            with _db_cursor(conn_factory) as (conn, cur):
                # Yesterday's order count
                cur.execute(
                    "SELECT COUNT(*) FROM abc_date WHERE date = %s",
                    (yesterday,),
                )
                yesterday_count = int(cur.fetchone()[0])

                # 7-day average
                cur.execute(
                    "SELECT COALESCE(AVG(cnt), 0) FROM ("
                    "  SELECT COUNT(*) as cnt FROM abc_date "
                    "  WHERE date >= %s AND date < %s GROUP BY date"
                    ") sub",
                    (week_ago, yesterday),
                )
                avg_count = float(cur.fetchone()[0])

            ratio = (yesterday_count / avg_count * 100) if avg_count > 0 else 100
            passed = ratio >= 70

            self._gates.append(GateResult(
                name="Orders volume vs avg",
                passed=passed,
                is_hard=False,
                value=round(ratio, 1),
                threshold=70,
                detail=f"Orders {yesterday_count} = {ratio:.0f}% of 7d avg {avg_count:.0f}"
                    if not passed else f"Orders volume OK: {ratio:.0f}% of 7d avg",
                extra={"count": yesterday_count, "ratio": ratio},
            ))
        except Exception as e:
            self._gates.append(GateResult(
                name="Orders volume vs avg",
                passed=True,  # Don't block on check failure
                is_hard=False,
                detail=f"Check skipped: {e}",
            ))

    def _check_revenue_vs_avg(self, marketplace: str) -> None:
        """Soft gate 5: Revenue vs 7-day avg ≥ 70%."""
        try:
            from shared.data_layer import _get_wb_connection, _get_ozon_connection, _db_cursor

            conn_factory = _get_wb_connection if marketplace == "wb" else _get_ozon_connection
            yesterday = get_yesterday_msk()
            col = self._col(marketplace, "revenue")

            with _db_cursor(conn_factory) as (conn, cur):
                # Yesterday's revenue
                cur.execute(
                    f"SELECT COALESCE(SUM({col}), 0) FROM abc_date WHERE date = %s",
                    (yesterday,),
                )
                yesterday_rev = float(cur.fetchone()[0])

                # 7-day average
                week_ago = get_today_msk() - timedelta(days=8)
                cur.execute(
                    f"SELECT COALESCE(AVG(daily_rev), 0) FROM ("
                    f"  SELECT date, SUM({col}) as daily_rev FROM abc_date "
                    f"  WHERE date >= %s AND date < %s GROUP BY date"
                    f") sub",
                    (week_ago, yesterday),
                )
                avg_rev = float(cur.fetchone()[0])

            ratio = (yesterday_rev / avg_rev * 100) if avg_rev > 0 else 100
            passed = ratio >= 70

            self._gates.append(GateResult(
                name="Revenue vs 7-day avg",
                passed=passed,
                is_hard=False,
                value=round(ratio, 1),
                threshold=70,
                detail=f"Yesterday revenue {yesterday_rev:,.0f} = {ratio:.0f}% of 7d avg {avg_rev:,.0f}"
                    if not passed else f"Revenue OK: {ratio:.0f}% of 7d avg",
                extra={"ratio": ratio},
            ))
        except Exception as e:
            self._gates.append(GateResult(
                name="Revenue vs 7-day avg",
                passed=True,
                is_hard=False,
                detail=f"Check skipped: {e}",
            ))

    def _check_margin_fill(self, marketplace: str) -> None:
        """Soft gate 6: Margin fill ≥ 50%."""
        try:
            from shared.data_layer import _get_wb_connection, _get_ozon_connection, _db_cursor

            conn_factory = _get_wb_connection if marketplace == "wb" else _get_ozon_connection
            yesterday = get_yesterday_msk()
            col = self._col(marketplace, "marga")

            with _db_cursor(conn_factory) as (conn, cur):
                cur.execute(
                    f"SELECT COUNT(*), "
                    f"SUM(CASE WHEN {col} IS NOT NULL AND {col} != 0 THEN 1 ELSE 0 END) "
                    f"FROM abc_date WHERE date = %s",
                    (yesterday,),
                )
                row = cur.fetchone()
                total = int(row[0]) if row else 0
                filled = int(row[1]) if row else 0

            fill_pct = (filled / total * 100) if total > 0 else 0
            passed = fill_pct >= 50

            self._gates.append(GateResult(
                name="Margin fill",
                passed=passed,
                is_hard=False,
                value=round(fill_pct, 1),
                threshold=50,
                detail=f"Margin: {filled}/{total} articles ({fill_pct:.0f}%, threshold 50%)",
                extra={"filled": filled, "total": total, "pct": fill_pct},
            ))
        except Exception as e:
            self._gates.append(GateResult(
                name="Margin fill",
                passed=True,
                is_hard=False,
                detail=f"Check skipped: {e}",
            ))
