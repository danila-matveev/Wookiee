from __future__ import annotations

import json

from sqlalchemy import text
from sqlalchemy.orm import Session

from services.influencer_crm.schemas.brief import BriefOut, BriefVersionOut


def create_brief(session: Session, *, title: str, content_md: str) -> BriefOut:
    # crm.briefs: status NOT NULL, current_version is an integer (version number, not FK id)
    brief_id = session.execute(
        text(
            "INSERT INTO crm.briefs (title, status, current_version) "
            "VALUES (:title, 'draft', 1) RETURNING id"
        ),
        {"title": title},
    ).scalar_one()
    # crm.brief_versions: content is jsonb, no content_md column
    version_id = session.execute(
        text(
            "INSERT INTO crm.brief_versions (brief_id, version, content) "
            "VALUES (:bid, 1, :content) RETURNING id"
        ),
        {"bid": brief_id, "content": json.dumps({"md": content_md})},
    ).scalar_one()
    # Return with current_version_id mapped to the version row id
    return BriefOut(id=brief_id, title=title, current_version_id=int(version_id))


def add_version(session: Session, brief_id: int, content_md: str) -> BriefVersionOut:
    # Atomic: SELECT MAX + INSERT in one statement, no race window.
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
        # Extract content_md from the jsonb content field
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
