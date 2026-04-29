import json
from pathlib import Path

from services.sheets_etl.transformers.candidates import transform


def test_transform_first_3():
    data = json.loads((Path(__file__).parent / "fixtures/candidates_first_3.json").read_text())
    rows = transform(data["values"])
    assert rows, "No candidates parsed"
    r0 = rows[0]
    assert r0["handle"]
    assert r0["status"] == "new"
    assert r0["sheet_row_id"]
    assert len(r0["sheet_row_id"]) == 32
