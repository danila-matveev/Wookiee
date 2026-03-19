"""
pgvector store for knowledge base chunks.

Uses Supabase PostgreSQL with pgvector extension.
Connection reuses sku_database pattern (psycopg2 + SQLAlchemy-style).
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import psycopg2
import psycopg2.extras
from pgvector.psycopg2 import register_vector

from . import config

logger = logging.getLogger(__name__)


@dataclass
class Chunk:
    content: str
    embedding: list[float]
    module: str
    file_name: str
    file_type: str
    content_type: str
    chunk_index: int
    is_cleaned: bool = False
    source_path: str = ""
    source_tag: str = "course"
    verified: bool = False


@dataclass
class SearchResult:
    id: int
    content: str
    similarity: float
    module: str
    file_name: str
    file_type: str
    content_type: str
    chunk_index: int
    source_path: str
    source_tag: str = ""
    verified: bool = False


class KnowledgeStore:
    """pgvector-backed knowledge base store."""

    def __init__(self):
        self._conn_params = {
            "host": config.POSTGRES_HOST,
            "port": config.POSTGRES_PORT,
            "database": config.POSTGRES_DB,
            "user": config.POSTGRES_USER,
            "password": config.POSTGRES_PASSWORD,
            "sslmode": "require" if "supabase" in config.POSTGRES_HOST.lower()
                                    or "pooler" in config.POSTGRES_HOST.lower()
                                 else "prefer",
        }

    def _get_conn(self):
        conn = psycopg2.connect(**self._conn_params)
        register_vector(conn)
        return conn

    def insert_chunks(self, chunks: list[Chunk]) -> int:
        """Insert chunks into kb_chunks. Returns number of inserted rows."""
        if not chunks:
            return 0

        conn = self._get_conn()
        cur = conn.cursor()
        inserted = 0

        try:
            import numpy as np

            for chunk in chunks:
                cur.execute(
                    """
                    INSERT INTO kb_chunks
                        (content, embedding, module, file_name, file_type,
                         content_type, chunk_index, is_cleaned, source_path,
                         source_tag, verified)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        chunk.content,
                        np.array(chunk.embedding, dtype=np.float32),
                        chunk.module,
                        chunk.file_name,
                        chunk.file_type,
                        chunk.content_type,
                        chunk.chunk_index,
                        chunk.is_cleaned,
                        chunk.source_path,
                        chunk.source_tag,
                        chunk.verified,
                    ),
                )
                inserted += 1

            conn.commit()
            logger.info("Inserted %d chunks", inserted)
            return inserted

        except Exception as e:
            conn.rollback()
            logger.error("Insert failed: %s", e)
            raise
        finally:
            cur.close()
            conn.close()

    def search(
        self,
        query_embedding: list[float],
        limit: int = 5,
        module: Optional[str] = None,
        content_type: Optional[str] = None,
        min_similarity: float = 0.5,
        source_tag: Optional[str] = None,
    ) -> list[SearchResult]:
        """Vector search using search_kb() SQL function."""
        import numpy as np

        conn = self._get_conn()
        cur = conn.cursor()

        try:
            cur.execute(
                "SELECT * FROM search_kb(%s, %s, %s, %s, %s, %s)",
                (
                    np.array(query_embedding, dtype=np.float32),
                    limit,
                    module,
                    content_type,
                    min_similarity,
                    source_tag,
                ),
            )
            rows = cur.fetchall()
            return [
                SearchResult(
                    id=r[0],
                    content=r[1],
                    similarity=r[2],
                    module=r[3],
                    file_name=r[4],
                    file_type=r[5],
                    content_type=r[6],
                    chunk_index=r[7],
                    source_path=r[8],
                    source_tag=r[9] if len(r) > 9 else "",
                    verified=r[10] if len(r) > 10 else False,
                )
                for r in rows
            ]
        finally:
            cur.close()
            conn.close()

    def delete_by_file(self, file_name: str) -> int:
        """Delete all chunks for a given file. Returns deleted count."""
        conn = self._get_conn()
        cur = conn.cursor()

        try:
            cur.execute(
                "DELETE FROM kb_chunks WHERE file_name = %s",
                (file_name,),
            )
            deleted = cur.rowcount
            conn.commit()
            logger.info("Deleted %d chunks for file: %s", deleted, file_name)
            return deleted
        except Exception as e:
            conn.rollback()
            logger.error("Delete failed: %s", e)
            raise
        finally:
            cur.close()
            conn.close()

    def get_stats(self) -> dict:
        """Get collection statistics."""
        conn = self._get_conn()
        cur = conn.cursor()

        try:
            cur.execute("SELECT COUNT(*) FROM kb_chunks;")
            total = cur.fetchone()[0]

            cur.execute(
                "SELECT module, COUNT(*) FROM kb_chunks GROUP BY module ORDER BY module;"
            )
            by_module = {r[0]: r[1] for r in cur.fetchall()}

            cur.execute(
                "SELECT file_type, COUNT(*) FROM kb_chunks GROUP BY file_type;"
            )
            by_type = {r[0]: r[1] for r in cur.fetchall()}

            cur.execute(
                "SELECT COUNT(DISTINCT file_name) FROM kb_chunks;"
            )
            unique_files = cur.fetchone()[0]

            return {
                "total_chunks": total,
                "unique_files": unique_files,
                "by_module": by_module,
                "by_file_type": by_type,
            }
        finally:
            cur.close()
            conn.close()

    def get_ingested_files(self) -> set[str]:
        """Get set of already ingested file names."""
        conn = self._get_conn()
        cur = conn.cursor()

        try:
            cur.execute("SELECT DISTINCT file_name FROM kb_chunks;")
            return {r[0] for r in cur.fetchall()}
        finally:
            cur.close()
            conn.close()

    def delete_by_module(self, module: str) -> int:
        """Delete all chunks for a given module. Returns deleted count."""
        conn = self._get_conn()
        cur = conn.cursor()

        try:
            cur.execute(
                "DELETE FROM kb_chunks WHERE module = %s",
                (module,),
            )
            deleted = cur.rowcount
            conn.commit()
            logger.info("Deleted %d chunks for module: %s", deleted, module)
            return deleted
        except Exception as e:
            conn.rollback()
            logger.error("Delete by module failed: %s", e)
            raise
        finally:
            cur.close()
            conn.close()

    def list_modules(self) -> list[dict]:
        """List all modules with chunk and file counts."""
        conn = self._get_conn()
        cur = conn.cursor()

        try:
            cur.execute("""
                SELECT module,
                       COUNT(*) as chunk_count,
                       COUNT(DISTINCT file_name) as file_count,
                       ARRAY_AGG(DISTINCT source_tag) as source_tags
                FROM kb_chunks
                GROUP BY module
                ORDER BY module;
            """)
            return [
                {
                    "module": r[0],
                    "chunk_count": r[1],
                    "file_count": r[2],
                    "source_tags": r[3] or [],
                }
                for r in cur.fetchall()
            ]
        finally:
            cur.close()
            conn.close()

    def list_files(self, module: str = None) -> list[dict]:
        """List files with metadata. Optionally filter by module."""
        conn = self._get_conn()
        cur = conn.cursor()

        try:
            if module:
                cur.execute("""
                    SELECT file_name, module, COUNT(*) as chunk_count,
                           MAX(source_tag) as source_tag,
                           BOOL_AND(verified) as verified
                    FROM kb_chunks
                    WHERE module = %s
                    GROUP BY file_name, module
                    ORDER BY file_name;
                """, (module,))
            else:
                cur.execute("""
                    SELECT file_name, module, COUNT(*) as chunk_count,
                           MAX(source_tag) as source_tag,
                           BOOL_AND(verified) as verified
                    FROM kb_chunks
                    GROUP BY file_name, module
                    ORDER BY module, file_name;
                """)
            return [
                {
                    "file_name": r[0],
                    "module": r[1],
                    "chunk_count": r[2],
                    "source_tag": r[3],
                    "verified": r[4],
                }
                for r in cur.fetchall()
            ]
        finally:
            cur.close()
            conn.close()

    def mark_verified(self, file_name: str, verified: bool = True) -> int:
        """Mark all chunks of a file as verified/unverified."""
        conn = self._get_conn()
        cur = conn.cursor()

        try:
            cur.execute(
                "UPDATE kb_chunks SET verified = %s, updated_at = now() WHERE file_name = %s",
                (verified, file_name),
            )
            updated = cur.rowcount
            conn.commit()
            logger.info("Marked %d chunks as verified=%s for file: %s", updated, verified, file_name)
            return updated
        except Exception as e:
            conn.rollback()
            logger.error("Mark verified failed: %s", e)
            raise
        finally:
            cur.close()
            conn.close()

    def get_detailed_stats(self) -> dict:
        """Get detailed statistics: by module, source_tag, verified status."""
        conn = self._get_conn()
        cur = conn.cursor()

        try:
            cur.execute("SELECT COUNT(*) FROM kb_chunks;")
            total = cur.fetchone()[0]

            cur.execute(
                "SELECT module, COUNT(*) FROM kb_chunks GROUP BY module ORDER BY module;"
            )
            by_module = {r[0]: r[1] for r in cur.fetchall()}

            cur.execute(
                "SELECT source_tag, COUNT(*) FROM kb_chunks GROUP BY source_tag ORDER BY source_tag;"
            )
            by_source_tag = {r[0]: r[1] for r in cur.fetchall()}

            cur.execute(
                "SELECT verified, COUNT(*) FROM kb_chunks GROUP BY verified;"
            )
            by_verified = {str(r[0]): r[1] for r in cur.fetchall()}

            cur.execute("SELECT COUNT(DISTINCT file_name) FROM kb_chunks;")
            unique_files = cur.fetchone()[0]

            cur.execute(
                "SELECT file_type, COUNT(*) FROM kb_chunks GROUP BY file_type;"
            )
            by_type = {r[0]: r[1] for r in cur.fetchall()}

            return {
                "total_chunks": total,
                "unique_files": unique_files,
                "by_module": by_module,
                "by_source_tag": by_source_tag,
                "by_verified": by_verified,
                "by_file_type": by_type,
            }
        finally:
            cur.close()
            conn.close()
