#!/usr/bin/env python3
"""
Fast finish: skip full tree scan, target only sections with missing files.

Strategy:
1. Delete failed records (re-index them)
2. Load all indexed MD5s from DB
3. Scan ONLY targeted roots (where gaps exist)
4. Process new files with 4 concurrent workers
5. Skip delete detection (not needed for finish run)
"""

import asyncio
import logging
from io import BytesIO

import psycopg2

from PIL import Image

try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
except ImportError:
    pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

CONCURRENCY = 4
_UNSUPPORTED_MIMES = {"image/heic", "image/heif", "image/tiff"}
_SKIP_EXTENSIONS = {".svg", ".psd", ".ai", ".eps", ".pdf"}


def should_skip(file_info):
    mime = file_info.get("mime_type", "")
    if mime == "image/svg+xml":
        return True
    name = file_info.get("name", "").lower()
    ext = "." + name.rsplit(".", 1)[-1] if "." in name else ""
    return ext in _SKIP_EXTENSIONS


def convert_to_jpeg(image_bytes):
    img = Image.open(BytesIO(image_bytes))
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=90)
    buf.seek(0)
    logger.info("Converted %s → JPEG", img.format or "unknown")
    return buf.read(), "image/jpeg"


def resize_image(image_bytes, max_dim=4096):
    img = Image.open(BytesIO(image_bytes))
    if max(img.size) <= max_dim:
        return image_bytes
    ratio = max_dim / max(img.size)
    new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
    img = img.resize(new_size, Image.LANCZOS)
    buf = BytesIO()
    fmt = "PNG" if img.mode == "RGBA" else "JPEG"
    img.save(buf, format=fmt, quality=85)
    buf.seek(0)
    return buf.read()


async def process_file(file_info, client, embedder, store, counter, sem):
    async with sem:
        try:
            image_bytes = await asyncio.to_thread(client.download_bytes, file_info["path"])
            mime = file_info["mime_type"]

            if len(image_bytes) > 10 * 1024 * 1024:
                image_bytes = resize_image(image_bytes)

            # Normalize: convert HEIC/TIFF/CMYK/palette to JPEG
            try:
                img = Image.open(BytesIO(image_bytes))
                needs_convert = (
                    mime in _UNSUPPORTED_MIMES
                    or img.mode in ("CMYK", "P", "L", "LA", "I", "F")
                    or (img.format and img.format.upper() in ("TIFF", "HEIF"))
                )
                if needs_convert:
                    if img.mode != "RGB":
                        img = img.convert("RGB")
                    buf = BytesIO()
                    img.save(buf, format="JPEG", quality=90)
                    buf.seek(0)
                    image_bytes = buf.read()
                    mime = "image/jpeg"
                    logger.info("Normalized %s/%s → JPEG", img.format, img.mode)
            except Exception as conv_err:
                logger.warning("Normalize failed: %s — %s", file_info["path"], conv_err)

            from services.content_kb.path_parser import parse_path_metadata
            metadata = parse_path_metadata(file_info["path"])

            embedding = await embedder.embed_image(image_bytes, mime_type=mime)

            from services.content_kb.store import ContentAsset
            asset = ContentAsset(
                disk_path=file_info["path"],
                file_name=file_info["name"],
                mime_type=file_info["mime_type"],
                file_size=file_info["size"],
                md5=file_info["md5"],
                embedding=embedding,
                year=metadata.get("year", 2025),
                content_category=metadata.get("content_category"),
                model_name=metadata.get("model_name"),
                color=metadata.get("color"),
                sku=metadata.get("sku"),
            )
            store.insert(asset)
            counter["indexed"] += 1
            logger.info("Indexed [%d]: %s", counter["indexed"], file_info["path"])

        except Exception as e:
            counter["failed"] += 1
            logger.warning("Failed: %s — %s", file_info["path"], e)
            try:
                store.mark_failed(file_info["path"], str(e))
            except Exception:
                pass


async def main():
    from services.content_kb.config import (
        POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB,
        POSTGRES_USER, POSTGRES_PASSWORD,
    )
    from services.content_kb.store import ContentStore
    from services.content_kb.embedder import ImageEmbedder
    from services.content_kb.yadisk_client import YaDiskClient

    # Step 1: delete failed records
    conn = psycopg2.connect(
        host=POSTGRES_HOST, port=POSTGRES_PORT, dbname=POSTGRES_DB,
        user=POSTGRES_USER, password=POSTGRES_PASSWORD,
    )
    cur = conn.cursor()
    cur.execute("DELETE FROM content_assets WHERE status = 'failed'")
    print(f"Deleted {cur.rowcount} failed records", flush=True)
    conn.commit()
    cur.close()
    conn.close()

    # Step 2: load indexed MD5s
    store = ContentStore()
    existing_md5s = set(store.get_indexed_files().keys())
    print(f"Already indexed: {len(existing_md5s)} files", flush=True)

    # Step 3: init clients
    client = YaDiskClient()
    embedder = ImageEmbedder()
    sem = asyncio.Semaphore(CONCURRENCY)
    counter = {"indexed": 0, "failed": 0, "skipped": 0}
    tasks = []

    # Step 4: scan targeted roots — these have the most gaps
    TARGETS = [
        "/Wookiee/Контент/2025",   # ~2,100 remaining
        "/Wookiee/Контент/2026",   # ~46 remaining
        "/Wookiee/Блогеры",        # ~113 remaining
    ]

    for root in TARGETS:
        print(f"\n{'='*60}", flush=True)
        print(f"Scanning: {root}", flush=True)
        print(f"{'='*60}", flush=True)

        for file_info in client.list_images_recursive(root):
            md5 = file_info["md5"]

            if should_skip(file_info):
                counter["skipped"] += 1
                continue

            if md5 in existing_md5s:
                counter["skipped"] += 1
                continue

            # New file — launch async task
            task = asyncio.create_task(
                process_file(file_info, client, embedder, store, counter, sem)
            )
            tasks.append(task)

            # Drain completed tasks periodically
            if len(tasks) >= CONCURRENCY * 4:
                done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                tasks = list(pending)

        # Drain remaining for this root
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
            tasks = []

        print(f"After {root}: indexed={counter['indexed']}, failed={counter['failed']}, skipped={counter['skipped']}", flush=True)

    print(f"\n{'='*60}", flush=True)
    print(f"DONE: indexed={counter['indexed']}, failed={counter['failed']}, skipped={counter['skipped']}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
