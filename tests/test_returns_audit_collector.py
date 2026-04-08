"""Tests for returns audit data collector."""
from unittest.mock import patch, MagicMock
import json
import os
import pytest

# Patch DB connections before importing collector
with patch.dict(os.environ, {
    "WB_API_KEY_IP": "test-ip-key",
    "WB_API_KEY_OOO": "test-ooo-key",
}):
    from scripts.returns_audit.collect_data import (
        _deduplicate_claims,
        _map_claims_to_models,
        _build_summary,
        _build_nm_id_to_article,
    )


class TestDeduplicateClaims:
    def test_removes_duplicates_by_id(self):
        claims = [
            {"id": "a", "nm_id": 1},
            {"id": "b", "nm_id": 2},
            {"id": "a", "nm_id": 1},
        ]
        result = _deduplicate_claims(claims)
        assert len(result) == 2
        ids = [c["id"] for c in result]
        assert ids == ["a", "b"]

    def test_empty_list(self):
        assert _deduplicate_claims([]) == []

    def test_no_duplicates(self):
        claims = [{"id": "a"}, {"id": "b"}, {"id": "c"}]
        assert len(_deduplicate_claims(claims)) == 3


class TestMapClaimsToModels:
    def test_maps_article_to_model(self):
        claims = [{"id": "a", "nm_id": 1, "imt_name": "Платье Wendy"}]
        result = _map_claims_to_models(claims, nm_id_to_article={1: "wendy/black/m"})
        assert result[0]["model"] == "wendy"
        assert result[0]["article"] == "wendy/black/m"

    def test_unknown_nm_id(self):
        claims = [{"id": "a", "nm_id": 999, "imt_name": "Unknown"}]
        result = _map_claims_to_models(claims, nm_id_to_article={})
        assert result[0]["model"] == "unknown"


class TestBuildNmIdToArticle:
    @patch("scripts.returns_audit.collect_data.get_nm_to_article_mapping", return_value={})
    def test_extracts_supplier_article(self, mock_mapping):
        claims = [{"nm_id": 1, "supplierArticle": "wendy/black/m"}]
        result = _build_nm_id_to_article(claims)
        assert result == {1: "wendy/black/m"}

    @patch("scripts.returns_audit.collect_data.get_nm_to_article_mapping", return_value={})
    def test_falls_back_to_sa_name(self, mock_mapping):
        claims = [{"nm_id": 1, "sa_name": "telma/red/s"}]
        result = _build_nm_id_to_article(claims)
        assert result == {1: "telma/red/s"}

    @patch("scripts.returns_audit.collect_data.get_nm_to_article_mapping", return_value={})
    def test_empty_when_no_article_fields(self, mock_mapping):
        claims = [{"nm_id": 1, "imt_name": "Some Product"}]
        result = _build_nm_id_to_article(claims)
        assert result == {}

    @patch("scripts.returns_audit.collect_data.get_nm_to_article_mapping", return_value={})
    def test_skips_claims_without_nm_id(self, mock_mapping):
        claims = [{"id": "a", "supplierArticle": "wendy/black/m"}]
        result = _build_nm_id_to_article(claims)
        assert result == {}

    @patch("scripts.returns_audit.collect_data.get_nm_to_article_mapping", return_value={1: "wendy/black/m"})
    def test_uses_supabase_mapping(self, mock_mapping):
        claims = [{"nm_id": 1}]
        result = _build_nm_id_to_article(claims)
        assert result == {1: "wendy/black/m"}

    @patch("scripts.returns_audit.collect_data.get_nm_to_article_mapping", return_value={1: "wendy/black/m"})
    def test_supabase_takes_priority(self, mock_mapping):
        claims = [{"nm_id": 1, "supplierArticle": "wrong/article"}]
        result = _build_nm_id_to_article(claims)
        assert result[1] == "wendy/black/m"


class TestBuildSummary:
    def test_summary_structure(self):
        claims = [
            {"id": "a", "model": "wendy"},
            {"id": "b", "model": "wendy"},
            {"id": "c", "model": "telma"},
        ]
        orders = {"wendy": {"count": 100}, "telma": {"count": 50}}
        summary = _build_summary(claims, orders)
        assert summary["total_claims"] == 3
        assert summary["by_model"]["wendy"]["claims"] == 2
        assert summary["by_model"]["wendy"]["orders"] == 100
        assert summary["by_model"]["wendy"]["rate_pct"] == pytest.approx(2.0)
        assert summary["by_model"]["telma"]["claims"] == 1
        assert summary["by_model"]["telma"]["rate_pct"] == pytest.approx(2.0)

    def test_zero_orders(self):
        claims = [{"id": "a", "model": "wendy"}]
        orders = {}
        summary = _build_summary(claims, orders)
        assert summary["by_model"]["wendy"]["rate_pct"] == 0.0
