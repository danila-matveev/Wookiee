"""Хранилище истории расчётов WB Logistics (SQLite)."""
from __future__ import annotations

import json
import logging
import shutil
import sqlite3
from datetime import date
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent / "data"
_OLD_DB = DATA_DIR / "vasily.db"
_NEW_DB = DATA_DIR / "wb_logistics.db"
_DEFAULT_TIMEOUT = 5.0  # seconds


def _get_db_path() -> Path:
    """Get DB path, migrating from old name if needed."""
    if _NEW_DB.exists():
        return _NEW_DB
    if _OLD_DB.exists():
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copy2(_OLD_DB, _NEW_DB)
        logger.info("Мигрирована БД: vasily.db → wb_logistics.db")
        return _NEW_DB
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return _NEW_DB


_DEFAULT_DB = _get_db_path()

_SCHEMA = """
CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cabinet TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    report_path TEXT,
    overall_index REAL,
    total_sku INTEGER,
    sku_with_orders INTEGER,
    movements_count INTEGER,
    movements_qty INTEGER,
    supplies_count INTEGER,
    supplies_qty INTEGER,
    regions_json TEXT,
    top_problems_json TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_reports_cabinet ON reports(cabinet);
CREATE INDEX IF NOT EXISTS idx_reports_timestamp ON reports(cabinet, timestamp DESC);

CREATE TABLE IF NOT EXISTS weekly_snapshots (
    cabinet TEXT NOT NULL,
    week_start DATE NOT NULL,
    article TEXT NOT NULL,
    region TEXT NOT NULL,
    local_orders INTEGER NOT NULL DEFAULT 0,
    nonlocal_orders INTEGER NOT NULL DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (cabinet, week_start, article, region)
);

CREATE INDEX IF NOT EXISTS idx_weekly_snapshots_cabinet_week
ON weekly_snapshots (cabinet, week_start DESC);
"""


class History:
    """SQLite-хранилище истории расчётов.

    Файл: services/wb_localization/data/wb_logistics.db
    Таблица: reports — один ряд на расчёт (кабинет × дата).
    """

    def __init__(self, db_path: Path | None = None, timeout: float = _DEFAULT_TIMEOUT):
        self._db_path = db_path or _DEFAULT_DB
        self._timeout = timeout
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self._auto_migrate()
        self._ensure_irp_columns()

    @property
    def db_path(self) -> Path:
        """Путь к SQLite-файлу (read-only)."""
        return self._db_path

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path), timeout=self._timeout)
        conn.execute(f"PRAGMA busy_timeout={int(self._timeout * 1000)}")
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._get_conn() as conn:
            conn.executescript(_SCHEMA)

    _IRP_COLUMNS = [
        ("il_current", "REAL", "1.0"),
        ("irp_current", "REAL", "0.0"),
        ("irp_zone_sku", "INTEGER", "0"),
        ("il_zone_sku", "INTEGER", "0"),
        ("irp_impact_rub_month", "REAL", "0.0"),
    ]

    def _ensure_irp_columns(self) -> None:
        """Add IRP columns if they don't exist (safe ALTER TABLE migration)."""
        with self._get_conn() as conn:
            existing = {row[1] for row in conn.execute("PRAGMA table_info(reports)").fetchall()}
            for col_name, col_type, default in self._IRP_COLUMNS:
                if col_name not in existing:
                    conn.execute(
                        f"ALTER TABLE reports ADD COLUMN {col_name} {col_type} DEFAULT {default}"
                    )
                    logger.info("Миграция: добавлена колонка reports.%s", col_name)

    def _auto_migrate(self) -> None:
        """Одноразовая миграция из history.json (если файл существует)."""
        json_path = self._db_path.parent / "history.json"
        if not json_path.exists():
            return
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
            runs = data.get("runs", [])
            if not runs:
                json_path.unlink()
                return
            count = self._migrate_records(runs)
            # Переименовать старый файл вместо удаления
            backup = json_path.with_suffix(".json.bak")
            json_path.rename(backup)
            logger.info("Мигрировано %d записей из history.json → SQLite (бэкап: %s)",
                        count, backup.name)
        except Exception as e:
            logger.warning("Ошибка миграции history.json: %s", e)

    def _migrate_records(self, runs: list[dict]) -> int:
        """Вставить записи из JSON в SQLite."""
        count = 0
        with self._get_conn() as conn:
            for run in runs:
                summary = run.get("summary", {})
                conn.execute(
                    """INSERT INTO reports
                       (cabinet, timestamp, report_path,
                        overall_index, total_sku, sku_with_orders,
                        movements_count, movements_qty,
                        supplies_count, supplies_qty,
                        regions_json, top_problems_json)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        run.get("cabinet", ""),
                        run.get("timestamp", ""),
                        run.get("report_path", ""),
                        summary.get("overall_index", 0),
                        summary.get("total_sku", 0),
                        summary.get("sku_with_orders", 0),
                        summary.get("movements_count", 0),
                        summary.get("movements_qty", 0),
                        summary.get("supplies_count", 0),
                        summary.get("supplies_qty", 0),
                        json.dumps(run.get("regions", []), ensure_ascii=False),
                        json.dumps(run.get("top_problems", []), ensure_ascii=False),
                    ),
                )
                count += 1
        return count

    # ------------------------------------------------------------------
    # Публичный API (тот же интерфейс, что был у JSON-версии)
    # ------------------------------------------------------------------

    def save_run(self, result: dict) -> None:
        """Сохранить результат расчёта."""
        summary = result.get("summary", {})
        with self._get_conn() as conn:
            conn.execute(
                """INSERT INTO reports
                   (cabinet, timestamp, report_path,
                    overall_index, total_sku, sku_with_orders,
                    movements_count, movements_qty,
                    supplies_count, supplies_qty,
                    regions_json, top_problems_json,
                    il_current, irp_current, irp_zone_sku,
                    il_zone_sku, irp_impact_rub_month)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    result.get("cabinet", ""),
                    result.get("timestamp", ""),
                    result.get("report_path", ""),
                    summary.get("overall_index", 0),
                    summary.get("total_sku", 0),
                    summary.get("sku_with_orders", 0),
                    summary.get("movements_count", 0),
                    summary.get("movements_qty", 0),
                    summary.get("supplies_count", 0),
                    summary.get("supplies_qty", 0),
                    json.dumps(result.get("regions", []), ensure_ascii=False),
                    json.dumps(result.get("top_problems", [])[:10], ensure_ascii=False),
                    summary.get("il_current", 1.0),
                    summary.get("irp_current", 0.0),
                    summary.get("irp_zone_sku", 0),
                    summary.get("il_zone_sku", 0),
                    summary.get("irp_impact_rub_month", 0.0),
                ),
            )
        logger.info("Сохранён расчёт %s от %s", result.get("cabinet"), result.get("timestamp"))

    def get_latest(self, cabinet: str) -> dict | None:
        """Последний расчёт для кабинета."""
        with self._get_conn() as conn:
            row = conn.execute(
                """SELECT * FROM reports
                   WHERE LOWER(cabinet) = LOWER(?)
                   ORDER BY timestamp DESC LIMIT 1""",
                (cabinet,),
            ).fetchone()
        return self._row_to_dict(row) if row else None

    def get_history(self, cabinet: str, limit: int = 10) -> list[dict]:
        """История расчётов для кабинета (последние N)."""
        with self._get_conn() as conn:
            rows = conn.execute(
                """SELECT * FROM reports
                   WHERE LOWER(cabinet) = LOWER(?)
                   ORDER BY timestamp DESC LIMIT ?""",
                (cabinet, limit),
            ).fetchall()
        return [self._row_to_dict(r) for r in reversed(rows)]

    def get_all_runs(self) -> list[dict]:
        """Вся история."""
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM reports ORDER BY timestamp ASC"
            ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Weekly snapshots (для forecast локализации на 13 недель вперёд)
    # ------------------------------------------------------------------

    def save_weekly_snapshots(
        self,
        cabinet: str,
        week_start: date,
        snapshots: list[dict[str, Any]],
    ) -> None:
        """Сохраняет понедельные снапшоты локализации.

        Idempotent: UPSERT по (cabinet, week_start, article, region).

        Args:
            cabinet: Идентификатор кабинета.
            week_start: Начало ISO-недели (понедельник).
            snapshots: Список с полями article, region, local_orders, nonlocal_orders.
        """
        if not snapshots:
            return
        week_iso = week_start.isoformat()
        with self._get_conn() as conn:
            conn.executemany(
                """INSERT INTO weekly_snapshots
                   (cabinet, week_start, article, region,
                    local_orders, nonlocal_orders, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                   ON CONFLICT(cabinet, week_start, article, region)
                   DO UPDATE SET
                       local_orders = excluded.local_orders,
                       nonlocal_orders = excluded.nonlocal_orders,
                       updated_at = CURRENT_TIMESTAMP""",
                [
                    (
                        cabinet,
                        week_iso,
                        snap["article"],
                        snap["region"],
                        int(snap.get("local_orders", 0)),
                        int(snap.get("nonlocal_orders", 0)),
                    )
                    for snap in snapshots
                ],
            )
        logger.info(
            "Сохранено %d weekly-снапшотов для %s (week_start=%s)",
            len(snapshots), cabinet, week_iso,
        )

    def get_weekly_snapshots(
        self,
        cabinet: str,
        weeks_back: int = 13,
    ) -> list[dict[str, Any]]:
        """Возвращает снапшоты за последние weeks_back недель.

        Args:
            cabinet: Идентификатор кабинета.
            weeks_back: Сколько последних ISO-недель вернуть.

        Returns:
            Список словарей {cabinet, week_start, article, region,
            local_orders, nonlocal_orders}. Отсортирован по week_start DESC.
        """
        with self._get_conn() as conn:
            rows = conn.execute(
                """SELECT cabinet, week_start, article, region,
                          local_orders, nonlocal_orders
                   FROM weekly_snapshots
                   WHERE LOWER(cabinet) = LOWER(?)
                     AND week_start IN (
                         SELECT DISTINCT week_start
                         FROM weekly_snapshots
                         WHERE LOWER(cabinet) = LOWER(?)
                         ORDER BY week_start DESC
                         LIMIT ?
                     )
                   ORDER BY week_start DESC, article, region""",
                (cabinet, cabinet, weeks_back),
            ).fetchall()
        return [
            {
                "cabinet": row["cabinet"],
                "week_start": row["week_start"],
                "article": row["article"],
                "region": row["region"],
                "local_orders": row["local_orders"],
                "nonlocal_orders": row["nonlocal_orders"],
            }
            for row in rows
        ]

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict:
        """Преобразовать строку SQLite в dict (совместимый со старым форматом)."""
        keys = row.keys()
        return {
            "cabinet": row["cabinet"],
            "timestamp": row["timestamp"],
            "report_path": row["report_path"],
            "summary": {
                "overall_index": row["overall_index"],
                "total_sku": row["total_sku"],
                "sku_with_orders": row["sku_with_orders"],
                "movements_count": row["movements_count"],
                "movements_qty": row["movements_qty"],
                "supplies_count": row["supplies_count"],
                "supplies_qty": row["supplies_qty"],
                "il_current": row["il_current"] if "il_current" in keys else 1.0,
                "irp_current": row["irp_current"] if "irp_current" in keys else 0.0,
                "irp_zone_sku": row["irp_zone_sku"] if "irp_zone_sku" in keys else 0,
                "il_zone_sku": row["il_zone_sku"] if "il_zone_sku" in keys else 0,
                "irp_impact_rub_month": row["irp_impact_rub_month"] if "irp_impact_rub_month" in keys else 0.0,
            },
            "regions": json.loads(row["regions_json"] or "[]"),
            "top_problems": json.loads(row["top_problems_json"] or "[]"),
        }
