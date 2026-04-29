import json
from pathlib import Path

from services.sheets_etl.transformers.substitute_articles import transform


def test_transform_extracts_articles_and_metrics():
    data = json.loads((Path(__file__).parent / "fixtures/substitute_articles_first_3.json").read_text())
    articles, metrics = transform(data["values"])
    assert articles, "No articles parsed"

    codes = {a["code"] for a in articles}
    assert "Wendy/white" in codes
    assert "Audrey/total_white" in codes

    a = next(a for a in articles if a["code"] == "Wendy/white")
    assert a["purpose"] == "yandex"
    assert a["status"] == "active"
    assert a["sheet_row_id"]
    assert len(a["sheet_row_id"]) == 32

    purposes = {a["purpose"] for a in articles}
    assert purposes <= {"yandex", "vk_target", "adblogger", "creators", "other"}

    for m in metrics:
        assert m["sub_code_ref"] in codes
        assert m["week_start"] is not None
