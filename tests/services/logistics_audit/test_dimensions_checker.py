from services.logistics_audit.calculators.dimensions_checker import (
    check_dimensions,
    DimensionResult,
)


def test_no_discrepancy():
    """Volumes within 10% — no flag."""
    card_dims = {257131227: 2.904}
    wb_volumes = {257131227: 2.90}
    results = check_dimensions(card_dims, wb_volumes)
    assert len(results) == 1
    assert results[257131227].flagged is False


def test_discrepancy_above_10pct():
    """WB measured 20% more — flag it."""
    card_dims = {123: 0.9}
    wb_volumes = {123: 1.1}
    results = check_dimensions(card_dims, wb_volumes)
    assert results[123].flagged is True
    assert results[123].pct_diff > 10


def test_missing_wb_volume():
    """If WB didn't measure, no result for that nm_id."""
    card_dims = {123: 0.9}
    wb_volumes = {}
    results = check_dimensions(card_dims, wb_volumes)
    assert 123 not in results
