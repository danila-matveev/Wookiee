from __future__ import annotations

from datetime import date
from pathlib import Path

import openpyxl

from services.logistics_audit.calculators.warehouse_coef_resolver import load_supabase_tariffs
from services.logistics_audit.etl.import_historical_tariffs import load_historical_tariff_rows
from services.logistics_audit.etl.setup_wb_tariffs import compute_gap_dates
from services.logistics_audit.etl.tariff_collector import build_tariff_rows
from services.logistics_audit.models.tariff_snapshot import TariffSnapshot


def _make_workbook(path: Path) -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Тарифы короб"
    ws.append(
        [
            "Дата",
            "Склад",
            "Коэффициент логистики, %",
            "Коэффициент хранения, %",
            None,
        ]
    )
    ws.append([date(2024, 2, 21), "Краснодар", 80, 70, None])
    ws.append([date(2024, 2, 21), "Краснодар", 85, 75, None])
    ws.append([date(2024, 2, 22), "Атакент", 90, 95, None])
    ws.append([date(2024, 2, 23), "Котовск", 100, None, None])
    wb.save(path)
    wb.close()


def test_load_historical_tariff_rows_maps_defaults_and_counts(tmp_path: Path):
    workbook_path = tmp_path / "tariffs.xlsx"
    _make_workbook(workbook_path)

    rows, stats = load_historical_tariff_rows(workbook_path)

    assert len(rows) == 3
    assert rows[0] == (
        date(2024, 2, 21),
        "Краснодар",
        80,
        0,
        0,
        0,
        0,
        70,
        "",
    )
    assert stats.raw_rows == 4
    assert stats.valid_rows == 3
    assert stats.skipped_rows == 1
    assert stats.unique_pairs == 2
    assert stats.duplicate_rows == 1
    assert stats.unique_dates == 2
    assert stats.unique_warehouses == 2
    assert stats.min_date == date(2024, 2, 21)
    assert stats.max_date == date(2024, 2, 22)


def test_compute_gap_dates_from_last_loaded_date():
    gap_dates = compute_gap_dates(date(2026, 3, 29), date(2026, 4, 2))

    assert gap_dates == [
        date(2026, 3, 30),
        date(2026, 3, 31),
        date(2026, 4, 1),
        date(2026, 4, 2),
    ]


def test_compute_gap_dates_when_table_empty():
    gap_dates = compute_gap_dates(None, date(2026, 4, 2))

    assert gap_dates == [date(2026, 4, 2)]


def test_build_tariff_rows_includes_storage_coef():
    tariffs = {
        "Коледино": TariffSnapshot(
            warehouse_name="Коледино",
            box_delivery_base=89.7,
            box_delivery_liter=27.3,
            delivery_coef_pct=195,
            box_storage_base=0.1,
            box_storage_liter=0.1,
            storage_coef_pct=145,
            geo_name="ЦФО",
        )
    }

    rows = build_tariff_rows(date(2026, 3, 20), tariffs)

    assert rows == [
        (
            date(2026, 3, 20),
            "Коледино",
            195,
            89.7,
            27.3,
            0.1,
            0,
            145,
            "ЦФО",
        )
    ]


def test_load_supabase_tariffs_uses_shared_connection_helper(monkeypatch):
    class FakeCursor:
        def execute(self, query: str, params: tuple[date, date]) -> None:
            self.query = query
            self.params = params

        def fetchall(self):
            return [
                (date(2026, 3, 20), "Коледино", 195),
                (date(2026, 3, 21), "Коледино", 205),
            ]

        def close(self) -> None:
            return None

    class FakeConnection:
        def __init__(self):
            self.cursor_instance = FakeCursor()

        def cursor(self):
            return self.cursor_instance

        def close(self) -> None:
            return None

    fake_connection = FakeConnection()

    def fake_get_supabase_connection():
        return fake_connection

    monkeypatch.setattr(
        "services.logistics_audit.calculators.warehouse_coef_resolver._get_supabase_connection",
        fake_get_supabase_connection,
    )

    result = load_supabase_tariffs(date(2026, 3, 20), date(2026, 3, 21))

    assert fake_connection.cursor_instance.params == (
        date(2026, 3, 20),
        date(2026, 3, 21),
    )
    assert result == {
        "Коледино": {
            date(2026, 3, 20): 1.95,
            date(2026, 3, 21): 2.05,
        }
    }
