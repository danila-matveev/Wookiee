"""Tests for ContentStore data classes."""

from services.content_kb.store import ContentAsset


def test_content_asset_creation():
    asset = ContentAsset(
        disk_path="/test/path.png",
        file_name="path.png",
        mime_type="image/png",
        file_size=1000,
        md5="abc123",
        embedding=[0.1] * 3072,
        year=2025,
        content_category="маркетплейсы",
        model_name="Bella",
        color="black",
        sku="257144777",
    )
    assert asset.disk_path == "/test/path.png"
    assert len(asset.embedding) == 3072
    assert asset.status == "indexed"
