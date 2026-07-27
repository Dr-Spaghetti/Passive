from __future__ import annotations
import json
import pytest
from pathlib import Path
from pia.schemas.profile import Profile
from pia.catalog.loader import load_catalog
from pia.engine.scorer import rank_streams

FIXTURE_DIR = Path(__file__).parent / "fixtures"
CATALOG_DIR = Path(__file__).parent.parent / "catalog" / "streams"


def load_profile(name: str) -> Profile:
    with open(FIXTURE_DIR / f"profile_{name}.json") as f:
        return Profile(**json.load(f))


@pytest.fixture(scope="module")
def streams():
    return load_catalog(CATALOG_DIR)


def top5(profile: Profile, all_streams) -> list[str]:
    ranked = rank_streams(profile, all_streams)
    qualified = [r for r in ranked if not r.disqualified]
    return [r.stream.stream_id for r in qualified[:5]]


def test_fixture_a_b_c_have_different_top5(streams):
    top_a = set(top5(load_profile("a"), streams))
    top_b = set(top5(load_profile("b"), streams))
    top_c = set(top5(load_profile("c"), streams))
    all_unique = top_a | top_b | top_c
    assert len(all_unique) >= 7, f"Fixtures A/B/C don't surface enough unique streams: {all_unique}"
    assert len(top_a - top_b) >= 1, f"A and B identical: A={top_a}, B={top_b}"
    assert len(top_b - top_c) >= 1, f"B and C identical: B={top_b}, C={top_c}"


def test_fixture_a_prioritizes_digital(streams):
    top = top5(load_profile("a"), streams)
    digital_streams = {"notion_templates", "faceless_youtube", "amazon_kdp",
                       "print_on_demand", "online_course", "ebooks", "printables", "ai_art_stock"}
    assert len(set(top) & digital_streams) >= 1, f"Fixture A should have >=1 digital stream: {top}"


def test_fixture_b_prioritizes_paper(streams):
    top = top5(load_profile("b"), streams)
    paper_streams = {"hysa", "tbills", "cd_ladder", "dividend_etf", "bond_etf",
                     "us_index_etf", "equity_reit_etf", "preferred_income"}
    assert len(set(top) & paper_streams) >= 3, f"Fixture B should be paper-heavy: {top}"


def test_fixture_c_includes_local_or_paper(streams):
    top = top5(load_profile("c"), streams)
    local_paper = {"parking", "storage_rental", "equipment_rental",
                   "hysa", "tbills", "cd_ladder", "dividend_etf"}
    assert len(set(top) & local_paper) >= 1, f"Fixture C should include local or paper: {top}"


def test_fixture_d_debt_gate_fires(streams):
    profile = load_profile("d")
    assert profile.has_debt_gate is True
    assert profile.effective_risk_score <= 4


def test_fixture_d_low_emergency_fund_caps_risk(streams):
    profile = load_profile("d")
    assert profile.financial.emergency_fund_months < 3
    assert profile.effective_risk_score == 4
