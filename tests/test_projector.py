from __future__ import annotations
import pytest
from pia.engine.projector import project_paper, project_digital, reverse_solve


def test_paper_projection_compounding():
    result = project_paper(principal=10000, annual_yield_pct=4.5,
                           monthly_contrib=0, months=12, reinvest=True)
    assert result["base"]["month_12"] > 10000
    assert result["bear"]["month_12"] < result["base"]["month_12"]
    assert result["bull"]["month_12"] > result["base"]["month_12"]


def test_paper_projection_monthly_income_no_reinvest():
    result = project_paper(principal=100000, annual_yield_pct=4.5,
                           monthly_contrib=0, months=1, reinvest=False)
    assert 300 < result["base"]["income_month_1"] < 450


def test_digital_projection_has_three_scenarios():
    result = project_digital(
        conversion_rate_pct=2.0, aov_usd=47, monthly_traffic_start=1000,
        monthly_traffic_growth_pct=10, platform_fee_pct=5, months=6
    )
    assert "bear" in result and "base" in result and "bull" in result


def test_reverse_solve_finds_capital():
    result = reverse_solve(target_monthly_usd=1000, months=24,
                           annual_yield_pct=4.5, monthly_contrib=200)
    assert result["required_principal"] > 0
    assert result["required_principal"] < 500000


def test_projections_never_single_point():
    r = project_paper(10000, 4.5, 0, 12, True)
    for scenario in ("bear", "base", "bull"):
        assert scenario in r
