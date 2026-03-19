#!/usr/bin/env python3
"""
One-shot ingestion of all knowledge base files.

Usage:
    python -m services.knowledge_base.scripts.ingest_all [--force]
"""

import asyncio
import argparse
import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from services.knowledge_base.ingest import ingest_directory
import importlib
_migration = importlib.import_module("services.knowledge_base.migrations.001_create_kb_tables")
create_vector_index = _migration.create_vector_index


def main():
    parser = argparse.ArgumentParser(description="Ingest knowledge base files")
    parser.add_argument(
        "--force", action="store_true",
        help="Re-ingest all files (delete + re-insert)",
    )
    parser.add_argument(
        "--source", type=str, default=None,
        help="Source directory (default: KB_SOURCE_DIR from config)",
    )
    parser.add_argument(
        "--log-level", type=str, default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    print("=" * 60)
    print("Knowledge Base — Full Ingestion")
    print("=" * 60)

    stats = asyncio.run(ingest_directory(
        source_dir=args.source,
        force=args.force,
    ))

    print(f"\nResults:")
    print(f"  Files processed: {stats['files_processed']}")
    print(f"  Files skipped:   {stats['files_skipped']}")
    print(f"  Files errored:   {stats['files_errored']}")
    print(f"  Total chunks:    {stats['chunks_total']}")

    if stats["errors"]:
        print(f"\nErrors:")
        for err in stats["errors"]:
            print(f"  - {err}")

    # Create vector index after ingestion
    if stats["chunks_total"] > 0:
        print("\nCreating vector index...")
        create_vector_index()

    print("\nDone!")


if __name__ == "__main__":
    main()
