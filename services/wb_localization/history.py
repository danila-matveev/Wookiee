"""Хранилище истории расчётов Василия (SQLite)."""
from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent / "data"
_DEFAULT_DB = DATA_DIR / "vasily.db"

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
"""


class History:
    """SQLite-хранилище истории расчётов.

    Файл: services/wb_localization/data/vasily.db
    Таблица: reports — один ряд на расчёт (кабинет × дата).
    """

    def __init__(self, db_path: Path | None = None):
        self._db_path = db_path or _DEFAULT_DB
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self._auto_migrate()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._get_conn() as conn:
            conn.executescript(_SCHEMA)

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
                    regions_json, top_problems_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
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

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict:
        """Преобразовать строку SQLite в dict (совместимый со старым форматом)."""
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
            },
            "regions": json.loads(row["regions_json"] or "[]"),
            "top_problems": json.loads(row["top_problems_json"] or "[]"),
        }
