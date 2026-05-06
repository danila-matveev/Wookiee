"""Pydantic schemas for /integrations."""
from __future__ import annotations

from datetime import date
from decimal import Decimal


def test_integration_out_minimal_payload():
    from services.influencer_crm.schemas.integration import IntegrationOut

    i = IntegrationOut(
        id=1, blogger_id=2, marketer_id=3,
        publish_date=date(2026, 4, 1),
        channel="instagram", ad_format="story", marketplace="wb",
        stage="переговоры", total_cost=Decimal("0"),
    )
    d = i.model_dump(mode="json")
    assert d["total_cost"] == "0"
    assert d["publish_date"] == "2026-04-01"


def test_stage_transition_input_requires_target():
    import pytest
    from pydantic import ValidationError
    from services.influencer_crm.schemas.integration import StageTransitionIn

    with pytest.raises(ValidationError):
        StageTransitionIn()  # type: ignore[call-arg]


def test_stage_transition_validates_known_stage():
    import pytest
    from pydantic import ValidationError
    from services.influencer_crm.schemas.integration import StageTransitionIn

    StageTransitionIn(target_stage="согласовано")
    with pytest.raises(ValidationError):
        StageTransitionIn(target_stage="bogus_stage")


def test_integration_out_has_primary_substitute_code():
    """primary_substitute_code must be optional string."""
    from services.influencer_crm.schemas.integration import IntegrationOut

    fields = IntegrationOut.model_fields
    assert "primary_substitute_code" in fields, (
        "IntegrationOut must have primary_substitute_code field"
    )
    field = fields["primary_substitute_code"]
    assert not field.is_required(), (
        "primary_substitute_code must be optional (None default)"
    )
