def test_post_metrics_snapshot(client, auth):
    list_resp = client.get("/integrations", headers=auth, params={"limit": 1}).json()
    if not list_resp["items"]:
        import pytest
        pytest.skip("DB empty")
    iid = list_resp["items"][0]["id"]
    r = client.post(
        f"/metrics-snapshots/{iid}",
        headers=auth,
        json={"fact_views": 12345, "fact_clicks": 678, "note": "test snapshot"},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["integration_id"] == iid
    assert body["fact_views"] == 12345


def test_post_metrics_404_unknown_integration(client, auth):
    r = client.post(
        "/metrics-snapshots/999999999",
        headers=auth,
        json={"fact_views": 1},
    )
    assert r.status_code == 404
