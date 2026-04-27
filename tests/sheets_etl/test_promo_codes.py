import json
from decimal import Decimal
from pathlib import Path

from services.sheets_etl.transformers.promo_codes import transform


def test_transform_first_3_rows():
    data = json.loads((Path(__file__).parent / "fixtures/promo_codes_first_3.json").read_text())
    rows = transform(data["values"])
    assert rows, "No rows transformed"
    r0 = rows[0]
    assert r0["code"] == "CHARLOTTE10"
    assert r0["channel"] == "Соцсети"
    assert r0["discount_pct"] == Decimal("10")
    assert r0["external_uuid"] == "be6900f2-c9e9-4963-9ad1-27d10d9492d6"
    assert r0["sheet_row_id"]
    assert len(r0["sheet_row_id"]) == 32
