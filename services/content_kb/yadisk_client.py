"""
Yandex Disk OAuth client wrapper.

Provides recursive file listing, image download, and preview URL generation.
Uses yadisk library for API access.
"""

from __future__ import annotations

import logging
from typing import Iterator

import yadisk

from . import config

logger = logging.getLogger(__name__)

# Folders to skip (not indexed in phase 1)
_SKIP_PATTERNS = {'видео', 'исходники', 'разработка продукта'}


class YaDiskClient:
    """Wrapper around yadisk.Client for content indexing."""

    def __init__(self, token: str | None = None):
        self._client = yadisk.Client(token=token or config.YANDEX_DISK_TOKEN)
        if not self._client.check_token():
            raise ValueError("Invalid Yandex Disk OAuth token")
        logger.info("YaDiskClient initialized, token valid")

    def _should_skip(self, path: str) -> bool:
        """Check if path belongs to a skipped category."""
        path_lower = path.lower()
        return any(pattern in path_lower for pattern in _SKIP_PATTERNS)

    def _list_dir_images(self, path: str) -> list[dict]:
        """List image files in a single directory (non-recursive)."""
        results = []
        for item in self._client.listdir(path):
            if item.type == "file" and item.mime_type and item.mime_type.startswith("image/"):
                results.append({
                    "path": item.path,
                    "name": item.name,
                    "mime_type": item.mime_type,
                    "md5": item.md5,
                    "size": item.size,
                })
        return results

    def list_images_recursive(self, root: str | None = None) -> Iterator[dict]:
        """Recursively list all image files under root."""
        root = root or config.YANDEX_DISK_ROOT
        dirs_to_visit = [root]

        while dirs_to_visit:
            current = dirs_to_visit.pop(0)
            if self._should_skip(current):
                logger.debug("Skipping: %s", current)
                continue

            logger.info("Scanning: %s", current)
            try:
                for item in self._client.listdir(current):
                    if item.type == "dir":
                        dirs_to_visit.append(item.path)
                    elif item.type == "file" and item.mime_type and item.mime_type.startswith("image/"):
                        yield {
                            "path": item.path,
                            "name": item.name,
                            "mime_type": item.mime_type,
                            "md5": item.md5,
                            "size": item.size,
                        }
            except Exception as e:
                logger.warning("Error listing %s: %s", current, e)

    def download_bytes(self, path: str) -> bytes:
        """Download file content as bytes."""
        import io
        buf = io.BytesIO()
        self._client.download(path, buf)
        buf.seek(0)
        return buf.read()

    def get_preview_url(self, path: str, size: str = "L") -> str | None:
        """Get preview URL for a file. Returns None if not available."""
        try:
            meta = self._client.get_meta(path, fields=["preview"])
            return getattr(meta, 'preview', None)
        except Exception:
            return None
