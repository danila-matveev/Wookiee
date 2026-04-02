"""Tests for monthly plan data collection orchestrator."""
import json
import pytest
from unittest.mock import patch, MagicMock
from scripts.monthly_plan.collect_all import run_collection


@patch("scripts.monthly_plan.collect_all.collect_pnl")
@patch("scripts.monthly_plan.collect_all.collect_pricing")
@patch("scripts.monthly_plan.collect_all.collect_advertising")
@patch("scripts.monthly_plan.collect_all.collect_inventory")
@patch("scripts.monthly_plan.collect_all.collect_abc")
@patch("scripts.monthly_plan.collect_all.collect_traffic")
@patch("scripts.monthly_plan.collect_all.collect_sheets")
def test_run_collection_merges_all_blocks(
    mock_sheets, mock_traffic, mock_abc, mock_inv,
    mock_adv, mock_pricing, mock_pnl,
):
    mock_pnl.return_value = {"pnl_total": {}, "pnl_models": {"active": [], "exiting": []}}
    mock_pricing.return_value = {"pricing": {"by_article": []}}
    mock_adv.return_value = {"advertising": {"by_model": []}}
    mock_inv.return_value = {"inventory": {"by_model": [], "risks": []}}
    mock_abc.return_value = {"abc": {"classification": []}}
    mock_traffic.return_value = {"traffic": {"by_model_current": []}}
    mock_sheets.return_value = {"sheets": {"financier_plan": {}}}

    result = run_collection("2026-05")

    assert "meta" in result
    assert result["meta"]["plan_month"] == "2026-05"
    assert "pnl_total" in result
    assert "pricing" in result
    assert "advertising" in result
    assert "inventory" in result
    assert "abc" in result
    assert "traffic" in result
    assert "sheets" in result
    assert "quality_flags" in result["meta"]

    # Verify JSON serializable
    json.dumps(result)
