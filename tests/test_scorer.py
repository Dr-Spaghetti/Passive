from __future__ import annotations
import pytest
from pia.engine.scorer import (
    score_capital_fit,
    score_maintenance_fit,
    score_risk_alignment,
    score_skill_leverage,
    score_goal_alignment,
    score_time_to_first_dollar,
    score_diversification_value,
    score_stream,
    rank_streams,
)
from pia.schemas.stream import Stream
from pia.schemas.profile import Profile


def make_stream(**kwargs) -> Stream:
    defaults = {
        "stream_id": "test", "name": "Test", "category": "paper",
        "passivity_index": 8,
        "capital_usd": {"min": 1000, "typical": 10000, "scale_tiers": [100000]},
        "setup": {"hours": 2, "calendar_weeks": 0.5},
        "maintenance_hours_per_month": {"steady": 1.0, "year_1_avg": 2.0},
        "yield": {"unit": "annual_pct_on_capital", "bear": 3.0, "base": 4.5, "bull": 6.0},
        "time_to_first_dollar_days": {"bear": 30, "base": 14, "bull": 7},
        "risk": {"principal_loss": "low", "platform": "low", "regulatory": "low",
                 "liquidity": "high", "complexity": "low"},
        "scalability": "linear_capital",
        "data_freshness": "2026-07-22",
    }
    defaults.update(kwargs)
    return Stream(**defaults)


def test_capital_fit_severe_underfund():
    s = make_stream(capital_usd={"min": 10000, "typical": 50000, "scale_tiers": [200000]})
    score = score_capital_fit(capital=1000, stream=s)
    assert score < 50


def test_capital_fit_in_range():
    s = make_stream(capital_usd={"min": 1000, "typical": 10000, "scale_tiers": [100000]})
    score = score_capital_fit(capital=5500, stream=s)
    assert 70 <= score <= 100


def test_capital_fit_at_typical():
    s = make_stream(capital_usd={"min": 1000, "typical": 10000, "scale_tiers": [100000]})
    score = score_capital_fit(capital=10000, stream=s)
    assert score == 100


def test_capital_fit_over_scale():
    s = make_stream(capital_usd={"min": 1000, "typical": 10000, "scale_tiers": [100000]})
    score = score_capital_fit(capital=200000, stream=s)
    assert score == 90


def test_maintenance_fit_perfect():
    s = make_stream(maintenance_hours_per_month={"steady": 1.0, "year_1_avg": 2.0})
    score = score_maintenance_fit(monthly_hours_budget=10.0, stream=s)
    assert score == 100


def test_maintenance_fit_disqualify():
    s = make_stream(maintenance_hours_per_month={"steady": 20.0, "year_1_avg": 25.0})
    disq, score = score_maintenance_fit(monthly_hours_budget=10.0, stream=s, return_disqualify=True)
    assert disq is True


def test_maintenance_fit_partial():
    s = make_stream(maintenance_hours_per_month={"steady": 8.0, "year_1_avg": 10.0})
    score = score_maintenance_fit(monthly_hours_budget=10.0, stream=s)
    assert 70 <= score < 100


def test_risk_exclusion_penalty():
    s = make_stream()
    s2 = Stream(**{**s.model_dump(by_alias=True), "exclusions_match": ["crypto"]})
    score = score_risk_alignment(user_risk=5, user_exclusions=["crypto"], stream=s2)
    assert score < 20


def test_risk_low_user_prefers_low_risk():
    s = make_stream(risk={"principal_loss": "low", "platform": "low", "regulatory": "low",
                          "liquidity": "high", "complexity": "low"})
    score = score_risk_alignment(user_risk=2, user_exclusions=[], stream=s)
    assert score >= 80


def test_skill_leverage_no_skills_needed():
    s = make_stream()
    score = score_skill_leverage(user_skills={}, stream=s)
    assert score == 50


def test_skill_leverage_high_match():
    s = make_stream()
    s2 = Stream(**{**s.model_dump(by_alias=True), "skills_leveraged": ["ai_ml", "content"]})
    score = score_skill_leverage(user_skills={"ai_ml": 9, "content": 8}, stream=s2)
    assert score >= 90


def test_goal_cash_flow_boosts_high_passivity():
    s = make_stream()
    score = score_goal_alignment(primary_goal="cash_flow", stream=s)
    assert score >= 70


def test_goal_wealth_boosts_equity():
    s = make_stream()
    s2 = Stream(**{**s.model_dump(by_alias=True), "category": "paper",
                   "correlation_tags": ["equity"]})
    score = score_goal_alignment(primary_goal="wealth", stream=s2)
    assert score >= 70


def test_time_to_first_dollar_fast_scores_high():
    s = make_stream(time_to_first_dollar_days={"bear": 7, "base": 1, "bull": 1})
    score = score_time_to_first_dollar(target_deadline_days=365, stream=s)
    assert score >= 90


def test_time_to_first_dollar_slow_scores_low():
    s = make_stream(time_to_first_dollar_days={"bear": 365, "base": 270, "bull": 180})
    score = score_time_to_first_dollar(target_deadline_days=180, stream=s)
    assert score < 50


def test_diversification_new_tag_adds_value():
    s = make_stream()
    s2 = Stream(**{**s.model_dump(by_alias=True), "correlation_tags": ["local_economy"]})
    score = score_diversification_value(selected_tags=["rates", "equity"], stream=s2)
    assert score > 50


def test_diversification_duplicate_tag_penalized():
    s = make_stream()
    s2 = Stream(**{**s.model_dump(by_alias=True), "correlation_tags": ["rates"]})
    score = score_diversification_value(selected_tags=["rates", "rates", "rates"], stream=s2)
    assert score < 50


def test_composite_score_produces_scored_stream():
    from pia.schemas.stream import ScoredStream
    profile = Profile(
        profile_id="t", created_at="2026-07-22",
        financial={"liquid_deployable_usd": {"min": 5000, "max": 10000},
                   "emergency_fund_months": 4},
        time={"maintenance_hours_per_month_steady": 5},
        risk={"score_1_to_10": 5},
        goals={"primary": "cash_flow"},
    )
    stream = make_stream()
    result = score_stream(profile=profile, stream=stream, selected_tags=[])
    assert isinstance(result, ScoredStream)
    assert 0 <= result.fit_score <= 100
    assert result.ras >= 0
    assert result.disqualified is False
