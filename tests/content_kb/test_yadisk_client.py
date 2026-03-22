"""Tests for YaDisk client wrapper — unit tests with mocked yadisk."""

from unittest.mock import MagicMock, patch
from services.content_kb.yadisk_client import YaDiskClient


def test_list_images_filters_non_images():
    """Only image/* mime types should be returned."""
    client = YaDiskClient.__new__(YaDiskClient)
    client._client = MagicMock()

    mock_items = [
        MagicMock(type="file", path="/a.png", mime_type="image/png", md5="abc", size=100, name="a.png"),
        MagicMock(type="file", path="/b.docx", mime_type="application/docx", md5="def", size=200, name="b.docx"),
        MagicMock(type="dir", path="/subdir", mime_type=None, md5=None, size=None, name="subdir"),
    ]
    client._client.listdir = MagicMock(return_value=iter(mock_items))

    results = list(client._list_dir_images("/test"))
    assert len(results) == 1
    assert results[0]["path"] == "/a.png"


def test_should_skip_category():
    """Videos and sources should be skipped."""
    client = YaDiskClient.__new__(YaDiskClient)
    assert client._should_skip("/Контент/2025/2. ВИДЕО/something") is True
    assert client._should_skip("/Контент/2025/3. ИСХОДНИКИ/file.psd") is True
    assert client._should_skip("/Контент/2025/5. МАРКЕТПЛЕЙСЫ/Bella/photo.png") is False
