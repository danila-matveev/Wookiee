"""
pgvector store for content assets.

Uses Supabase PostgreSQL with pgvector extension.
Connection reuses knowledge_base pattern (psycopg2 + register_vector).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import psycopg2
import psycopg2.extras
from pgvector.psycopg2 import register_vector

from . import config

logger = logging.getLogger(__name__)


@dataclass
class ContentAsset:
    disk_path: str
    file_name: str
    mime_type: str
    file_size: int
    md5: str
    embedding: list[float]
    year: int = 2025
    content_category: str | None = None
    model_name: str | None = None
    color: str | None = None
    sku: str | None = None
    status: str = "indexed"


@dataclass
class SearchResult:
    id: int
    disk_path: str
    file_name: str
    similarity: float
    model_name: str | None
    color: str | None
    content_category: str | None
    sku: str | None
    mime_type: str
    file_size: int


class ContentStore:
    """pgvector-backed content assets store."""

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

    def insert(self, asset: ContentAsset) -> int:
        """Insert a content asset. Returns the new row id."""
        conn = self._get_conn()
        cur = conn.cursor()

        try:
            cur.execute(
                """
                INSERT INTO content_assets
                    (embedding, disk_path, file_name, mime_type, file_size,
                     md5, year, content_category, model_name, color, sku, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    np.array(asset.embedding, dtype=np.float32),
                    asset.disk_path,
                    asset.file_name,
                    asset.mime_type,
                    asset.file_size,
                    asset.md5,
                    asset.year,
                    asset.content_category,
                    asset.model_name,
                    asset.color,
                    asset.sku,
                    asset.status,
                ),
            )
            row_id = cur.fetchone()[0]
            conn.commit()
            logger.info("Inserted asset id=%d: %s", row_id, asset.disk_path)
            return row_id

        except Exception as e:
            conn.rollback()
            logger.error("Insert failed: %s", e)
            raise
        finally:
            cur.close()
            conn.close()

    def update_path(self, md5: str, new_path: str, metadata: dict) -> None:
        """Update disk_path and metadata for a moved file."""
        conn = self._get_conn()
        cur = conn.cursor()

        try:
            cur.execute(
                """
                UPDATE content_assets
                SET disk_path = %s,
                    content_category = COALESCE(%s, content_category),
                    model_name = COALESCE(%s, model_name),
                    color = COALESCE(%s, color),
                    sku = COALESCE(%s, sku),
                    updated_at = NOW()
                WHERE md5 = %s AND status = 'indexed'
                """,
                (
                    new_path,
                    metadata.get("content_category"),
                    metadata.get("model_name"),
                    metadata.get("color"),
                    metadata.get("sku"),
                    md5,
                ),
            )
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error("Update path failed: %s", e)
            raise
        finally:
            cur.close()
            conn.close()

    def mark_failed(self, disk_path: str, error: str) -> None:
        """Mark an asset as failed."""
        conn = self._get_conn()
        cur = conn.cursor()

        try:
            # Try to update existing record, or insert a minimal failed record
            cur.execute(
                """
                UPDATE content_assets
                SET status = 'failed', updated_at = NOW()
                WHERE disk_path = %s
                """,
                (disk_path,),
            )
            conn.commit()
            logger.info("Marked failed: %s — %s", disk_path, error)
        except Exception as e:
            conn.rollback()
            logger.error("Mark failed error: %s", e)
        finally:
            cur.close()
            conn.close()

    def mark_deleted(self, paths: list[str]) -> None:
        """Mark multiple assets as deleted."""
        if not paths:
            return

        conn = self._get_conn()
        cur = conn.cursor()

        try:
            cur.execute(
                """
                UPDATE content_assets
                SET status = 'deleted', updated_at = NOW()
                WHERE disk_path = ANY(%s) AND status = 'indexed'
                """,
                (paths,),
            )
            updated = cur.rowcount
            conn.commit()
            logger.info("Marked %d assets as deleted", updated)
        except Exception as e:
            conn.rollback()
            logger.error("Mark deleted failed: %s", e)
            raise
        finally:
            cur.close()
            conn.close()

    def get_indexed_files(self) -> dict[str, str]:
        """Get {md5: disk_path} for all indexed files."""
        conn = self._get_conn()
        cur = conn.cursor()

        try:
            cur.execute(
                "SELECT md5, disk_path FROM content_assets WHERE status = 'indexed'"
            )
            return {r[0]: r[1] for r in cur.fetchall()}
        finally:
            cur.close()
            conn.close()

    def search(
        self,
        query_embedding: list[float],
        limit: int = 10,
        model_name: str | None = None,
        color: str | None = None,
        category: str | None = None,
        sku: str | None = None,
        min_similarity: float = 0.3,
    ) -> list[SearchResult]:
        """Vector search using search_content() SQL function."""
        conn = self._get_conn()
        cur = conn.cursor()

        try:
            cur.execute(
                "SELECT * FROM search_content(%s, %s, %s, %s, %s, %s, %s)",
                (
                    np.array(query_embedding, dtype=np.float32),
                    limit,
                    model_name,
                    color,
                    category,
                    sku,
                    min_similarity,
                ),
            )
            rows = cur.fetchall()
            return [
                SearchResult(
                    id=r[0],
                    disk_path=r[1],
                    file_name=r[2],
                    similarity=r[3],
                    model_name=r[4],
                    color=r[5],
                    content_category=r[6],
                    sku=r[7],
                    mime_type=r[8],
                    file_size=r[9],
                )
                for r in rows
            ]
        finally:
            cur.close()
            conn.close()

    def get_stats(self) -> dict:
        """Get collection statistics."""
        conn = self._get_conn()
        cur = conn.cursor()

        try:
            cur.execute(
                "SELECT COUNT(*) FROM content_assets WHERE status = 'indexed';"
            )
            total = cur.fetchone()[0]

            cur.execute(
                """SELECT content_category, COUNT(*)
                   FROM content_assets WHERE status = 'indexed'
                   GROUP BY content_category ORDER BY content_category;"""
            )
            by_category = {r[0]: r[1] for r in cur.fetchall()}

            cur.execute(
                """SELECT LOWER(model_name), COUNT(*)
                   FROM content_assets WHERE status = 'indexed' AND model_name IS NOT NULL
                   GROUP BY LOWER(model_name) ORDER BY LOWER(model_name);"""
            )
            by_model = {r[0]: r[1] for r in cur.fetchall()}

            cur.execute(
                "SELECT MAX(indexed_at) FROM content_assets WHERE status = 'indexed';"
            )
            last_indexed = cur.fetchone()[0]

            return {
                "total_assets": total,
                "by_category": by_category,
                "by_model": by_model,
                "last_indexed": str(last_indexed) if last_indexed else None,
            }
        finally:
            cur.close()
            conn.close()

    def list_content(
        self,
        model_name: str | None = None,
        color: str | None = None,
        category: str | None = None,
        sku: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict]:
        """List content assets by metadata filters (no vector search)."""
        conn = self._get_conn()
        cur = conn.cursor()

        try:
            conditions = ["status = 'indexed'"]
            params = []

            if model_name:
                conditions.append("LOWER(model_name) = LOWER(%s)")
                params.append(model_name)
            if color:
                conditions.append("LOWER(color) = LOWER(%s)")
                params.append(color)
            if category:
                conditions.append("LOWER(content_category) = LOWER(%s)")
                params.append(category)
            if sku:
                conditions.append("sku = %s")
                params.append(sku)

            where = " AND ".join(conditions)
            params.extend([limit, offset])

            cur.execute(
                f"""
                SELECT id, disk_path, file_name, mime_type, file_size,
                       model_name, color, content_category, sku, year, indexed_at
                FROM content_assets
                WHERE {where}
                ORDER BY indexed_at DESC
                LIMIT %s OFFSET %s
                """,
                params,
            )
            columns = [
                "id", "disk_path", "file_name", "mime_type", "file_size",
                "model_name", "color", "content_category", "sku", "year", "indexed_at",
            ]
            return [dict(zip(columns, row)) for row in cur.fetchall()]
        finally:
            cur.close()
            conn.close()
