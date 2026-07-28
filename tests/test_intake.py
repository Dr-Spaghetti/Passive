from __future__ import annotations

from pia.ai.intake import _coerce_provider_json


def test_coerce_replaces_list_skills_with_empty_object():
    data = {"skills": []}
    assert _coerce_provider_json(data)["skills"] == {}


def test_coerce_replaces_list_constraints_other_with_empty_string():
    data = {"constraints": {"other": []}}
    assert _coerce_provider_json(data)["constraints"]["other"] == ""


def test_coerce_drops_non_object_section_so_schema_default_applies():
    data = {"risk": "moderate", "goals": {"primary": "cash_flow"}}
    result = _coerce_provider_json(data)
    assert "risk" not in result
    assert result["goals"]["primary"] == "cash_flow"


def test_coerce_normalizes_out_of_enum_goal_to_default():
    data = {"goals": {"primary": "Generate $400 per month in passive income"}}
    assert _coerce_provider_json(data)["goals"]["primary"] == "cash_flow"


def test_coerce_normalizes_out_of_enum_cadence_and_liquidity():
    data = {
        "time": {"preferred_cadence": "whenever i feel like it"},
        "risk": {"liquidity_need": "flexible"},
    }
    result = _coerce_provider_json(data)
    assert result["time"]["preferred_cadence"] == "light_ops"
    assert result["risk"]["liquidity_need"] == "months"


def test_coerce_leaves_valid_enum_values_untouched():
    data = {"goals": {"primary": "wealth"}, "confidence": {"financial": "high"}}
    result = _coerce_provider_json(data)
    assert result["goals"]["primary"] == "wealth"
    assert result["confidence"]["financial"] == "high"
