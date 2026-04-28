from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from services.influencer_crm.deps import get_session, verify_api_key
from services.influencer_crm.schemas.brief import (
    BriefCreate,
    BriefOut,
    BriefVersionCreate,
    BriefVersionOut,
)
from shared.data_layer.influencer_crm import briefs as repo

router = APIRouter(
    prefix="/briefs",
    tags=["briefs"],
    dependencies=[Depends(verify_api_key)],
)


@router.post("", response_model=BriefOut, status_code=status.HTTP_201_CREATED)
def create_brief(
    payload: BriefCreate,
    session: Session = Depends(get_session),
) -> BriefOut:
    return repo.create_brief(session, title=payload.title, content_md=payload.content_md)


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
