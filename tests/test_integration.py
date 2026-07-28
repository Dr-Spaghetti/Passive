from __future__ import annotations
import json
import pytest
from pathlib import Path
from pia.schemas.profile import Profile
from pia.catalog.loader import load_catalog
from pia.engine.scorer import rank_streams
from pia.engine.portfolio import build_portfolio
from pia.output.renderer import render_ranked_table, render_portfolio_blueprint, DISCLAIMER
from pia.output.checklist import render_90day_checklist

FIXTURE_DIR = Path(__file__).parent / "fixtures"
CATALOG_DIR = Path(__file__).parent.parent / "catalog" / "streams"


def load_profile(name: str) -> Profile:
    with open(FIXTURE_DIR / f"profile_{name}.json") as f:
        return Profile(**json.load(f))


@pytest.fixture(scope="module")
def streams():
    return load_catalog(CATALOG_DIR)


def run_full_pipeline(profile_name, all_streams):
    profile = load_profile(profile_name)
    ranked = rank_streams(profile, all_streams)
    alloc = build_portfolio(profile, ranked)
    table_md = render_ranked_table(ranked)
    blueprint_md = render_portfolio_blueprint(alloc, {"bear": 0, "base": 100, "bull": 200})
    checklist_md = render_90day_checklist(ranked)
    return ranked, alloc, table_md, blueprint_md, checklist_md


def test_full_pipeline_all_fixtures(streams):
    for name in ("a", "b", "c", "d"):
        ranked, alloc, table, blueprint, checklist = run_full_pipeline(name, streams)
        assert len(ranked) > 0
        assert DISCLAIMER in blueprint
        assert "90-Day" in checklist


def test_fixture_d_shows_debt_warning(streams):
    _, alloc, _, blueprint, _ = run_full_pipeline("d", streams)
    assert alloc.debt_gate_active
    assert "DEBT GATE" in blueprint


def test_all_exports_contain_disclaimer(streams):
    _, _, table, blueprint, checklist = run_full_pipeline("b", streams)
    assert "not financial" in blueprint.lower()
    assert "not financial" in checklist.lower()


def test_no_single_point_yield_in_blueprint(streams):
    _, _, _, blueprint, _ = run_full_pipeline("a", streams)
    assert "guaranteed" not in blueprint.lower()
    assert "risk-free" not in blueprint.lower()
