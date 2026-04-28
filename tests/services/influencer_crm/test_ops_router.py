"""Tests for GET /ops/health.

Runs against the live Supabase instance the rest of the suite uses. The
endpoint must always return 200 with the documented shape — even when a
sub-source (e.g. pg_cron) is unavailable, the router degrades gracefully.
"""
from __future__ import annotations


def test_ops_health_shape(client, auth):
    r = client.get("/ops/health", headers=auth)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "etl_last_run" in body
    assert "etl_last_24h" in body
    assert "mv_age_seconds" in body
    assert "retention" in body
    assert "cron_jobs" in body
    assert isinstance(body["cron_jobs"], list)


def test_ops_health_requires_api_key(client):
    r = client.get("/ops/health")
    assert r.status_code == 403
