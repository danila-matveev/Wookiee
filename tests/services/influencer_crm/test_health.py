"""GET /health is unauthenticated and returns ok."""


def test_health_returns_ok(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_health_no_auth_required(client):
    # No X-API-Key header
    r = client.get("/api/health")
    assert r.status_code == 200
