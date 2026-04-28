"""X-API-Key gate."""
from fastapi import APIRouter, Depends
from fastapi.testclient import TestClient

from services.influencer_crm.app import create_app
from services.influencer_crm.deps import verify_api_key


def test_missing_api_key_blocks_request():
    # Mount a protected probe endpoint
    app = create_app()
    r = APIRouter()

    @r.get("/probe")
    def probe(_=Depends(verify_api_key)) -> dict:
        return {"ok": True}

    app.include_router(r)
    with TestClient(app) as tc:
        resp = tc.get("/probe")
    assert resp.status_code == 403
    assert "X-API-Key" in resp.json()["detail"]


def test_wrong_api_key_blocks_request():
    app = create_app()
    r = APIRouter()

    @r.get("/probe")
    def probe(_=Depends(verify_api_key)) -> dict:
        return {"ok": True}
    app.include_router(r)
    with TestClient(app) as tc:
        resp = tc.get("/probe", headers={"X-API-Key": "wrong"})
    assert resp.status_code == 403


def test_correct_api_key_allows_request(auth):
    app = create_app()
    r = APIRouter()

    @r.get("/probe")
    def probe(_=Depends(verify_api_key)) -> dict:
        return {"ok": True}
    app.include_router(r)
    with TestClient(app) as tc:
        resp = tc.get("/probe", headers=auth)
    assert resp.status_code == 200
