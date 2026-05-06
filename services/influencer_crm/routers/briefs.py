from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from services.influencer_crm.deps import get_session, verify_api_key
from services.influencer_crm.schemas.brief import (
    BriefCreate,
    BriefDetailOut,
    BriefOut,
    BriefStatus,
    BriefUpdate,
    BriefVersionCreate,
    BriefVersionOut,
    BriefsPage,
)
from shared.data_layer.influencer_crm import briefs as repo

router = APIRouter(
    prefix="/briefs",
    tags=["briefs"],
    dependencies=[Depends(verify_api_key)],
)


@router.get("", response_model=BriefsPage)
def list_briefs(
    status: Optional[BriefStatus] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=200),
    session: Session = Depends(get_session),
) -> BriefsPage:
    return repo.list_briefs(session, status=status, limit=limit)


@router.get("/{brief_id}", response_model=BriefDetailOut)
def get_brief(
    brief_id: int,
    session: Session = Depends(get_session),
) -> BriefDetailOut:
    result = repo.get_brief(session, brief_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Brief not found")
    return result


@router.post("", response_model=BriefOut, status_code=status.HTTP_201_CREATED)
def create_brief(
    payload: BriefCreate,
    session: Session = Depends(get_session),
) -> BriefOut:
    return repo.create_brief(session, title=payload.title, content_md=payload.content_md)


@router.patch("/{brief_id}", response_model=BriefOut)
def patch_brief(
    brief_id: int,
    payload: BriefUpdate,
    session: Session = Depends(get_session),
) -> BriefOut:
    result = repo.patch_brief(
        session,
        brief_id,
        title=payload.title,
        status=payload.status,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Brief not found")
    return result


@router.delete("/{brief_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def delete_brief(
    brief_id: int,
    session: Session = Depends(get_session),
):
    found = repo.delete_brief(session, brief_id)
    if not found:
        raise HTTPException(status_code=404, detail="Brief not found")


@router.post(
    "/{brief_id}/versions",
    response_model=BriefVersionOut,
    status_code=status.HTTP_201_CREATED,
)
def add_version(
    brief_id: int,
    payload: BriefVersionCreate,
    session: Session = Depends(get_session),
) -> BriefVersionOut:
    return repo.add_version(session, brief_id, payload.content_md)


@router.get("/{brief_id}/versions", response_model=list[BriefVersionOut])
def list_versions(
    brief_id: int,
    session: Session = Depends(get_session),
) -> list[BriefVersionOut]:
    return repo.list_versions(session, brief_id)
