#!/usr/bin/env python3
"""
Retry previously failed files.

Reads failed paths from log, downloads, normalizes, embeds with retry.
"""

import asyncio
import logging
import re
import sys
from io import BytesIO

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
MAX_RETRIES = 3
RETRY_DELAY = 10  # seconds


async def process_one(path, client, embedder, store, counter, sem):
    """Download, normalize, embed with retry on 504/timeout."""
    from services.content_kb import config
    from services.content_kb.path_parser import parse_path_metadata
    from services.content_kb.store import ContentAsset

    _UNSUPPORTED_MIMES = {"image/heic", "image/heif", "image/tiff"}

    async with sem:
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                # Download
                file_info = await asyncio.to_thread(_get_file_info, client, path)
                if not file_info:
                    counter["skip"] += 1
                    logger.warning("File not found on disk: %s", path)
                    return

                image_bytes = await asyncio.to_thread(client.download_bytes, path)
                mime = file_info["mime_type"]

                # Normalize: resize + convert
                img = Image.open(BytesIO(image_bytes))

                needs_reencode = False
                if img.mode in ("CMYK", "P", "L", "LA", "I", "F"):
                    img = img.convert("RGB")
                    needs_reencode = True

                if mime in _UNSUPPORTED_MIMES:
                    if img.mode != "RGB":
                        img = img.convert("RGB")
                    needs_reencode = True
                    mime = "image/jpeg"

                if max(img.size) > config.MAX_IMAGE_DIMENSION:
                    ratio = config.MAX_IMAGE_DIMENSION / max(img.size)
                    new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
                    logger.info("Resize %dx%d → %dx%d", *img.size, *new_size)
                    img = img.resize(new_size, Image.LANCZOS)
                    needs_reencode = True

                if len(image_bytes) > config.MAX_IMAGE_SIZE_BYTES:
                    needs_reencode = True

                if needs_reencode:
                    buf = BytesIO()
                    fmt = "PNG" if img.mode == "RGBA" else "JPEG"
                    img.save(buf, format=fmt, quality=85)
                    buf.seek(0)
                    image_bytes = buf.read()
                    if fmt == "JPEG":
                        mime = "image/jpeg"

                # Embed
                embedding = await embedder.embed_image(image_bytes, mime_type=mime)

                # Store
                metadata = parse_path_metadata(path)
                asset = ContentAsset(
                    disk_path=path,
                    file_name=file_info["name"],
                    mime_type=file_info["mime_type"],
                    file_size=file_info["size"],
                    md5=file_info["md5"],
                    embedding=embedding,
                    year=metadata.get("year"),
                    content_category=metadata.get("content_category"),
                    model_name=metadata.get("model_name"),
                    color=metadata.get("color"),
                    sku=metadata.get("sku"),
                )
                store.insert(asset)
                counter["ok"] += 1
                logger.info("OK [%d]: %s", counter["ok"], path)
                return

            except Exception as e:
                err = str(e)
                if attempt < MAX_RETRIES and ("504" in err or "Deadline" in err or "timeout" in err.lower() or "503" in err):
                    logger.warning("Retry %d/%d for %s: %s", attempt, MAX_RETRIES, path.split("/")[-1], err[:60])
                    await asyncio.sleep(RETRY_DELAY * attempt)
                    continue
                else:
                    counter["fail"] += 1
                    logger.warning("FAIL: %s — %s", path, err[:100])
                    return


def _get_file_info(client, path):
    """Get file metadata from Yandex Disk."""
    try:
        meta = client._client.get_meta(path)
        if meta.type != "file":
            return None
        return {
            "path": meta.path,
            "name": meta.name,
            "mime_type": meta.mime_type,
            "md5": meta.md5,
            "size": meta.size,
        }
    except Exception:
        return None


async def main():
    from services.content_kb.store import ContentStore
    from services.content_kb.embedder import ImageEmbedder
    from services.content_kb.yadisk_client import YaDiskClient

    # Read failed paths from log
    log_path = sys.argv[1] if len(sys.argv) > 1 else "/tmp/content_kb_fast.log"
    failed_paths = []
    with open(log_path) as f:
        for line in f:
            if "Failed:" in line:
                # Path has spaces, extract between "Failed: " and " — "
                m = re.search(r"Failed: (disk:.+?) — ", line)
                if m:
                    failed_paths.append(m.group(1))

    # Deduplicate
    failed_paths = list(dict.fromkeys(failed_paths))
    print(f"Retrying {len(failed_paths)} failed files\n", flush=True)

    if not failed_paths:
        print("Nothing to retry!")
        return

    # Init
    client = YaDiskClient()
    embedder = ImageEmbedder()
    store = ContentStore()
    sem = asyncio.Semaphore(CONCURRENCY)
    counter = {"ok": 0, "fail": 0, "skip": 0}

    # Check which are already indexed (from previous retry)
    existing_md5s = set(store.get_indexed_files().keys())

    tasks = []
    for path in failed_paths:
        task = asyncio.create_task(process_one(path, client, embedder, store, counter, sem))
        tasks.append(task)

        if len(tasks) >= CONCURRENCY * 4:
            done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            tasks = list(pending)

    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)

    print(f"\nDONE: ok={counter['ok']}, fail={counter['fail']}, skip={counter['skip']}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
