"""
Content indexing pipeline.

Crawls Yandex Disk, downloads images, creates embeddings, stores in pgvector.
Incremental: skips already-indexed files, handles moves and deletes.
"""

from __future__ import annotations

import asyncio
import logging
import time
from io import BytesIO

from PIL import Image

from . import config
from .embedder import ImageEmbedder
from .path_parser import parse_path_metadata
from .store import ContentAsset, ContentStore
from .yadisk_client import YaDiskClient

logger = logging.getLogger(__name__)


def resize_image(image_bytes: bytes, max_dimension: int = 4096) -> bytes:
    """Resize image if largest side exceeds max_dimension."""
    img = Image.open(BytesIO(image_bytes))
    if max(img.size) <= max_dimension:
        return image_bytes

    old_size = img.size
    ratio = max_dimension / max(img.size)
    new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
    img = img.resize(new_size, Image.LANCZOS)

    buf = BytesIO()
    fmt = "PNG" if img.mode == "RGBA" else "JPEG"
    img.save(buf, format=fmt, quality=85)
    buf.seek(0)
    logger.info("Resized %dx%d → %dx%d", *old_size, *new_size)
    return buf.read()


async def index_all(root: str | None = None, dry_run: bool = False):
    """Main indexing pipeline."""
    client = YaDiskClient()
    embedder = ImageEmbedder()
    store = ContentStore()

    # Load existing indexed files: {md5: disk_path}
    existing = store.get_indexed_files()
    logger.info("Already indexed: %d files", len(existing))

    # Scan disk
    disk_files = {}  # {md5: file_info}
    indexed_count = 0
    skipped_count = 0
    failed_count = 0
    moved_count = 0

    for file_info in client.list_images_recursive(root):
        md5 = file_info["md5"]
        disk_files[md5] = file_info

        # Already indexed, same path → skip
        if md5 in existing and existing[md5] == file_info["path"]:
            skipped_count += 1
            continue

        # Already indexed, different path → moved
        if md5 in existing and existing[md5] != file_info["path"]:
            metadata = parse_path_metadata(file_info["path"])
            if not dry_run:
                store.update_path(md5, file_info["path"], metadata)
            moved_count += 1
            logger.info("Moved: %s → %s", existing[md5], file_info["path"])
            continue

        # New file → index
        if dry_run:
            logger.info("[DRY RUN] Would index: %s", file_info["path"])
            indexed_count += 1
            continue

        try:
            image_bytes = client.download_bytes(file_info["path"])

            if len(image_bytes) > config.MAX_IMAGE_SIZE_BYTES:
                image_bytes = resize_image(image_bytes, config.MAX_IMAGE_DIMENSION)

            metadata = parse_path_metadata(file_info["path"])
            embedding = await embedder.embed_image(
                image_bytes, mime_type=file_info["mime_type"]
            )

            asset = ContentAsset(
                disk_path=file_info["path"],
                file_name=file_info["name"],
                mime_type=file_info["mime_type"],
                file_size=file_info["size"],
                md5=md5,
                embedding=embedding,
                year=metadata.get("year", 2025),
                content_category=metadata.get("content_category"),
                model_name=metadata.get("model_name"),
                color=metadata.get("color"),
                sku=metadata.get("sku"),
            )
            store.insert(asset)
            indexed_count += 1
            logger.info("Indexed [%d]: %s", indexed_count, file_info["path"])

        except Exception as e:
            failed_count += 1
            logger.warning("Failed: %s — %s", file_info["path"], e)
            try:
                store.mark_failed(file_info["path"], str(e))
            except Exception:
                logger.warning("Could not mark_failed in DB (connection issue)")

        await asyncio.sleep(config.INDEX_DELAY)

    # Mark deleted files
    deleted_paths = [
        path for md5, path in existing.items()
        if md5 not in disk_files
    ]
    if deleted_paths and not dry_run:
        store.mark_deleted(deleted_paths)

    logger.info(
        "Indexing complete: indexed=%d, skipped=%d, moved=%d, failed=%d, deleted=%d",
        indexed_count, skipped_count, moved_count, failed_count, len(deleted_paths),
    )
    return {
        "indexed": indexed_count,
        "skipped": skipped_count,
        "moved": moved_count,
        "failed": failed_count,
        "deleted": len(deleted_paths),
    }
