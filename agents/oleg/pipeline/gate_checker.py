"""
GateChecker — pre-flight data quality gates for the reliability pipeline.

3 hard gates (blocking) + 3 soft gates (warning only).

Hard gates check dateupdate freshness in the DB. If any hard gate fails,
GateChecker.check_all() returns can_run=False and the pipeline must NOT launch.

Soft gates check for expected non-zero values (advertising costs, margin fill,
logistics). Soft gate failure adds to soft_warnings but does NOT block the run.

All DB queries go through shared.data_layer._connection (_db_cursor context
manager) per AGENTS.md — no direct psycopg2 imports.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Optional

from shared.data_layer._connection import (
    _db_cursor,
    _get_ozon_connection,
    _get_wb_connection,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class GateResult:
    """Result of a single gate check."""
    name: str
    passed: bool
    detail: str = ""
    is_hard: bool = True  # hard=блокирует запуск, soft=только предупреждение


@dataclass
class CheckAllResult:
    """Aggregated result of all gate checks."""
    gates: List[GateResult] = field(default_factory=list)
    target_date: Optional[date] = None
    summary_metrics: Dict = field(default_factory=dict)

    @property
    def hard_failed(self) -> List[GateResult]:
        """Hard gates that failed (blocking)."""
        return [g for g in self.gates if g.is_hard and not g.passed]

    @property
    def soft_warnings(self) -> List[GateResult]:
        """Soft gates that failed (informational only)."""
        return [g for g in self.gates if not g.is_hard and not g.passed]

    @property
    def can_run(self) -> bool:
        """True if all hard gates passed."""
        return len(self.hard_failed) == 0


# ---------------------------------------------------------------------------
# Gate Checker
# ---------------------------------------------------------------------------

class GateChecker:
    """Pre-flight data quality gate checker.

    Compatible with DiagnosticRunner interface:
        gate_checker.check_all(marketplace) -> result
        result.gates[i].passed | .name | .detail
    """

    def check_all(
        self, marketplace: str = "wb", target_date: Optional[date] = None
    ) -> CheckAllResult:
        """Run all 6 gates (3 hard + 3 soft) and return aggregated result.

        Args:
            marketplace: "wb" or "ozon" — used to select connection factory for
                marketplace-specific gates. Financial data always uses WB connection.
            target_date: Date to check freshness against. Defaults to today.
        """
        if target_date is None:
            target_date = date.today()

        gates: List[GateResult] = []
        summary_metrics: Dict = {}

        # -----------------------------------------------------------------
        # Hard gate 1: WB orders freshness
        # -----------------------------------------------------------------
        gates.append(self._check_wb_orders_freshness(target_date))

        # -----------------------------------------------------------------
        # Hard gate 2: OZON orders freshness
        # -----------------------------------------------------------------
        gates.append(self._check_ozon_orders_freshness(target_date))

        # -----------------------------------------------------------------
        # Hard gate 3: Financial data freshness (fin_data table, WB DB)
        # -----------------------------------------------------------------
        gates.append(self._check_fin_data_freshness(target_date))

        # -----------------------------------------------------------------
        # Soft gate 1: Advertising data for target_date
        # -----------------------------------------------------------------
        gates.append(self._check_advertising_data(target_date))

        # -----------------------------------------------------------------
        # Soft gate 2: Margin fill rate
        # -----------------------------------------------------------------
        gates.append(self._check_margin_fill_rate())

        # -----------------------------------------------------------------
        # Soft gate 3: Logistics data for target_date
        # -----------------------------------------------------------------
        gates.append(self._check_logistics_data(target_date))

        return CheckAllResult(
            gates=gates,
            target_date=target_date,
            summary_metrics=summary_metrics,
        )

    # ------------------------------------------------------------------
    # Hard gates
    # ------------------------------------------------------------------

    def _check_wb_orders_freshness(self, target_date: date) -> GateResult:
        """Hard gate: WB orders dateupdate must be >= target_date."""
        name = "wb_orders_freshness"
        try:
            with _db_cursor(_get_wb_connection) as (conn, cur):
                cur.execute("SELECT MAX(dateupdate) FROM abc_date")
                row = cur.fetchone()
                last_update = row[0] if row else None

            if last_update is None:
                return GateResult(
                    name=name,
                    passed=False,
                    detail="Нет данных в abc_date (WB). ETL не запускался.",
                )

            update_date = self._normalize_date(last_update)
            if update_date < target_date:
                return GateResult(
                    name=name,
                    passed=False,
                    detail=f"Последнее обновление WB: {update_date}, ожидается: {target_date}",
                )

            return GateResult(name=name, passed=True, detail=f"Обновлено: {update_date}")

        except Exception as e:
            logger.error(f"Gate {name} error: {e}")
            return GateResult(name=name, passed=False, detail=f"Ошибка проверки: {e}")

    def _check_ozon_orders_freshness(self, target_date: date) -> GateResult:
        """Hard gate: OZON orders date_update must be >= target_date."""
        name = "ozon_orders_freshness"
        try:
            with _db_cursor(_get_ozon_connection) as (conn, cur):
                cur.execute("SELECT MAX(date_update) FROM abc_date")
                row = cur.fetchone()
                last_update = row[0] if row else None

            if last_update is None:
                return GateResult(
                    name=name,
                    passed=False,
                    detail="Нет данных в abc_date (OZON). ETL не запускался.",
                )

            update_date = self._normalize_date(last_update)
            if update_date < target_date:
                return GateResult(
                    name=name,
                    passed=False,
                    detail=f"Последнее обновление OZON: {update_date}, ожидается: {target_date}",
                )

            return GateResult(name=name, passed=True, detail=f"Обновлено: {update_date}")

        except Exception as e:
            logger.error(f"Gate {name} error: {e}")
            return GateResult(name=name, passed=False, detail=f"Ошибка проверки: {e}")

    def _check_fin_data_freshness(self, target_date: date) -> GateResult:
        """Hard gate: Financial data dateupdate must be >= target_date."""
        name = "fin_data_freshness"
        try:
            with _db_cursor(_get_wb_connection) as (conn, cur):
                cur.execute("SELECT MAX(dateupdate) FROM fin_data")
                row = cur.fetchone()
                last_update = row[0] if row else None

            if last_update is None:
                return GateResult(
                    name=name,
                    passed=False,
                    detail="Нет данных в fin_data. ETL не запускался.",
                )

            update_date = self._normalize_date(last_update)
            if update_date < target_date:
                return GateResult(
                    name=name,
                    passed=False,
                    detail=f"Последнее обновление fin_data: {update_date}, ожидается: {target_date}",
                )

            return GateResult(name=name, passed=True, detail=f"Обновлено: {update_date}")

        except Exception as e:
            logger.error(f"Gate {name} error: {e}")
            return GateResult(name=name, passed=False, detail=f"Ошибка проверки: {e}")

    # ------------------------------------------------------------------
    # Soft gates
    # ------------------------------------------------------------------

    def _check_advertising_data(self, target_date: date) -> GateResult:
        """Soft gate: advertising costs for target_date > 0."""
        name = "advertising_data"
        try:
            with _db_cursor(_get_wb_connection) as (conn, cur):
                cur.execute(
                    "SELECT COALESCE(SUM(cost), 0) FROM advertising WHERE date = %s",
                    (target_date,),
                )
                row = cur.fetchone()
                total = float(row[0]) if row and row[0] is not None else 0.0

            if total <= 0:
                return GateResult(
                    name=name,
                    passed=False,
                    detail=f"Рекламных расходов за {target_date}: 0. Данные могут не загрузиться.",
                    is_hard=False,
                )

            return GateResult(
                name=name,
                passed=True,
                detail=f"Рекламные расходы за {target_date}: {total:.0f} руб.",
                is_hard=False,
            )

        except Exception as e:
            logger.warning(f"Soft gate {name} error: {e}")
            return GateResult(
                name=name,
                passed=False,
                detail=f"Не удалось проверить рекламные данные: {e}",
                is_hard=False,
            )

    def _check_margin_fill_rate(self) -> GateResult:
        """Soft gate: fraction of articles with margin > 0 must exceed 50%."""
        name = "margin_fill_rate"
        try:
            with _db_cursor(_get_wb_connection) as (conn, cur):
                cur.execute(
                    "SELECT "
                    "  COUNT(*) FILTER (WHERE margin > 0) AS with_margin, "
                    "  COUNT(*) AS total "
                    "FROM fin_data"
                )
                row = cur.fetchone()
                with_margin = row[0] if row and row[0] is not None else 0
                total = row[1] if row and row[1] is not None else 0

            if total == 0:
                return GateResult(
                    name=name,
                    passed=False,
                    detail="Нет данных о марже (fin_data пустая).",
                    is_hard=False,
                )

            fill_rate = with_margin / total
            if fill_rate < 0.5:
                return GateResult(
                    name=name,
                    passed=False,
                    detail=(
                        f"Маржа рассчитана только для {fill_rate:.0%} артикулов "
                        f"({with_margin}/{total}). ETL мог загрузить неполные данные."
                    ),
                    is_hard=False,
                )

            return GateResult(
                name=name,
                passed=True,
                detail=f"Маржа заполнена для {fill_rate:.0%} артикулов ({with_margin}/{total}).",
                is_hard=False,
            )

        except Exception as e:
            logger.warning(f"Soft gate {name} error: {e}")
            return GateResult(
                name=name,
                passed=False,
                detail=f"Не удалось проверить заполненность маржи: {e}",
                is_hard=False,
            )

    def _check_logistics_data(self, target_date: date) -> GateResult:
        """Soft gate: logistics delivery costs for target_date > 0."""
        name = "logistics_data"
        try:
            with _db_cursor(_get_wb_connection) as (conn, cur):
                cur.execute(
                    "SELECT COALESCE(SUM(delivery_rub), 0) FROM logistics WHERE date = %s",
                    (target_date,),
                )
                row = cur.fetchone()
                total = float(row[0]) if row and row[0] is not None else 0.0

            if total <= 0:
                return GateResult(
                    name=name,
                    passed=False,
                    detail=f"Логистических расходов за {target_date}: 0. Данные могут не загрузиться.",
                    is_hard=False,
                )

            return GateResult(
                name=name,
                passed=True,
                detail=f"Логистика за {target_date}: {total:.0f} руб.",
                is_hard=False,
            )

        except Exception as e:
            logger.warning(f"Soft gate {name} error: {e}")
            return GateResult(
                name=name,
                passed=False,
                detail=f"Не удалось проверить логистические данные: {e}",
                is_hard=False,
            )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_date(val) -> date:
        """Normalize datetime/date to date. Handles D-02 pitfall from RESEARCH.md."""
        try:
            return val.date()  # works for datetime objects
        except AttributeError:
            return val          # already a date object


# ---------------------------------------------------------------------------
# Telegram pre-flight message formatter
# ---------------------------------------------------------------------------

def format_preflight_message(result: CheckAllResult, report_names: List[str]) -> str:
    """Format the pre-flight Telegram notification (D-05 format).

    Success:
        ✅ Данные за {date} готовы
        WB: | заказов {N} | выручка {X}% | маржа {Y}%
        📊 Запускаю: {report_names joined by ", "}

    Failure:
        ❌ Данные за {date} не готовы: {reasons}
    """
    target = result.target_date or date.today()
    date_str = target.strftime("%d.%m.%Y")

    if not result.can_run:
        reasons = "; ".join(g.detail for g in result.hard_failed) or "данные не загружены"
        return f"❌ Данные за {date_str} не готовы: {reasons}"

    lines = [f"✅ Данные за {date_str} готовы"]

    # Metrics from summary_metrics if available
    metrics = result.summary_metrics or {}
    wb_orders = metrics.get("wb_orders", "?")
    ozon_orders = metrics.get("ozon_orders", "?")
    wb_revenue_pct = metrics.get("wb_revenue_pct", "")
    wb_margin_pct = metrics.get("wb_margin_pct", "")
    ozon_revenue_pct = metrics.get("ozon_revenue_pct", "")
    ozon_margin_pct = metrics.get("ozon_margin_pct", "")

    wb_parts = [f"заказов {wb_orders}"]
    if wb_revenue_pct:
        wb_parts.append(f"выручка {wb_revenue_pct}%")
    if wb_margin_pct:
        wb_parts.append(f"маржа {wb_margin_pct}%")
    lines.append(f"WB: | {' | '.join(wb_parts)}")

    ozon_parts = [f"заказов {ozon_orders}"]
    if ozon_revenue_pct:
        ozon_parts.append(f"выручка {ozon_revenue_pct}%")
    if ozon_margin_pct:
        ozon_parts.append(f"маржа {ozon_margin_pct}%")
    lines.append(f"OZON: | {' | '.join(ozon_parts)}")

    if result.soft_warnings:
        warn_msgs = [f"⚠️ {g.detail}" for g in result.soft_warnings]
        lines.extend(warn_msgs)

    if report_names:
        lines.append(f"📊 Запускаю: {', '.join(report_names)}")

    return "\n".join(lines)
