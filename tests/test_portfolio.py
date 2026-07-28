from __future__ import annotations
import json
from pathlib import Path
from pia.schemas.profile import Profile
from pia.schemas.stream import ScoredStream, Stream
from pia.engine.portfolio import build_portfolio, PortfolioAllocation


def load_profile(name: str) -> Profile:
    with open(Path(__file__).parent / "fixtures" / f"profile_{name}.json") as f:
        return Profile(**json.load(f))


def make_scored(stream_id: str, category: str, ras: float, passivity: int, tags: list) -> ScoredStream:
    base = {
        "stream_id": stream_id, "name": stream_id, "category": category,
        "passivity_index": passivity,
        "public_face_requirement": "none",
        "customer_support_requirement": "none",
        "capital_usd": {"min": 0, "typical": 5000, "scale_tiers": [50000]},
        "setup": {"hours": 2, "calendar_weeks": 1},
        "maintenance_hours_per_month": {"steady": 1.0, "year_1_avg": 2.0},
        "yield": {"unit": "annual_pct_on_capital", "bear": 3.0, "base": 4.5, "bull": 6.0},
        "time_to_first_dollar_days": {"bear": 30, "base": 14, "bull": 7},
        "risk": {"principal_loss": "low", "platform": "low", "regulatory": "low",
                 "liquidity": "high", "complexity": "low"},
        "scalability": "linear_capital",
        "correlation_tags": tags,
        "data_freshness": "2026-07-22",
    }
    return ScoredStream(stream=Stream(**base), ras=ras, fit_score=ras, capital_suggested_usd=5000)


def test_portfolio_respects_max_single_stream_pct():
    profile = load_profile("b")
    scored = [
        make_scored("hysa", "paper", 90, 10, ["rates"]),
        make_scored("tbills", "paper", 88, 10, ["rates"]),
        make_scored("dividend_etf", "paper", 80, 9, ["equity"]),
    ]
    alloc = build_portfolio(profile, scored)
    if alloc.total_deployed > 0:
        for item in alloc.allocations:
            pct = item.allocation_usd / alloc.total_deployed
            assert pct <= 0.35 + 1e-9, f"{item.stream_id} exceeds 35% single-stream cap"


def test_portfolio_core_floor_for_low_risk():
    profile = load_profile("b")
    scored = [
        make_scored("hysa", "paper", 90, 10, ["rates"]),
        make_scored("dividend_etf", "paper", 85, 9, ["equity"]),
        make_scored("faceless_youtube", "content", 60, 6, ["attention"]),
    ]
    alloc = build_portfolio(profile, scored)
    if alloc.total_deployed > 0:
        core_usd = sum(i.allocation_usd for i in alloc.allocations if i.tier == "core")
        assert core_usd / alloc.total_deployed >= 0.40


def test_portfolio_has_phases():
    profile = load_profile("a")
    scored = [make_scored(f"stream_{i}", "digital", 70, 7, ["attention"]) for i in range(3)]
    alloc = build_portfolio(profile, scored)
    phases = {i.phase for i in alloc.allocations}
    assert "P0" in phases or "P1" in phases


def test_portfolio_debt_gate_message():
    profile = load_profile("d")
    scored = [make_scored("hysa", "paper", 90, 10, ["rates"])]
    alloc = build_portfolio(profile, scored)
    assert alloc.debt_gate_active is True
    assert "DEBT GATE" in alloc.debt_gate_message
