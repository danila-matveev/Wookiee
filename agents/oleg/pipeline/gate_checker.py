"""
GateChecker — data quality gates with graceful degradation.

Hard gates (must pass): data must exist.
Soft gates (may fail): report generated with caveat.

v1 had 6 hard gates → all-or-nothing → silent death.
v2 has 3 hard + 3 soft → graceful degradation.
"""
import logging
from dataclasses import dataclass
from datetime import datetime, date, timedelta
from typing import List, Optional

from agents.oleg.services.time_utils import get_today_msk, get_yesterday_msk

logger = logging.getLogger(__name__)


@dataclass
class GateResult:
    """Result of a single gate check."""
    name: str
    passed: bool
    is_hard: bool
    value: Optional[float] = None
    threshold: Optional[float] = None
    detail: str = ""

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

    def format_status_message(self, target_date: str = "") -> str:
        """Format gate check results as a human-readable Telegram message."""
        lines = []
        if self.can_generate:
            lines.append(f"✅ Данные за {target_date} готовы.")
        else:
            lines.append(f"❌ Данные за {target_date} не готовы.")

        for g in self.gates:
            icon = "✅" if g.passed else ("❌" if g.is_hard else "⚠️")
            lines.append(f"  {icon} {g.name}: {g.detail}")

        lines.append(
            f"\nHard: {self.hard_passed}/{self.hard_total}, "
            f"Soft: {self.soft_passed}/{self.soft_total}"
        )
        return "\n".join(lines)


class GateChecker:
    """
    Check data quality gates before report generation.

    Hard gates (data must exist):
    1. ETL ran today — abc_date updated today
    2. Source data loaded today — orders for yesterday have today's dateupdate
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
        """Hard gate 1: ETL ran today (abc_date updated today)."""
        try:
            from shared.data_layer import _get_wb_connection, _get_ozon_connection, _db_cursor

            conn_factory = _get_wb_connection if marketplace == "wb" else _get_ozon_connection
            col = self._col(marketplace, "dateupdate")
            with _db_cursor(conn_factory) as (conn, cur):
                cur.execute(f"SELECT MAX({col}) FROM abc_date")
                row = cur.fetchone()
                last_update = row[0] if row else None

            today = get_today_msk()
            passed = last_update is not None and (
                last_update == today or
                (hasattr(last_update, 'date') and last_update.date() == today)
            )

            self._gates.append(GateResult(
                name="ETL ran today",
                passed=passed,
                is_hard=True,
                detail=f"Last ETL update: {last_update}, today: {today}",
            ))
        except Exception as e:
            self._gates.append(GateResult(
                name="ETL ran today",
                passed=False,
                is_hard=True,
                detail=f"Check failed: {e}",
            ))

    def _check_source_loaded_today(self, marketplace: str) -> None:
        """Hard gate 2: Orders for yesterday were loaded by today's ETL."""
        try:
            from shared.data_layer import _get_wb_connection, _get_ozon_connection, _db_cursor

            conn_factory = _get_wb_connection if marketplace == "wb" else _get_ozon_connection
            cfg = self._ORDERS_CONFIG[marketplace]
            yesterday = get_yesterday_msk()
            today = get_today_msk()

            with _db_cursor(conn_factory) as (conn, cur):
                cur.execute(
                    f"SELECT COUNT(*) FROM {cfg['table']} "
                    f"WHERE {cfg['date_col']} = %s AND dateupdate::date = %s",
                    (yesterday, today),
                )
                row = cur.fetchone()
                count = int(row[0]) if row else 0

            passed = count > 0

            self._gates.append(GateResult(
                name="Source data loaded today",
                passed=passed,
                is_hard=True,
                value=count,
                detail=f"Orders for {yesterday} loaded today: {count} rows"
                    if passed else f"No orders for {yesterday} loaded today",
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
            ))
        except Exception as e:
            self._gates.append(GateResult(
                name="Margin fill",
                passed=True,
                is_hard=False,
                detail=f"Check skipped: {e}",
            ))
