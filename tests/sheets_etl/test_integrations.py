import json
from pathlib import Path

from services.sheets_etl.transformers.integrations import transform


def test_transform_skips_garbage_and_maps_enums():
    data = json.loads((Path(__file__).parent / "fixtures/integrations_first_3.json").read_text())
    integrations, sub_links = transform(data["values"])
    # The first-3 fixture is sparse, but should at least run cleanly without crashing.
    assert isinstance(integrations, list)
    assert isinstance(sub_links, list)
    for r in integrations:
        assert r["channel"] in {"instagram", "youtube", "tiktok", "telegram", "vk", "rutube", "other"}
        assert r["ad_format"] in {
            "short_video", "long_video", "image_post", "text_post",
            "live_stream", "story", "integration", "long_post",
        }
        assert r["marketplace"] in {"wb", "ozon", "both"}
        assert r["sheet_row_id"]
        assert len(r["sheet_row_id"]) == 32
