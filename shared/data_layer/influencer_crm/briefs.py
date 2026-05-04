from __future__ import annotations

import json

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from services.influencer_crm.schemas.brief import (
    BriefDetailOut,
    BriefOut,
    BriefVersionOut,
    BriefsPage,
)

# DB stores short English tokens; UI expects user-friendly API values.
_DB_TO_API: dict[str, str] = {
    "draft": "draft",
    "review": "on_review",
    "signed": "signed",
    "finished": "completed",
    "cancelled": "completed",
}
_API_TO_DB: dict[str, str] = {
    "draft": "draft",
    "on_review": "review",
    "signed": "signed",
    "completed": "finished",
}

_LIST_SELECT = """
    SELECT
        b.id,
        b.title,
        b.status,
        b.current_version,
        bv.id  AS current_version_id,
        b.created_at,
        b.updated_at
    FROM crm.briefs b
    LEFT JOIN crm.brief_versions bv
        ON bv.brief_id = b.id AND bv.version = b.current_version
"""


def _to_brief_out(row: dict) -> BriefOut:
    d = dict(row)
    d["status"] = _DB_TO_API.get(d.get("status", "draft"), "draft")
    return BriefOut(**d)


def list_briefs(
    session: Session,
    *,
    status: str | None = None,
    limit: int = 100,
) -> BriefsPage:
    params: dict = {"limit": min(limit, 200)}
    where = ""
    if status is not None:
        db_status = _API_TO_DB.get(status)
        if db_status:
            # 'completed' maps to 'finished'; also include 'cancelled' rows.
            if status == "completed":
                where = "WHERE b.status IN ('finished', 'cancelled')"
            else:
                where = "WHERE b.status = :status"
                params["status"] = db_status
    sql = f"{_LIST_SELECT} {where} ORDER BY b.updated_at DESC, b.id DESC LIMIT :limit"
    rows = session.execute(text(sql), params).mappings().all()
    return BriefsPage(items=[_to_brief_out(r) for r in rows])


def get_brief(session: Session, brief_id: int) -> BriefDetailOut:
    row = session.execute(
        text(f"{_LIST_SELECT} WHERE b.id = :id"),
        {"id": brief_id},
    ).mappings().first()
    if row is None:
        raise HTTPException(status_code=404, detail="Brief not found")
    base = _to_brief_out(row)
    versions = list_versions(session, brief_id)
    # Latest version content as content_md for the detail view.
    content_md = versions[0].content_md if versions else ""
    return BriefDetailOut(**base.model_dump(), content_md=content_md, versions=versions)


def patch_brief(
    session: Session,
    brief_id: int,
    *,
    title: str | None = None,
    status: str | None = None,
) -> BriefOut:
    if title is None and status is None:
        # No-op — return current state.
        return get_brief(session, brief_id)

    sets: list[str] = ["updated_at = now()"]
    params: dict = {"id": brief_id}
    if title is not None:
        sets.append("title = :title")
        params["title"] = title
    if status is not None:
        db_status = _API_TO_DB.get(status, "draft")
        sets.append("status = :status")
        params["status"] = db_status

    updated = session.execute(
        text(
            f"UPDATE crm.briefs SET {', '.join(sets)} WHERE id = :id RETURNING id"
        ),
        params,
    ).scalar_one_or_none()
    if updated is None:
        raise HTTPException(status_code=404, detail="Brief not found")

    row = session.execute(
        text(f"{_LIST_SELECT} WHERE b.id = :id"),
        {"id": brief_id},
    ).mappings().first()
    return _to_brief_out(row)


def create_brief(session: Session, *, title: str, content_md: str) -> BriefOut:
    brief_id = session.execute(
        text(
            "INSERT INTO crm.briefs (title, status, current_version) "
            "VALUES (:title, 'draft', 1) RETURNING id"
        ),
        {"title": title},
    ).scalar_one()
    version_id = session.execute(
        text(
            "INSERT INTO crm.brief_versions (brief_id, version, content) "
            "VALUES (:bid, 1, :content) RETURNING id"
        ),
        {"bid": brief_id, "content": json.dumps({"md": content_md})},
    ).scalar_one()
    return BriefOut(
        id=brief_id,
        title=title,
        status="draft",
        current_version=1,
        current_version_id=int(version_id),
    )


def add_version(session: Session, brief_id: int, content_md: str) -> BriefVersionOut:
    row = session.execute(
        text(
            "INSERT INTO crm.brief_versions (brief_id, version, content) "
            "SELECT :bid, COALESCE(MAX(version), 0) + 1, CAST(:content AS jsonb) "
            "FROM crm.brief_versions WHERE brief_id = :bid "
            "RETURNING id, version"
        ),
        {"bid": brief_id, "content": json.dumps({"md": content_md})},
    ).mappings().first()
    new_id = row["id"]
    new_version = row["version"]
    session.execute(
        text("UPDATE crm.briefs SET current_version = :v WHERE id = :bid"),
        {"v": new_version, "bid": brief_id},
    )
    return BriefVersionOut(
        id=int(new_id), brief_id=brief_id, version=int(new_version),
        content_md=content_md,
    )


def list_versions(session: Session, brief_id: int) -> list[BriefVersionOut]:
    rows = session.execute(
        text(
            "SELECT id, brief_id, version, content, created_at "
            "FROM crm.brief_versions WHERE brief_id = :bid "
            "ORDER BY version DESC"
        ),
        {"bid": brief_id},
    ).mappings().all()
    result = []
    for r in rows:
        row = dict(r)
        content = row.pop("content", None)
        if isinstance(content, dict):
            md = content.get("md", "")
        elif isinstance(content, str):
            try:
                md = json.loads(content).get("md", "")
            except (json.JSONDecodeError, AttributeError):
                md = content
        else:
            md = ""
        result.append(BriefVersionOut(content_md=md, **row))
    return result
