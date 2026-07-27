from __future__ import annotations
import json
import pytest
from pathlib import Path
from pia.schemas.profile import Profile
from pia.schemas.stream import Stream
from pia.catalog.loader import load_catalog

CATALOG_DIR = Path(__file__).parent.parent / "catalog" / "streams"

HYSA_DICT = {
    "stream_id": "hysa",
    "name": "HYSA",
    "category": "paper",
    "passivity_index": 10,
    "capital_usd": {"min": 0, "typical": 10000, "scale_tiers": [100000]},
    "setup": {"hours": 1, "calendar_weeks": 0.25},
    "maintenance_hours_per_month": {"steady": 0.1, "year_1_avg": 0.2},
    "yield": {"unit": "annual_pct_on_capital", "bear": 3.5, "base": 4.5, "bull": 5.5, "as_of": "2026-07"},
    "time_to_first_dollar_days": {"bear": 30, "base": 7, "bull": 1},
    "risk": {"principal_loss": "low", "platform": "low", "regulatory": "low",
             "liquidity": "high", "complexity": "low"},
    "scalability": "linear_capital",
    "data_freshness": "2026-07-22",
}


def test_profile_loads_from_dict():
    data = {"profile_id": "test-001", "created_at": "2026-07-22T00:00:00"}
    p = Profile(**data)
    assert p.profile_id == "test-001"
    assert p.financial.liquid_deployable_usd.point == 0.0


def test_effective_risk_capped_when_low_emergency_fund():
    p = Profile(profile_id="x", created_at="2026-07-22",
                financial={"emergency_fund_months": 1},
                risk={"score_1_to_10": 8})
    assert p.effective_risk_score == 4


def test_effective_risk_uncapped_with_adequate_emergency_fund():
    p = Profile(profile_id="x", created_at="2026-07-22",
                financial={"emergency_fund_months": 6},
                risk={"score_1_to_10": 8})
    assert p.effective_risk_score == 8


def test_debt_gate_fires():
    p = Profile(profile_id="x", created_at="2026-07-22",
                financial={"high_interest_debt_usd": 12000})
    assert p.has_debt_gate is True


def test_stream_loads():
    s = Stream(**HYSA_DICT)
    assert s.stream_id == "hysa"
    assert s.passivity_index == 10


def test_stream_not_stale_when_fresh():
    s = Stream(**HYSA_DICT)
    assert s.is_stale is False


def test_stream_stale_when_old():
    d = {**HYSA_DICT, "data_freshness": "2020-01-01"}
    s = Stream(**d)
    assert s.is_stale is True


def test_stream_risk_composite():
    s = Stream(**HYSA_DICT)
    assert s.risk_composite == pytest.approx(1.0)


def test_catalog_loads_hysa():
    streams = load_catalog(CATALOG_DIR)
    ids = [s.stream_id for s in streams]
    assert "hysa" in ids


def test_catalog_all_have_required_fields():
    streams = load_catalog(CATALOG_DIR)
    for s in streams:
        assert s.passivity_index >= 0
        assert s.capital_usd.min >= 0
        assert s.yield_.base >= 0


def test_catalog_has_36_streams():
    streams = load_catalog(CATALOG_DIR)
    assert len(streams) == 36
