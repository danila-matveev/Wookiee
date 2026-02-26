"""
DiagnosticRunner — automatic diagnostics when a report fails.

Checks: data gates, PostgreSQL, LLM API, ETL status, recent errors.
Produces a human-readable diagnostic report with fix instructions.
"""
import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class DiagCheck:
    """Single diagnostic check result."""
    component: str
    status: str    # "OK", "FAIL", "WARN"
    detail: str = ""
    fix: str = ""


@dataclass
class DiagnosticReport:
    """Full diagnostic report."""
    checks: List[DiagCheck] = field(default_factory=list)

    @property
    def has_failures(self) -> bool:
        return any(c.status == "FAIL" for c in self.checks)

    @property
    def primary_issue(self) -> Optional[DiagCheck]:
        fails = [c for c in self.checks if c.status == "FAIL"]
        return fails[0] if fails else None

    def format_telegram(self) -> str:
        """Format for Telegram alert."""
        lines = ["Диагностика завершена:\n"]
        for c in self.checks:
            icon = {"OK": "✅", "FAIL": "❌", "WARN": "⚠️"}.get(c.status, "❓")
            lines.append(f"{icon} {c.component}: {c.detail or c.status}")

        if self.has_failures:
            primary = self.primary_issue
            lines.append(f"\nПричина: {primary.detail}")
            if primary.fix:
                lines.append(f"\nКак починить:\n{primary.fix}")

        return "\n".join(lines)


class DiagnosticRunner:
    """Automatic diagnostics when report generation fails."""

    def __init__(self, gate_checker=None, state_store=None, llm_client=None):
        self.gate_checker = gate_checker
        self.state_store = state_store
        self.llm_client = llm_client

    async def diagnose(self, report_type: str = "daily", marketplace: str = "wb") -> DiagnosticReport:
        """Run full diagnostic chain."""
        checks: List[DiagCheck] = []

        # 1. Check data gates
        if self.gate_checker:
            try:
                gate_result = self.gate_checker.check_all(marketplace)
                for gate in gate_result.gates:
                    if not gate.passed:
                        checks.append(DiagCheck(
                            component=f"Data Gate: {gate.name}",
                            status="FAIL",
                            detail=gate.detail,
                            fix=self._suggest_gate_fix(gate.name),
                        ))
                    else:
                        checks.append(DiagCheck(
                            component=f"Data Gate: {gate.name}",
                            status="OK",
                        ))
            except Exception as e:
                checks.append(DiagCheck(
                    component="Data Gates",
                    status="FAIL",
                    detail=str(e),
                    fix="Проверить подключение к БД",
                ))

        # 2. Check PostgreSQL
        for db_name in ["WB", "OZON"]:
            checks.append(await self._check_postgres(db_name))

        # 3. Check LLM API
        checks.append(await self._check_llm())

        # 4. Check ETL
        checks.append(await self._check_etl(marketplace))

        # 5. Check recent errors
        if self.state_store:
            try:
                errors = self.state_store.get_recent_errors(hours=24)
                if errors:
                    checks.append(DiagCheck(
                        component="Ошибки за 24ч",
                        status="WARN",
                        detail=f"{len(errors)} ошибок",
                        fix=errors[0].get("error", "")[:200],
                    ))
                else:
                    checks.append(DiagCheck(
                        component="Ошибки за 24ч",
                        status="OK",
                        detail="Нет ошибок",
                    ))
            except Exception:
                pass

        return DiagnosticReport(checks=checks)

    async def _check_postgres(self, db_name: str) -> DiagCheck:
        """Check PostgreSQL connectivity."""
        try:
            from shared.data_layer import _get_wb_connection, _get_ozon_connection

            conn_factory = _get_wb_connection if db_name == "WB" else _get_ozon_connection
            conn = conn_factory()
            cur = conn.cursor()
            cur.execute("SELECT 1")
            cur.close()
            conn.close()

            return DiagCheck(
                component=f"PostgreSQL {db_name}",
                status="OK",
            )
        except Exception as e:
            return DiagCheck(
                component=f"PostgreSQL {db_name}",
                status="FAIL",
                detail=str(e)[:200],
                fix=f"БД {db_name} недоступна. Проверить сервер БД.",
            )

    async def _check_llm(self) -> DiagCheck:
        """Check LLM API availability."""
        if not self.llm_client:
            return DiagCheck(
                component="LLM API",
                status="WARN",
                detail="LLM client not configured",
            )

        try:
            healthy = await self.llm_client.health_check()
            if healthy:
                return DiagCheck(component="LLM API (OpenRouter)", status="OK")
            return DiagCheck(
                component="LLM API (OpenRouter)",
                status="FAIL",
                fix="OpenRouter недоступен. Проверить API ключ.",
            )
        except Exception as e:
            return DiagCheck(
                component="LLM API",
                status="FAIL",
                detail=str(e)[:200],
                fix="Проверить OPENROUTER_API_KEY и доступность API.",
            )

    async def _check_etl(self, marketplace: str = "wb") -> DiagCheck:
        """Check when ETL last ran."""
        try:
            from shared.data_layer import _get_wb_connection, _get_ozon_connection, _db_cursor

            conn_factory = _get_wb_connection if marketplace == "wb" else _get_ozon_connection
            dateupdate_col = "dateupdate" if marketplace == "wb" else "date_update"

            with _db_cursor(conn_factory) as (conn, cur):
                cur.execute(f"SELECT MAX({dateupdate_col}) FROM abc_date")
                row = cur.fetchone()
                last_update = row[0] if row else None

            today = date.today()
            if last_update is None:
                return DiagCheck(
                    component="ETL загрузка",
                    status="FAIL",
                    detail="Нет данных в abc_date.dateupdate",
                    fix="ETL никогда не запускался. Проверить контейнер ETL.",
                )

            # Normalize: datetime → date (datetime is subclass of date, so isinstance check is unreliable)
            update_date = last_update.date() if isinstance(last_update, datetime) else last_update
            if update_date < today:
                return DiagCheck(
                    component="ETL загрузка",
                    status="FAIL",
                    detail=f"Последнее обновление: {update_date}",
                    fix=(
                        f"ETL не запускался сегодня. Проверить контейнер:\n"
                        f"1. docker logs wookiee-etl\n"
                        f"2. docker restart wookiee-etl"
                    ),
                )

            return DiagCheck(
                component="ETL загрузка",
                status="OK",
                detail=f"Последнее обновление: {update_date}",
            )
        except Exception as e:
            return DiagCheck(
                component="ETL загрузка",
                status="WARN",
                detail=f"Check failed: {e}",
            )

    def _suggest_gate_fix(self, gate_name: str) -> str:
        """Suggest fix based on gate name."""
        fixes = {
            "ETL ran today": (
                "ETL не загрузил данные сегодня.\n"
                "1. docker logs wookiee-etl\n"
                "2. docker restart wookiee-etl"
            ),
            "Yesterday's data exists": (
                "Нет данных за вчера в abc_date.\n"
                "Проверить ETL загрузку."
            ),
            "Logistics > 0": (
                "Нет данных о логистике.\n"
                "Возможно ETL загрузил частичные данные."
            ),
            "Margin fill": (
                "Маржа рассчитана для малого % артикулов.\n"
                "ETL мог загрузить неполные данные."
            ),
        }
        return fixes.get(gate_name, "Проверить компонент вручную.")
