from __future__ import annotations
from pia.output.renderer import render_ranked_table, render_portfolio_blueprint, DISCLAIMER


def test_ranked_table_contains_passivity_index(scored_list):
    md = render_ranked_table(scored_list)
    assert "Passivity" in md


def test_ranked_table_labels_semi_active(scored_list):
    md = render_ranked_table(scored_list)
    assert "(semi-active)" in md or all(s.stream.passivity_index >= 5 for s in scored_list)


def test_ranked_table_no_banned_phrases(scored_list):
    md = render_ranked_table(scored_list)
    assert "guaranteed" not in md.lower()
    assert "risk-free" not in md.lower()


def test_portfolio_blueprint_has_three_scenarios(portfolio_alloc):
    md = render_portfolio_blueprint(portfolio_alloc, monthly_projections={
        "bear": 100, "base": 200, "bull": 350
    })
    assert "bear" in md.lower() and "base" in md.lower() and "bull" in md.lower()


def test_disclaimer_present():
    assert "not financial" in DISCLAIMER.lower()
