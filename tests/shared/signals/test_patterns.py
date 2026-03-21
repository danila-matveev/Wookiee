from shared.signals.patterns import BASE_PATTERNS


def test_base_patterns_count():
    assert len(BASE_PATTERNS) >= 20


def test_pattern_has_required_fields():
    required = {"pattern_name", "description", "category", "trigger_condition",
                 "impact_on", "severity", "source_tag", "confidence"}
    for p in BASE_PATTERNS:
        missing = required - set(p.keys())
        assert not missing, f"Pattern {p.get('pattern_name', '?')} missing: {missing}"


def test_all_categories_covered():
    categories = {p["category"] for p in BASE_PATTERNS}
    assert categories >= {"margin", "funnel", "adv", "price", "turnover"}


def test_source_tag_is_base():
    for p in BASE_PATTERNS:
        assert p["source_tag"] == "base"
