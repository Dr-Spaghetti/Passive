from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from pia.catalog.loader import load_catalog
from pia.engine.scorer import rank_streams, score_stream
from pia.output.commitment_brief import (
    build_commitment_brief,
    build_feasibility,
    pick_commitment,
    render_commitment_markdown,
)
from pia.output.decision_brief import select_options
from pia.schemas.profile import Profile

from tests.test_abcde_stack_debt import make_stream, nick_like_profile

CATALOG_DIR = Path(__file__).parent.parent / "catalog" / "streams"


def _top_ids(ranked, n: int = 8) -> list[str]:
    return [r.stream.stream_id for r in ranked if not r.disqualified][:n]


def test_maximize_default_on_profile():
    p = nick_like_profile()
    assert p.maximize_executable_upside is True


def test_target_and_deadline_do_not_change_rank_or_start_under_maximize():
    """P0: changing only target_monthly + deadline must not steer ranking/Start."""
    streams = load_catalog(CATALOG_DIR)
    base = nick_like_profile()
    assert base.maximize_executable_upside is True

    alt_data = base.model_dump()
    alt_data["financial"]["target_monthly_passive_usd"] = 50.0  # below low_ceiling trigger
    alt_data["financial"]["target_deadline_months"] = 60
    alt = Profile(**alt_data)

    ranked_hi = rank_streams(base, streams)
    ranked_lo = rank_streams(alt, streams)
    assert _top_ids(ranked_hi) == _top_ids(ranked_lo)

    cb_hi = build_commitment_brief(base, streams)
    cb_lo = build_commitment_brief(alt, streams)
    start_hi = (cb_hi.get("start") or {}).get("stream_id")
    start_lo = (cb_lo.get("start") or {}).get("stream_id")
    assert start_hi is not None
    assert start_hi == start_lo

    # Feasibility scoreboard may differ; Start must not.
    assert cb_hi["feasibility"]["target_monthly"] != cb_lo["feasibility"]["target_monthly"]
    assert cb_hi["feasibility"].get("scoreboard_only") is True


def test_low_ceiling_flag_informational_no_fit_penalty_under_maximize():
    profile = nick_like_profile()  # target 10k, cash_flow
    stream = make_stream(
        stream_id="tiny_yield_digital",
        category="digital",
        capital_usd={"min": 0, "typical": 50, "scale_tiers": [200]},
        skills_leveraged=["content"],
        **{"yield": {"unit": "monthly_usd_at_typical", "bear": 10, "base": 40, "bull": 80}},
    )
    scored = score_stream(profile, stream, [])
    assert scored.low_ceiling is True
    assert "low_ceiling" in scored.reachability_flags
    assert any("Informational stretch gap" in e or "does not change ranking" in e for e in scored.explain)
    # No soft penalty language about "weak as a primary path"
    assert not any("weak as a primary path" in e for e in scored.explain)

    # Legacy maximize-off still applies soft penalty
    legacy_data = profile.model_dump()
    legacy_data["maximize_executable_upside"] = False
    legacy = Profile(**legacy_data)
    scored_legacy = score_stream(legacy, stream, [])
    assert scored_legacy.low_ceiling is True
    assert scored_legacy.fit_score < scored.fit_score
    assert any("weak as a primary path" in e for e in scored_legacy.explain)


def test_select_options_and_pick_ignore_low_ceiling_under_maximize():
    streams = load_catalog(CATALOG_DIR)
    profile = nick_like_profile()
    ranked = rank_streams(profile, streams)
    # Ensure at least one low_ceiling exists among scored monthly streams
    assert any(r.low_ceiling for r in ranked)

    picks = select_options(ranked, maximize=True)
    # option_key must not prefer non-low_ceiling solely due to flag
    picks_legacy = select_options(ranked, maximize=False)
    # Both should return a primary; under maximize primary may be low_ceiling
    assert picks["primary"] is not None
    assert picks_legacy["primary"] is not None

    commit = pick_commitment(ranked, debt_gate_active=profile.has_debt_gate, maximize=True)
    assert commit["start"] is not None


def test_feasibility_stretch_gap_not_strategy_verdict():
    profile = nick_like_profile()
    streams = load_catalog(CATALOG_DIR)
    cb = build_commitment_brief(profile, streams)
    feas = cb["feasibility"]
    assert feas.get("scoreboard_only") is True
    # With aggressive 10k target, expect gap language
    assert feas["status"] in {"on_track", "stretch", "stretch_gap"}
    assert "unreachable" != feas["status"] or not profile.maximize_executable_upside
    assert "scoreboard" in feas["note"].lower() or "illustrative" in feas["note"].lower()
    assert "strategy verdict" in feas["note"].lower() or "does not change" in feas["note"].lower()


def test_kill_summary_omits_low_ceiling_group_under_maximize():
    streams = load_catalog(CATALOG_DIR)
    profile = nick_like_profile()
    cb = build_commitment_brief(profile, streams)
    kill = "\n".join(cb.get("kill_summary") or [])
    assert "Low ceiling:" not in kill


def test_render_commitment_markdown_has_sections():
    streams = load_catalog(CATALOG_DIR)
    profile = nick_like_profile()
    cb = build_commitment_brief(profile, streams)
    md = render_commitment_markdown(cb)
    for heading in ("## Start", "## Support", "## Kill / not now", "## Feasibility", "## First 7 days"):
        assert heading in md
    assert "maximize mode ON" in md


def test_legacy_maximize_off_deadline_can_change_time_factor():
    """Sanity: with maximize OFF, deadline still feeds time_to_first_dollar scoring."""
    streams = load_catalog(CATALOG_DIR)
    data = nick_like_profile().model_dump()
    data["maximize_executable_upside"] = False
    data["financial"]["target_deadline_months"] = 3
    short = Profile(**data)
    data2 = deepcopy(data)
    data2["financial"]["target_deadline_months"] = 120
    long = Profile(**data2)
    # Rank order or RAS values may differ when deadline changes under legacy
    r_short = {r.stream.stream_id: r.ras for r in rank_streams(short, streams) if not r.disqualified}
    r_long = {r.stream.stream_id: r.ras for r in rank_streams(long, streams) if not r.disqualified}
    # At least one shared stream should differ in RAS (deadline affects time factor)
    shared = set(r_short) & set(r_long)
    assert shared
    assert any(abs(r_short[s] - r_long[s]) > 1e-6 for s in shared)
