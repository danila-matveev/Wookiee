from services.logistics_audit.api.wb_reports import parse_report_rows
from services.logistics_audit.models.report_row import ReportRow
from services.logistics_audit.api.wb_tariffs import parse_tariff_response
from services.logistics_audit.api.wb_content import parse_cards_dimensions


def test_parse_report_rows():
    """Parse raw API response into list of ReportRow."""
    raw_data = [
        {
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
            "rrd_id": 999,
        },
    ]
    rows, last_rrd_id = parse_report_rows(raw_data)
    assert len(rows) == 1
    assert isinstance(rows[0], ReportRow)
    assert rows[0].nm_id == 257131227
    assert last_rrd_id == 999


def test_parse_empty_response():
    """Empty response → no rows, last_rrd_id = 0."""
    rows, last_rrd_id = parse_report_rows([])
    assert len(rows) == 0
    assert last_rrd_id == 0


def test_parse_tariff_response():
    raw = {
        "response": {
            "data": {
                "dtNextBox": "",
                "dtTillMax": "2026-03-26",
                "warehouseList": [
                    {
                        "warehouseName": "Коледино",
                        "boxDeliveryBase": "89,7",
                        "boxDeliveryLiter": "27,3",
                        "boxDeliveryCoefExpr": "195",
                        "boxStorageBase": "0,1",
                        "boxStorageCoefExpr": "145",
                        "boxStorageLiter": "0,1",
                        "geoName": "ЦФО",
                    },
                ],
            }
        }
    }
    tariffs = parse_tariff_response(raw)
    assert len(tariffs) == 1
    assert tariffs["Коледино"].box_delivery_base == 89.7
    assert tariffs["Коледино"].delivery_coef_pct == 195
    assert tariffs["Коледино"].storage_coef_pct == 145


def test_parse_cards_dimensions():
    raw_cards = [
        {
            "nmID": 257131227,
            "dimensions": {"width": 33, "height": 22, "length": 4},
        },
        {
            "nmID": 545069116,
            "dimensions": {"width": 15, "height": 20, "length": 3},
        },
    ]
    dims = parse_cards_dimensions(raw_cards)
    assert dims[257131227] == {"width": 33, "height": 22, "length": 4, "volume": 2.904}
    assert abs(dims[545069116]["volume"] - 0.9) < 0.001
