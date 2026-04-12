from datetime import date, datetime


def test_report_row_from_api_dict():
    """Parse a real API row into ReportRow dataclass."""
    raw = {
        "realizationreport_id": 658038623,
        "nm_id": 257131227,
        "office_name": "Коледино",
        "supplier_oper_name": "Логистика",
        "bonus_type_name": "К клиенту при продаже",
        "delivery_rub": 147.23,
        "dlv_prc": 1.95,
        "fix_tariff_date_from": "2025-12-11",
        "fix_tariff_date_to": "2026-02-09",
        "order_dt": "2026-02-28T00:00:00",
        "shk_id": 41793344171,
        "srid": "20966880121115600.0.0",
        "gi_id": 12345,
        "gi_box_type_name": "Микс",
        "storage_fee": 0,
        "penalty": 0,
        "deduction": 0,
        "rebill_logistic_cost": 0,
        "ppvz_for_pay": 1234.56,
        "ppvz_supplier_name": "ООО Вуки",
        "retail_amount": 2000.0,
        "date_from": "2026-03-09",
        "date_to": "2026-03-15",
        "doc_type_name": "Продажа",
        "acceptance": 0,
    }
    from services.logistics_audit.models.report_row import ReportRow
    row = ReportRow.from_api(raw)
    assert row.nm_id == 257131227
    assert row.delivery_rub == 147.23
    assert row.dlv_prc == 1.95
    assert row.order_dt == date(2026, 2, 28)
    assert row.fix_tariff_date_to == date(2026, 2, 9)
    assert row.is_logistics is True
    assert row.is_fixed_rate is False


def test_report_row_fixed_rate():
    """Rows with 'От клиента при отмене' are fixed-rate."""
    raw = {
        "supplier_oper_name": "Логистика",
        "bonus_type_name": "От клиента при отмене",
        "delivery_rub": 50.0,
        "dlv_prc": 0,
        "nm_id": 123,
        "office_name": "Тула",
        "order_dt": "2026-03-01T00:00:00",
        "fix_tariff_date_from": "",
        "fix_tariff_date_to": "",
    }
    from services.logistics_audit.models.report_row import ReportRow
    row = ReportRow.from_api(raw)
    assert row.is_fixed_rate is True


def test_tariff_snapshot_parse_russian_decimal():
    """Parse Russian-format decimals: '89,7' → 89.7"""
    from services.logistics_audit.models.tariff_snapshot import TariffSnapshot
    raw = {
        "warehouseName": "Коледино",
        "boxDeliveryBase": "89,7",
        "boxDeliveryLiter": "27,3",
        "boxDeliveryCoefExpr": "195",
        "boxStorageBase": "0,1",
        "boxStorageCoefExpr": "145",
        "boxStorageLiter": "0,1",
        "geoName": "ЦФО",
    }
    snap = TariffSnapshot.from_api(raw)
    assert snap.warehouse_name == "Коледино"
    assert snap.box_delivery_base == 89.7
    assert snap.box_delivery_liter == 27.3
    assert snap.delivery_coef_pct == 195
    assert snap.storage_coef_pct == 145


def test_tariff_snapshot_dash_value():
    """'-' values (marketplace unavailable) parse as 0."""
    from services.logistics_audit.models.tariff_snapshot import TariffSnapshot
    raw = {
        "warehouseName": "Электросталь",
        "boxDeliveryBase": "73,6",
        "boxDeliveryLiter": "22,4",
        "boxDeliveryCoefExpr": "160",
        "boxDeliveryMarketplaceBase": "-",
        "boxDeliveryMarketplaceCoefExpr": "-",
        "boxDeliveryMarketplaceLiter": "-",
        "boxStorageBase": "0,08",
        "boxStorageCoefExpr": "115",
        "boxStorageLiter": "0,08",
        "geoName": "ЦФО",
    }
    snap = TariffSnapshot.from_api(raw)
    assert snap.box_delivery_base == 73.6


def test_audit_config():
    from services.logistics_audit.models.audit_config import AuditConfig
    cfg = AuditConfig(
        api_key="test_key",
        date_from=date(2026, 3, 9),
        date_to=date(2026, 3, 15),
        ktr=1.04,
        base_tariff_1l=46.0,
        base_tariff_extra_l=14.0,
    )
    assert cfg.ktr == 1.04
    assert cfg.base_tariff_1l == 46.0
