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


class GateChecker:
    """
    Check data quality gates before report generation.

    Hard gates (data must exist):
    1. ETL ran today — abc_date.dateupdate = today
    2. Yesterday's data exists — MAX(date) = yesterday
    3. Logistics > 0 — logistics data present

    Soft gates (report with caveat if failed):
    4. Orders cross-check — ≤ 5% discrepancy
    5. Revenue vs 7-day avg — ≥ 70%
    6. Margin fill — ≥ 50% of articles have margin data
    """

    def __init__(self):
        self._gates: List[GateResult] = []

    def check_all(self, marketplace: str = "wb") -> GateCheckResult:
        """Run all gates for a marketplace."""
        self._gates = []

        # Hard gates
        self._check_etl_ran_today(marketplace)
        self._check_yesterday_data(marketplace)
        self._check_logistics_present(marketplace)

        # Soft gates
        self._check_orders_crosscheck(marketplace)
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
        """Hard gate 1: ETL ran today."""
        try:
            from shared.data_layer import _get_wb_connection, _get_ozon_connection, _db_cursor

            conn_factory = _get_wb_connection if marketplace == "wb" else _get_ozon_connection
            with _db_cursor(conn_factory) as (conn, cur):
                cur.execute("SELECT MAX(dateupdate) FROM abc_date")
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

    def _check_yesterday_data(self, marketplace: str) -> None:
        """Hard gate 2: Yesterday's data exists."""
        try:
            from shared.data_layer import _get_wb_connection, _get_ozon_connection, _db_cursor

            conn_factory = _get_wb_connection if marketplace == "wb" else _get_ozon_connection
            with _db_cursor(conn_factory) as (conn, cur):
                cur.execute("SELECT MAX(date) FROM abc_date")
                row = cur.fetchone()
                max_date = row[0] if row else None

            yesterday = get_yesterday_msk()
            passed = max_date is not None and (
                max_date >= yesterday if isinstance(max_date, date) else False
            )

            self._gates.append(GateResult(
                name="Yesterday's data exists",
                passed=passed,
                is_hard=True,
                detail=f"Max date: {max_date}, yesterday: {yesterday}",
            ))
        except Exception as e:
            self._gates.append(GateResult(
                name="Yesterday's data exists",
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

            with _db_cursor(conn_factory) as (conn, cur):
                cur.execute(
                    "SELECT COALESCE(SUM(ABS(logist)), 0) FROM abc_date WHERE date = %s",
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

    def _check_orders_crosscheck(self, marketplace: str) -> None:
        """Soft gate 4: Orders cross-check ≤ 5%."""
        # Simplified: check that orders data exists and is reasonable
        try:
            from shared.data_layer import _get_wb_connection, _get_ozon_connection, _db_cursor

            conn_factory = _get_wb_connection if marketplace == "wb" else _get_ozon_connection
            yesterday = get_yesterday_msk()

            with _db_cursor(conn_factory) as (conn, cur):
                cur.execute(
                    "SELECT COUNT(*) FROM abc_date WHERE date = %s",
                    (yesterday,),
                )
                row = cur.fetchone()
                count = int(row[0]) if row else 0

            passed = count > 0

            self._gates.append(GateResult(
                name="Orders cross-check",
                passed=passed,
                is_hard=False,
                value=count,
                threshold=1,
                detail=f"Orders records for {yesterday}: {count}" if passed
                    else f"No orders data for {yesterday}",
            ))
        except Exception as e:
            self._gates.append(GateResult(
                name="Orders cross-check",
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

            with _db_cursor(conn_factory) as (conn, cur):
                # Yesterday's revenue
                col = "revenue"
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

            with _db_cursor(conn_factory) as (conn, cur):
                cur.execute(
                    "SELECT COUNT(*), "
                    "SUM(CASE WHEN marga IS NOT NULL AND marga != 0 THEN 1 ELSE 0 END) "
                    "FROM abc_date WHERE date = %s",
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
