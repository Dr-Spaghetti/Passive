from __future__ import annotations
import pytest
from pia.schemas.stream import Stream, ScoredStream
from pia.engine.portfolio import PortfolioAllocation, AllocationItem


@pytest.fixture
def base_stream_dict():
    return {
        "stream_id": "hysa", "name": "HYSA", "category": "paper", "passivity_index": 10,
        "public_face_requirement": "none", "customer_support_requirement": "none",
        "capital_usd": {"min": 0, "typical": 10000, "scale_tiers": [100000]},
        "setup": {"hours": 1, "calendar_weeks": 0.25},
        "maintenance_hours_per_month": {"steady": 0.1, "year_1_avg": 0.2},
        "yield": {"unit": "annual_pct_on_capital", "bear": 3.5, "base": 4.5, "bull": 5.5},
        "time_to_first_dollar_days": {"bear": 30, "base": 7, "bull": 1},
        "risk": {"principal_loss": "low", "platform": "low", "regulatory": "low",
                 "liquidity": "high", "complexity": "low"},
        "scalability": "linear_capital", "data_freshness": "2026-07-22",
    }


@pytest.fixture
def scored_list(base_stream_dict):
    s = Stream(**base_stream_dict)
    low_p = Stream(**{**base_stream_dict, "stream_id": "tiktok", "name": "TikTok Shop",
                     "passivity_index": 3, "category": "commerce"})
    return [
        ScoredStream(stream=s, fit_score=85, ras=75, explain=["Good fit", "Low risk", "Open account"]),
        ScoredStream(stream=low_p, fit_score=40, ras=20, explain=["High maintenance", "Platform risk", "Setup store"]),
    ]


@pytest.fixture
def portfolio_alloc():
    return PortfolioAllocation(
        allocations=[AllocationItem("hysa", "HYSA", "core", "P0", 5000, 100.0, 10, 75)],
        total_deployed=5000, debt_gate_active=False,
    )
