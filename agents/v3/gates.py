"""
Gate checker for Wookiee v3 — validates data quality before report generation.

Hard gates block report generation if failed.
Soft gates allow generation but add caveats.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

from shared.data_layer import _get_wb_connection, _get_ozon_connection, _db_cursor

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Time helpers (Moscow timezone, inline — no v2 imports)
# ---------------------------------------------------------------------------
_MSK = timezone(timedelta(hours=3))


def get_today_msk() -> date:
    return datetime.now(_MSK).date()


def get_yesterday_msk() -> date:
    return get_today_msk() - timedelta(days=1)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------
@dataclass
class GateResult:
    name: str
    passed: bool
    is_hard: bool
    value: float | None = None
    threshold: float | None = None
    detail: str = ""
    extra: dict = field(default_factory=dict)


@dataclass
class GateCheckResult:
    gates: list[GateResult]
    can_generate: bool        # all hard gates passed
    has_caveats: bool         # any soft gate failed
    caveats: list[str]        # warning messages

    def format_status_message(self) -> str:
        """Format gate results for Telegram notification."""
        lines: list[str] = []
        if self.can_generate and not self.has_caveats:
            lines.append("✅ Все проверки пройдены")
        elif self.can_generate and self.has_caveats:
            lines.append("⚠️ Отчёт готов с оговорками")
        else:
            lines.append("❌ Отчёт заблокирован")

        for g in self.gates:
            icon = "✅" if g.passed else ("❌" if g.is_hard else "⚠️")
            line = f"{icon} {g.name}"
            if g.detail:
                line += f": {g.detail}"
            lines.append(line)

        if self.caveats:
            lines.append("")
            lines.append("Оговорки:")
            for c in self.caveats:
                lines.append(f"• {c}")

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Column / table mapping per marketplace
# ---------------------------------------------------------------------------
_COLUMN_MAP = {
    "wb":   {"dateupdate": "dateupdate",  "logistics": "logist",     "revenue": "revenue",   "marga": "marga"},
    "ozon": {"dateupdate": "date_update", "logistics": "logist_end", "revenue": "price_end", "marga": "marga"},
}

_ORDERS_CONFIG = {
    "wb":   {"table": "orders", "date_col": "date::date"},
    "ozon": {"table": "orders", "date_col": "in_process_at::date"},
}


# ---------------------------------------------------------------------------
# GateChecker
# ---------------------------------------------------------------------------
class GateChecker:
    """Run hard + soft data-quality gates for a marketplace."""

    def _conn_factory(self, marketplace: str):
        return _get_wb_connection if marketplace == "wb" else _get_ozon_connection

    def _cols(self, marketplace: str) -> dict:
        return _COLUMN_MAP[marketplace]

    def _orders(self, marketplace: str) -> dict:
        return _ORDERS_CONFIG[marketplace]

    # ---- hard gates -------------------------------------------------------

    def _gate_etl_ran_today(self, marketplace: str) -> GateResult:
        """Hard gate 1: ETL ran today — abc_date has update for yesterday with today's dateupdate."""
        cols = self._cols(marketplace)
        yesterday = get_yesterday_msk()
        today = get_today_msk()
        try:
            with _db_cursor(self._conn_factory(marketplace)) as (_conn, cur):
                cur.execute(
                    f"SELECT MAX({cols['dateupdate']}) FROM abc_date WHERE date = %s",
                    (yesterday,),
                )
                row = cur.fetchone()
                max_update = row[0] if row else None

            if max_update is None:
                return GateResult(
                    name=f"ETL ran today ({marketplace})",
                    passed=False, is_hard=True,
                    detail=f"Нет данных abc_date за {yesterday}",
                )

            # max_update may be date or datetime — normalise to date
            update_date = max_update if isinstance(max_update, date) and not isinstance(max_update, datetime) else max_update.date() if isinstance(max_update, datetime) else max_update
            passed = update_date == today
            return GateResult(
                name=f"ETL ran today ({marketplace})",
                passed=passed, is_hard=True,
                value=None, threshold=None,
                detail=f"Последнее обновление: {update_date}, ожидалось: {today}",
            )
        except Exception as e:
            logger.exception("gate_etl_ran_today %s failed", marketplace)
            return GateResult(
                name=f"ETL ran today ({marketplace})",
                passed=False, is_hard=True,
                detail=f"Ошибка: {e}",
            )

    def _gate_source_data_loaded(self, marketplace: str) -> GateResult:
        """Hard gate 2: Source data loaded — yesterday orders >= 30% of 7-day avg."""
        ocfg = self._orders(marketplace)
        yesterday = get_yesterday_msk()
        week_ago = yesterday - timedelta(days=7)
        try:
            with _db_cursor(self._conn_factory(marketplace)) as (_conn, cur):
                # Yesterday count
                cur.execute(
                    f"SELECT COUNT(*) FROM {ocfg['table']} WHERE {ocfg['date_col']} = %s",
                    (yesterday,),
                )
                yesterday_count = cur.fetchone()[0] or 0

                # 7-day average
                cur.execute(
                    f"SELECT COUNT(*)::float / 7 FROM {ocfg['table']} "
                    f"WHERE {ocfg['date_col']} BETWEEN %s AND %s",
                    (week_ago, yesterday - timedelta(days=1)),
                )
                avg_count = cur.fetchone()[0] or 0

            ratio = (yesterday_count / avg_count) if avg_count > 0 else 0
            passed = ratio >= 0.30
            return GateResult(
                name=f"Source data loaded ({marketplace})",
                passed=passed, is_hard=True,
                value=round(ratio * 100, 1), threshold=30.0,
                detail=f"Вчера: {yesterday_count}, среднее 7д: {avg_count:.0f}, ratio: {ratio:.1%}",
            )
        except Exception as e:
            logger.exception("gate_source_data_loaded %s failed", marketplace)
            return GateResult(
                name=f"Source data loaded ({marketplace})",
                passed=False, is_hard=True,
                detail=f"Ошибка: {e}",
            )

    def _gate_logistics_positive(self, marketplace: str) -> GateResult:
        """Hard gate 3: Logistics > 0."""
        cols = self._cols(marketplace)
        yesterday = get_yesterday_msk()
        try:
            with _db_cursor(self._conn_factory(marketplace)) as (_conn, cur):
                cur.execute(
                    f"SELECT COALESCE(SUM(ABS({cols['logistics']})), 0) FROM abc_date WHERE date = %s",
                    (yesterday,),
                )
                total = float(cur.fetchone()[0] or 0)

            passed = total > 0
            return GateResult(
                name=f"Logistics > 0 ({marketplace})",
                passed=passed, is_hard=True,
                value=total, threshold=0,
                detail=f"Сумма логистики: {total:.0f}",
            )
        except Exception as e:
            logger.exception("gate_logistics_positive %s failed", marketplace)
            return GateResult(
                name=f"Logistics > 0 ({marketplace})",
                passed=False, is_hard=True,
                detail=f"Ошибка: {e}",
            )

    # ---- soft gates -------------------------------------------------------

    def _gate_orders_volume(self, marketplace: str) -> GateResult:
        """Soft gate 4: Yesterday orders vs 7-day avg >= 70%."""
        ocfg = self._orders(marketplace)
        yesterday = get_yesterday_msk()
        week_ago = yesterday - timedelta(days=7)
        try:
            with _db_cursor(self._conn_factory(marketplace)) as (_conn, cur):
                cur.execute(
                    f"SELECT COUNT(*) FROM {ocfg['table']} WHERE {ocfg['date_col']} = %s",
                    (yesterday,),
                )
                yesterday_count = cur.fetchone()[0] or 0

                cur.execute(
                    f"SELECT COUNT(*)::float / 7 FROM {ocfg['table']} "
                    f"WHERE {ocfg['date_col']} BETWEEN %s AND %s",
                    (week_ago, yesterday - timedelta(days=1)),
                )
                avg_count = cur.fetchone()[0] or 0

            ratio = (yesterday_count / avg_count) if avg_count > 0 else 0
            passed = ratio >= 0.70
            return GateResult(
                name=f"Orders volume ({marketplace})",
                passed=passed, is_hard=False,
                value=round(ratio * 100, 1), threshold=70.0,
                detail=f"Вчера: {yesterday_count}, среднее 7д: {avg_count:.0f}, ratio: {ratio:.1%}",
            )
        except Exception as e:
            logger.exception("gate_orders_volume %s failed", marketplace)
            return GateResult(
                name=f"Orders volume ({marketplace})",
                passed=False, is_hard=False,
                detail=f"Ошибка: {e}",
            )

    def _gate_revenue_vs_avg(self, marketplace: str) -> GateResult:
        """Soft gate 5: Yesterday revenue vs 7-day avg >= 70%."""
        cols = self._cols(marketplace)
        yesterday = get_yesterday_msk()
        week_ago = yesterday - timedelta(days=7)
        try:
            with _db_cursor(self._conn_factory(marketplace)) as (_conn, cur):
                cur.execute(
                    f"SELECT COALESCE(SUM({cols['revenue']}), 0) FROM abc_date WHERE date = %s",
                    (yesterday,),
                )
                yesterday_rev = float(cur.fetchone()[0] or 0)

                cur.execute(
                    f"SELECT COALESCE(SUM({cols['revenue']}), 0) / 7 FROM abc_date "
                    f"WHERE date BETWEEN %s AND %s",
                    (week_ago, yesterday - timedelta(days=1)),
                )
                avg_rev = float(cur.fetchone()[0] or 0)

            ratio = (yesterday_rev / avg_rev) if avg_rev > 0 else 0
            passed = ratio >= 0.70
            return GateResult(
                name=f"Revenue vs avg ({marketplace})",
                passed=passed, is_hard=False,
                value=round(ratio * 100, 1), threshold=70.0,
                detail=f"Вчера: {yesterday_rev:.0f}, среднее 7д: {avg_rev:.0f}, ratio: {ratio:.1%}",
            )
        except Exception as e:
            logger.exception("gate_revenue_vs_avg %s failed", marketplace)
            return GateResult(
                name=f"Revenue vs avg ({marketplace})",
                passed=False, is_hard=False,
                detail=f"Ошибка: {e}",
            )

    def _gate_margin_fill(self, marketplace: str) -> GateResult:
        """Soft gate 6: % of articles with margin != 0 >= 50%."""
        cols = self._cols(marketplace)
        yesterday = get_yesterday_msk()
        try:
            with _db_cursor(self._conn_factory(marketplace)) as (_conn, cur):
                cur.execute(
                    f"SELECT COUNT(*), COUNT(*) FILTER (WHERE {cols['marga']} != 0) "
                    f"FROM abc_date WHERE date = %s",
                    (yesterday,),
                )
                row = cur.fetchone()
                total = row[0] or 0
                filled = row[1] or 0

            pct = (filled / total * 100) if total > 0 else 0
            passed = pct >= 50
            return GateResult(
                name=f"Margin fill ({marketplace})",
                passed=passed, is_hard=False,
                value=round(pct, 1), threshold=50.0,
                detail=f"С маржой: {filled}/{total} ({pct:.1f}%)",
            )
        except Exception as e:
            logger.exception("gate_margin_fill %s failed", marketplace)
            return GateResult(
                name=f"Margin fill ({marketplace})",
                passed=False, is_hard=False,
                detail=f"Ошибка: {e}",
            )

    # ---- public API -------------------------------------------------------

    def check_all(self, marketplace: str = "wb") -> GateCheckResult:
        """Run all 6 gates for a single marketplace."""
        gates = [
            self._gate_etl_ran_today(marketplace),
            self._gate_source_data_loaded(marketplace),
            self._gate_logistics_positive(marketplace),
            self._gate_orders_volume(marketplace),
            self._gate_revenue_vs_avg(marketplace),
            self._gate_margin_fill(marketplace),
        ]

        hard_failed = [g for g in gates if g.is_hard and not g.passed]
        soft_failed = [g for g in gates if not g.is_hard and not g.passed]

        caveats = [f"{g.name}: {g.detail}" for g in soft_failed]

        return GateCheckResult(
            gates=gates,
            can_generate=len(hard_failed) == 0,
            has_caveats=len(soft_failed) > 0,
            caveats=caveats,
        )

    def check_both(self) -> GateCheckResult:
        """Run gates for WB + OZON, merge results."""
        wb = self.check_all("wb")
        ozon = self.check_all("ozon")

        all_gates = wb.gates + ozon.gates
        can_generate = wb.can_generate and ozon.can_generate
        caveats = wb.caveats + ozon.caveats

        return GateCheckResult(
            gates=all_gates,
            can_generate=can_generate,
            has_caveats=len(caveats) > 0,
            caveats=caveats,
        )
