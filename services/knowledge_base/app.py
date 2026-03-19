"""
Knowledge Base FastAPI service.

Endpoints:
- POST /search — semantic search over knowledge base
- GET /health — healthcheck
- GET /stats — collection statistics
"""

import logging
import time
from typing import Optional

from fastapi import FastAPI
from pydantic import BaseModel, Field

from .search import search_knowledge
from .store import KnowledgeStore

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Wookiee Knowledge Base",
    description="Vector search over WB marketplace knowledge (Let's Rock course)",
    version="1.0.0",
)


class SearchRequest(BaseModel):
    query: str = Field(..., description="Search query in natural language")
    limit: int = Field(5, ge=1, le=20, description="Max results")
    module: Optional[str] = Field(None, description="Filter by module: 1-8 or processes")
    content_type: Optional[str] = Field(None, description="Filter: theory, template, example")
    min_score: float = Field(0.5, ge=0.0, le=1.0, description="Min similarity score")


class SearchResultItem(BaseModel):
    text: str
    score: float
    module: Optional[str]
    file_name: str
    file_type: str
    content_type: Optional[str]
    chunk_index: int
    source_path: Optional[str]


class SearchResponse(BaseModel):
    results: list[SearchResultItem]
    query_time_ms: int
    count: int


@app.post("/search", response_model=SearchResponse)
async def search(req: SearchRequest):
    """Semantic search over the knowledge base."""
    start = time.time()

    results = await search_knowledge(
        query=req.query,
        limit=req.limit,
        module=req.module,
        content_type=req.content_type,
        min_score=req.min_score,
    )

    elapsed_ms = int((time.time() - start) * 1000)

    return SearchResponse(
        results=[SearchResultItem(**r) for r in results],
        query_time_ms=elapsed_ms,
        count=len(results),
    )


@app.get("/health")
async def health():
    return {"status": "ok", "service": "knowledge-base"}


@app.get("/stats")
async def stats():
    store = KnowledgeStore()
    return store.get_stats()


# ── Management endpoints ──────────────────────────────────────


class IngestTextRequest(BaseModel):
    text: str = Field(..., description="Text content to ingest")
    file_name: str = Field(..., description="Logical file name for this content")
    module: str = Field("manual", description="Module: 1-8, processes, manual")
    content_type: str = Field("theory", description="Content type: theory, template, example")
    source_tag: str = Field("manual", description="Source: course, playbook, manual, insight")


@app.post("/ingest_text")
async def ingest_text_endpoint(req: IngestTextRequest):
    """Ingest arbitrary text into KB (chunk → embed → store)."""
    from .ingest import ingest_text

    chunks_inserted = await ingest_text(
        text=req.text,
        file_name=req.file_name,
        module=req.module,
        content_type=req.content_type,
        source_tag=req.source_tag,
    )
    return {"status": "ok", "chunks_inserted": chunks_inserted, "file_name": req.file_name}


@app.get("/modules")
async def list_modules():
    """List all KB modules with chunk/file counts."""
    store = KnowledgeStore()
    return store.list_modules()


@app.get("/files")
async def list_files(module: Optional[str] = None):
    """List files in KB, optionally filtered by module."""
    store = KnowledgeStore()
    return store.list_files(module=module)


@app.delete("/file/{file_name}")
async def delete_file(file_name: str):
    """Delete all chunks for a file."""
    store = KnowledgeStore()
    deleted = store.delete_by_file(file_name)
    return {"status": "ok", "deleted": deleted, "file_name": file_name}


@app.delete("/module/{module}")
async def delete_module(module: str):
    """Delete all chunks for a module."""
    store = KnowledgeStore()
    deleted = store.delete_by_module(module)
    return {"status": "ok", "deleted": deleted, "module": module}


@app.patch("/verify/{file_name}")
async def verify_file(file_name: str, verified: bool = True):
    """Mark all chunks of a file as verified/unverified."""
    store = KnowledgeStore()
    updated = store.mark_verified(file_name, verified=verified)
    return {"status": "ok", "updated": updated, "file_name": file_name, "verified": verified}


@app.get("/detailed_stats")
async def detailed_stats():
    """Get detailed KB statistics by module, source_tag, verified status."""
    store = KnowledgeStore()
    return store.get_detailed_stats()
