import json
from pathlib import Path

from services.sheets_etl.transformers.bloggers import transform


def test_transform_first_3():
    data = json.loads((Path(__file__).parent / "fixtures/bloggers_first_3.json").read_text())
    bloggers, channels = transform(data["values"])
    assert bloggers, "No bloggers parsed"
    b0 = bloggers[0]
    assert b0["display_handle"] == "sofiimarvel"
    assert b0["sheet_row_id"]
    handles = [c for c in channels if c["display_handle_ref"] == "sofiimarvel"]
    assert len(handles) == 2
    by_kind = {c["channel"]: c for c in handles}
    assert by_kind["instagram"]["url"] == "https://www.instagram.com/sofiimarvel/"
    assert by_kind["instagram"]["followers"] == 78400
    assert by_kind["telegram"]["url"] == "https://t.me/yakutyanochkaaaaa"
