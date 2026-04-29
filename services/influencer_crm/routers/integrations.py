"""Integrations endpoints — list (Kanban-aware), detail, create, patch, stage."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from services.influencer_crm.deps import get_session, verify_api_key
from services.influencer_crm.pagination import Page
from services.influencer_crm.schemas.integration import (
    IntegrationCreate,
    IntegrationDetailOut,
    IntegrationOut,
    IntegrationUpdate,
    StageTransitionIn,
)
from shared.data_layer.influencer_crm import integrations as repo

router = APIRouter(
    prefix="/integrations",
    tags=["integrations"],
    dependencies=[Depends(verify_api_key)],
)


@router.get("", response_model=Page[IntegrationOut])
def list_integrations(
    session: Session = Depends(get_session),
    limit: int = Query(50, ge=1, le=200),
    cursor: str | None = None,
    stage_in: list[str] | None = Query(default=None),
    marketplace: str | None = None,
    marketer_id: int | None = None,
    blogger_id: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> Page[IntegrationOut]:
    items, next_cursor = repo.list_integrations(
        session, limit=limit, cursor=cursor,
        stage_in=stage_in, marketplace=marketplace,
        marketer_id=marketer_id, blogger_id=blogger_id,
        date_from=date_from, date_to=date_to,
    )
    return Page[IntegrationOut](items=items, next_cursor=next_cursor)


@router.get("/{integration_id}", response_model=IntegrationDetailOut)
def get_integration(
    integration_id: int,
    session: Session = Depends(get_session),
) -> IntegrationDetailOut:
    detail = repo.get_integration(session, integration_id)
    if detail is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Integration not found")
    return detail


@router.post("", response_model=IntegrationOut, status_code=status.HTTP_201_CREATED)
def create_integration(
    payload: IntegrationCreate,
    session: Session = Depends(get_session),
) -> IntegrationOut:
    new_id = repo.create_integration(session, **payload.model_dump(exclude_unset=True))
    created = repo.get_integration(session, new_id)
    if created is None:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Created integration vanished")
    return IntegrationOut.model_validate(created.model_dump())


@router.patch("/{integration_id}", response_model=IntegrationOut)
def patch_integration(
    integration_id: int,
    payload: IntegrationUpdate,
    session: Session = Depends(get_session),
) -> IntegrationOut:
    repo.update_integration(session, integration_id, payload.model_dump(exclude_unset=True))
    updated = repo.get_integration(session, integration_id)
    if updated is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Integration not found")
    return IntegrationOut.model_validate(updated.model_dump())


@router.post("/{integration_id}/stage", response_model=IntegrationOut)
def transition_stage(
    integration_id: int,
    payload: StageTransitionIn,
    session: Session = Depends(get_session),
) -> IntegrationOut:
    repo.transition_stage(
        session, integration_id,
        target_stage=payload.target_stage,
        note=payload.note,
    )
    refreshed = repo.get_integration(session, integration_id)
    if refreshed is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Integration not found")
    return IntegrationOut.model_validate(refreshed.model_dump())
