"""Тесты reference_builder."""
from services.wb_localization.calculators.reference_builder import build_reference_content


def test_build_reference_structure_has_all_sections():
    result = build_reference_content()
    assert "cover" in result
    assert "formula_block" in result
    assert "il_section" in result
    assert "irp_section" in result
    assert "exceptions" in result
    assert "relocation_section" in result
    assert "sliding_window" in result
    assert "disclaimer" in result


def test_il_section_has_full_ktr_table():
    result = build_reference_content()
    ktr_table = result["il_section"]["table"]
    assert len(ktr_table) == 20
    first = ktr_table[0]
    assert "min_loc" in first
    assert "max_loc" in first
    assert "ktr" in first
    assert "color" in first


def test_irp_section_has_krp_table():
    result = build_reference_content()
    krp_table = result["irp_section"]["table"]
    assert len(krp_table) >= 13


def test_relocation_section_has_warehouses():
    result = build_reference_content()
    relocation = result["relocation_section"]
    assert relocation["commission_pct"] == 0.5
    assert relocation["lock_in_days"] == 90
    warehouses = relocation["warehouses"]
    assert len(warehouses) >= 20
    first = warehouses[0]
    assert "name" in first
    assert "limit_per_day" in first


def test_sliding_window_has_weeks_to_threshold():
    result = build_reference_content()
    window = result["sliding_window"]
    weeks = window["weeks_to_threshold"]
    from_values = [w["from_loc"] for w in weeks]
    assert 40 in from_values
    assert 50 in from_values
    assert 55 in from_values
