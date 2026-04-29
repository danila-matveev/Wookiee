from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from services.influencer_crm.deps import get_session, verify_api_key
from services.influencer_crm.schemas.metrics import MetricsSnapshotIn, MetricsSnapshotOut
from shared.data_layer.influencer_crm import metrics as repo

router = APIRouter(
    prefix="/metrics-snapshots",
    tags=["metrics"],
    dependencies=[Depends(verify_api_key)],
)


@router.post(
    "/{integration_id}",
    response_model=MetricsSnapshotOut,
    status_code=status.HTTP_201_CREATED,
)
def create_snapshot(
    integration_id: int,
    payload: MetricsSnapshotIn,
    session: Session = Depends(get_session),
) -> MetricsSnapshotOut:
    snap = repo.insert_snapshot(session, integration_id, payload.model_dump(exclude_unset=True))
    if snap is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Integration not found")
    return snap
