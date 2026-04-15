"""
Ingestion pipeline — parse → chunk → embed → store.

Walks the knowledge directory, processes all DOCX/PDF/XLSX files,
and stores embeddings in Supabase pgvector.
"""

import asyncio
import logging
import re
from pathlib import Path
from typing import Optional

from . import config
from .chunker import chunk_sections
from .embedder import GeminiEmbedder
from .store import KnowledgeStore, Chunk
from .parsers.docx_parser import parse_docx
from .parsers.pdf_parser import parse_pdf
from .parsers.xlsx_parser import parse_xlsx

logger = logging.getLogger(__name__)

# Module folder name → module ID
MODULE_PATTERN = re.compile(r"^(\d+)\s*модуль", re.IGNORECASE)


def _detect_module(folder_name: str) -> str:
    """Detect module ID from folder name."""
    m = MODULE_PATTERN.match(folder_name)
    if m:
        return m.group(1)
    if "управлен" in folder_name.lower():
        return "processes"
    return "other"


def _detect_content_type(file_path: Path) -> str:
    """Detect content type from file path."""
    path_lower = str(file_path).lower()
    if "таблиц" in path_lower or file_path.suffix == ".xlsx":
        if "пример" in path_lower:
            return "example"
        return "template"
    return "theory"


def _is_notebooklm_version(file_path: Path) -> bool:
    """Check if file is in a 'для notebooklm' subfolder."""
    return "notebooklm" in str(file_path).lower()


def _find_docx_duplicate(pdf_path: Path) -> Optional[Path]:
    """Check if a DOCX version exists for a PDF file."""
    # Look in same directory and parent directory
    stem = pdf_path.stem
    for search_dir in [pdf_path.parent, pdf_path.parent.parent]:
        for docx_path in search_dir.rglob("*.docx"):
            # Fuzzy match: same stem or very similar
            if docx_path.stem.lower() == stem.lower():
                return docx_path
    return None


def collect_files(source_dir: Path) -> list[dict]:
    """
    Walk source directory and collect files to process.

    Applies priority rules:
    - Prefer 'для notebooklm' versions
    - Skip PDFs when DOCX duplicate exists
    - Skip image-heavy PDFs
    """
    files = []
    seen_topics: dict[str, dict] = {}  # (module, stem) → file info

    for path in sorted(source_dir.rglob("*")):
        if not path.is_file():
            continue

        suffix = path.suffix.lower()
        if suffix not in (".docx", ".pdf", ".xlsx"):
            continue

        # Detect module from top-level folder
        rel = path.relative_to(source_dir)
        module_folder = rel.parts[0] if rel.parts else ""
        module = _detect_module(module_folder)

        is_cleaned = _is_notebooklm_version(path)
        content_type = _detect_content_type(path)

        file_info = {
            "path": path,
            "module": module,
            "file_name": path.name,
            "file_type": suffix.lstrip("."),
            "content_type": content_type,
            "is_cleaned": is_cleaned,
            "source_path": str(rel),
        }

        # Dedup key: module + normalized stem
        key = (module, path.stem.lower().replace(" ", "_"))

        if key in seen_topics:
            existing = seen_topics[key]
            # Prefer cleaned versions
            if is_cleaned and not existing["is_cleaned"]:
                seen_topics[key] = file_info
                continue
            # Prefer DOCX over PDF
            if suffix == ".docx" and existing["file_type"] == "pdf":
                seen_topics[key] = file_info
                continue
            # Skip duplicate
            if suffix == ".pdf" and existing["file_type"] == "docx":
                continue
        else:
            seen_topics[key] = file_info

    # Collect all unique files
    # Add xlsx files unconditionally (they don't duplicate docx/pdf)
    for path in sorted(source_dir.rglob("*.xlsx")):
        rel = path.relative_to(source_dir)
        module_folder = rel.parts[0] if rel.parts else ""
        module = _detect_module(module_folder)

        key = (module, path.stem.lower().replace(" ", "_"))
        if key not in seen_topics:
            seen_topics[key] = {
                "path": path,
                "module": module,
                "file_name": path.name,
                "file_type": "xlsx",
                "content_type": _detect_content_type(path),
                "is_cleaned": _is_notebooklm_version(path),
                "source_path": str(rel),
            }

    return list(seen_topics.values())


def parse_file(file_info: dict) -> list:
    """Parse a single file using the appropriate parser."""
    path = file_info["path"]
    file_type = file_info["file_type"]

    if file_type == "docx":
        return parse_docx(path)
    elif file_type == "pdf":
        return parse_pdf(path)
    elif file_type == "xlsx":
        return parse_xlsx(path)
    else:
        logger.warning("Unknown file type: %s", file_type)
        return []


async def ingest_file(
    file_info: dict,
    embedder: GeminiEmbedder,
    store: KnowledgeStore,
    force: bool = False,
) -> int:
    """Ingest a single file: parse → chunk → embed → store."""
    file_name = file_info["file_name"]

    # Check if already ingested
    if not force:
        existing = store.get_ingested_files()
        if file_name in existing:
            logger.info("Skipping already ingested: %s", file_name)
            return 0

    # Parse
    sections = parse_file(file_info)
    if not sections:
        logger.warning("No content extracted from: %s", file_name)
        return 0

    # Chunk
    chunks = chunk_sections(
        sections=sections,
        module=file_info["module"],
        file_name=file_name,
        file_type=file_info["file_type"],
        content_type=file_info["content_type"],
        is_cleaned=file_info.get("is_cleaned", False),
        source_path=file_info.get("source_path", ""),
    )

    if not chunks:
        logger.warning("No chunks generated from: %s", file_name)
        return 0

    # Embed
    texts = [c.text for c in chunks]
    embeddings = await embedder.embed_batch(texts, task_type="RETRIEVAL_DOCUMENT")

    # Store
    if force:
        store.delete_by_file(file_name)

    store_chunks = [
        Chunk(
            content=chunk.text,
            embedding=emb,
            module=chunk.metadata["module"],
            file_name=chunk.metadata["file_name"],
            file_type=chunk.metadata["file_type"],
            content_type=chunk.metadata["content_type"],
            chunk_index=chunk.chunk_index,
            is_cleaned=chunk.metadata["is_cleaned"],
            source_path=chunk.metadata["source_path"],
        )
        for chunk, emb in zip(chunks, embeddings)
    ]

    inserted = store.insert_chunks(store_chunks)
    logger.info("Ingested %s: %d chunks", file_name, inserted)
    return inserted


async def ingest_text(
    text: str,
    file_name: str,
    module: str = "manual",
    content_type: str = "theory",
    source_tag: str = "manual",
) -> int:
    """
    Ingest arbitrary text into the knowledge base at runtime.

    No file parsing needed — text is chunked, embedded, and stored directly.
    Returns number of chunks inserted.
    """
    from .chunker import chunk_text

    if not text or not text.strip():
        logger.warning("Empty text provided for ingest_text, skipping")
        return 0

    # Chunk the text
    raw_chunks = chunk_text(text)
    if not raw_chunks:
        logger.warning("No chunks generated from text for: %s", file_name)
        return 0

    # Add context header to each chunk
    header = f"[Модуль {module}] [{file_name}]"

    embedder = GeminiEmbedder()
    store = KnowledgeStore()

    # Embed
    texts_with_headers = [f"{header}\n{chunk}" for chunk in raw_chunks]
    embeddings = await embedder.embed_batch(texts_with_headers, task_type="RETRIEVAL_DOCUMENT")

    # Store
    store_chunks = [
        Chunk(
            content=texts_with_headers[i],
            embedding=embeddings[i],
            module=module,
            file_name=file_name,
            file_type="text",
            content_type=content_type,
            chunk_index=i,
            is_cleaned=False,
            source_path="",
            source_tag=source_tag,
            verified=False,
        )
        for i in range(len(raw_chunks))
    ]

    inserted = store.insert_chunks(store_chunks)
    logger.info("Ingested text '%s': %d chunks (module=%s, source=%s)",
                file_name, inserted, module, source_tag)
    return inserted


async def ingest_directory(
    source_dir: Optional[str] = None,
    force: bool = False,
) -> dict:
    """
    Ingest all files from the knowledge directory.

    Returns stats dict with counts and errors.
    """
    source = Path(source_dir or config.KB_SOURCE_DIR)
    if not source.exists():
        raise FileNotFoundError(f"Source directory not found: {source}")

    logger.info("Collecting files from: %s", source)
    files = collect_files(source)
    logger.info("Found %d files to process", len(files))

    embedder = GeminiEmbedder()
    store = KnowledgeStore()

    stats = {
        "files_total": len(files),
        "files_processed": 0,
        "files_skipped": 0,
        "files_errored": 0,
        "chunks_total": 0,
        "errors": [],
    }

    for i, file_info in enumerate(files, 1):
        file_name = file_info["file_name"]
        try:
            logger.info("[%d/%d] Processing: %s", i, len(files), file_name)
            chunks_inserted = await ingest_file(
                file_info, embedder, store, force=force,
            )
            if chunks_inserted > 0:
                stats["files_processed"] += 1
                stats["chunks_total"] += chunks_inserted
            else:
                stats["files_skipped"] += 1
        except Exception as e:
            logger.error("Error processing %s: %s", file_name, e)
            stats["files_errored"] += 1
            stats["errors"].append(f"{file_name}: {e}")
            # Cooldown after rate limit errors before trying next file
            if "retries" in str(e).lower() or "429" in str(e):
                cooldown = 120  # 2 minutes
                logger.info("Rate limit cooldown: waiting %ds before next file...", cooldown)
                await asyncio.sleep(cooldown)

    # Log summary
    logger.info("=" * 60)
    logger.info("INGESTION COMPLETE")
    logger.info("Files: %d processed, %d skipped, %d errors (of %d total)",
                stats["files_processed"], stats["files_skipped"],
                stats["files_errored"], stats["files_total"])
    logger.info("Total chunks: %d", stats["chunks_total"])
    if stats["errors"]:
        logger.warning("Errors:\n  %s", "\n  ".join(stats["errors"]))
    logger.info("=" * 60)

    # Print store stats
    db_stats = store.get_stats()
    logger.info("DB stats: %s", db_stats)

    return stats
