"""crm.tags — list + find-or-create (case-insensitive)."""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from services.influencer_crm.schemas.common import TagOut


def list_tags(session: Session) -> list[TagOut]:
    rows = session.execute(
        text("SELECT id, name FROM crm.tags ORDER BY LOWER(name)")
    ).mappings().all()
    return [TagOut(**dict(r)) for r in rows]


def find_or_create_tag(session: Session, name: str) -> TagOut:
    found = session.execute(
        text("SELECT id, name FROM crm.tags WHERE LOWER(name) = LOWER(:name)"),
        {"name": name},
    ).mappings().first()
    if found:
        return TagOut(**dict(found))
    new_id = session.execute(
        text("INSERT INTO crm.tags (name) VALUES (:name) RETURNING id"),
        {"name": name},
    ).scalar_one()
    return TagOut(id=int(new_id), name=name)
