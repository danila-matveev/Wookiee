from __future__ import annotations

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from services.influencer_crm.deps import get_session, verify_api_key
from services.influencer_crm.schemas.common import TagOut
from shared.data_layer.influencer_crm import tags as repo

router = APIRouter(
    prefix="/tags",
    tags=["tags"],
    dependencies=[Depends(verify_api_key)],
)


class TagCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)


@router.get("", response_model=list[TagOut])
def list_tags(session: Session = Depends(get_session)) -> list[TagOut]:
    return repo.list_tags(session)


@router.post("", response_model=TagOut, status_code=status.HTTP_201_CREATED)
def create_tag(
    payload: TagCreate,
    session: Session = Depends(get_session),
) -> TagOut:
    return repo.find_or_create_tag(session, payload.name)
