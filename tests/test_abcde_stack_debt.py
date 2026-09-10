from __future__ import annotations

import json
from pathlib import Path

from pia.catalog.inventory import merge_inventory_into_profile, parse_inventory_markdown
from pia.catalog.loader import load_catalog
from pia.engine.portfolio import build_portfolio
from pia.engine.scorer import rank_streams, score_skill_leverage, score_stack_match, score_stream
from pia.output.decision_brief import build_decision_brief
from pia.schemas.profile import Profile, StackAsset, StackInventory
from pia.schemas.stream import Stream

CATALOG_DIR = Path(__file__).parent.parent / "catalog" / "streams"
FIXTURE_DIR = Path(__file__).parent / "fixtures"


def make_stream(**kwargs) -> Stream:
    defaults = {
        "stream_id": "test",
        "name": "Test",
        "category": "paper",
        "passivity_index": 8,
        "public_face_requirement": "none",
        "customer_support_requirement": "none",
        "capital_usd": {"min": 1000, "typical": 10000, "scale_tiers": [100000]},
        "setup": {"hours": 2, "calendar_weeks": 0.5},
        "maintenance_hours_per_month": {"steady": 1.0, "year_1_avg": 2.0},
        "yield": {"unit": "annual_pct_on_capital", "bear": 3.0, "base": 4.5, "bull": 6.0},
        "time_to_first_dollar_days": {"bear": 30, "base": 14, "bull": 7},
        "risk": {
            "principal_loss": "low",
            "platform": "low",
            "regulatory": "low",
            "liquidity": "high",
            "complexity": "low",
        },
        "scalability": "linear_capital",
        "data_freshness": "2026-07-22",
    }
    defaults.update(kwargs)
    return Stream(**defaults)


def nick_like_profile(**overrides) -> Profile:
    base = {
        "profile_id": "nick-test",
        "created_at": "2026-09-05",
        "financial": {
            "liquid_deployable_usd": {"min": 0, "max": 0},
            "monthly_surplus_usd": {"min": 200, "max": 500},
            "emergency_fund_months": 1,
            "high_interest_debt_usd": 2500,
            "target_monthly_passive_usd": 10000,
            "target_deadline_months": 12,
        },
        "time": {
            "setup_hours_per_week_90d": 35,
            "maintenance_hours_per_month_steady": 20,
            "preferred_cadence": "creative_ops",
        },
        "risk": {"score_1_to_10": 9, "exclusions": [], "liquidity_need": "months"},
        "skills": {
            "ai_ml": 9,
            "content": 8,
            "software": 8,
            "video": 5,
            "copywriting": 6,
            "marketing": 5,
            "domain_expertise": ["seo", "gbp", "ai", "panorama"],
        },
        "goals": {"primary": "cash_flow", "secondary": ["freedom"]},
        "stack": {
            "assets": [
                {
                    "name": "Justify Local AI/SEO skills",
                    "lane": "work",
                    "status": "fact",
                    "personal_use_ok": True,
                    "tags": ["seo", "gbp", "ai", "citation"],
                },
                {
                    "name": "Insta360 camera",
                    "lane": "work",
                    "status": "fact",
                    "personal_use_ok": True,
                    "tags": ["insta360", "360", "video", "pano"],
                },
                {
                    "name": "panostitch-pro",
                    "lane": "product",
                    "status": "fact",
                    "personal_use_ok": True,
                    "tags": ["panostitch", "pano", "software"],
                },
                {
                    "name": "BrightLocal",
                    "lane": "work",
                    "status": "fact",
                    "personal_use_ok": False,
                    "tags": ["seo", "brightlocal"],
                },
            ],
            "notes": ["WORK SaaS not personal capital"],
        },
    }
    base.update(overrides)
    return Profile(**base)


def test_capital_hard_dq_when_below_min():
    profile = nick_like_profile()
    stream = make_stream(
        stream_id="str_like",
        category="real_asset",
        capital_usd={"min": 5000, "typical": 30000, "scale_tiers": [100000]},
        passivity_index=4,
    )
    result = score_stream(profile, stream, [])
    assert result.disqualified is True
    assert result.unreachable_capital is True
    assert "below stream minimum" in result.disqualify_reason or "unreachable" in result.disqualify_reason.lower()


def test_zero_capital_still_allows_zero_min_streams():
    profile = nick_like_profile()
    stream = make_stream(
        stream_id="digital_zero",
        category="digital",
        capital_usd={"min": 0, "typical": 100, "scale_tiers": [500]},
        skills_leveraged=["ai_ml", "content"],
        **{"yield": {"unit": "monthly_usd_at_typical", "bear": 50, "base": 500, "bull": 2000}},
    )
    result = score_stream(profile, stream, [])
    assert result.disqualified is False


def test_nick_catalog_disqualifies_capital_heavy_streams():
    profile = nick_like_profile()
    streams = load_catalog(CATALOG_DIR)
    ranked = rank_streams(profile, streams)
    by_id = {r.stream.stream_id: r for r in ranked}
    assert by_id["str_rental"].disqualified is True
    assert by_id["house_hack"].disqualified is True
    assert by_id["longterm_rental_pm"].disqualified is True
    assert by_id["online_course"].disqualified is False


def test_debt_gate_surplus_guidance_and_risky_cap():
    profile = nick_like_profile()
    streams = load_catalog(CATALOG_DIR)
    ranked = rank_streams(profile, streams)
    alloc = build_portfolio(profile, ranked)
    assert alloc.debt_gate_active is True
    assert alloc.max_risky_allocation_pct == 10.0
    assert "60%" in alloc.surplus_allocation_guidance
    assert "Not financial advice" in alloc.surplus_allocation_guidance


def test_work_saas_without_personal_use_ok_excluded_from_tags():
    profile = nick_like_profile()
    tags = profile.stack_tags()
    assert "brightlocal" not in tags  # work + personal_use_ok False
    assert "seo" in tags  # from personal_use_ok work skills + domain
    assert "insta360" in tags


def test_stack_match_boosts_seo_and_video_streams():
    profile = nick_like_profile()
    affiliate = next(s for s in load_catalog(CATALOG_DIR) if s.stream_id == "affiliate_niche_site")
    stock = next(s for s in load_catalog(CATALOG_DIR) if s.stream_id == "stock_video")
    hysa = next(s for s in load_catalog(CATALOG_DIR) if s.stream_id == "hysa")
    aff = score_stream(profile, affiliate, [])
    vid = score_stream(profile, stock, [])
    paper = score_stream(profile, hysa, [])
    assert aff.disqualified is False
    assert vid.disqualified is False
    assert aff.stack_match_score > paper.stack_match_score
    assert vid.stack_match_score > paper.stack_match_score
    assert any("Stack" in e or "stack" in e.lower() or "Why this fits" in e for e in aff.explain)


def test_multi_skill_uses_coverage_not_only_max():
    stream = make_stream(skills_leveraged=["ai_ml", "content", "software"])
    deep = score_skill_leverage({"ai_ml": 9, "content": 0, "software": 0}, stream)
    broad = score_skill_leverage({"ai_ml": 7, "content": 7, "software": 7}, stream)
    assert broad >= deep - 5  # breadth should compete with single-max depth


def test_domain_expertise_boosts_matching_stream():
    stream = make_stream(
        stream_id="affiliate_niche_site",
        name="Affiliate Niche Website / SEO Blog",
        skills_leveraged=["content"],
        tool_stack_examples=["WordPress", "Ahrefs"],
        correlation_tags=["attention"],
    )
    base = score_skill_leverage({"content": 5}, stream, domain_expertise=[])
    boosted = score_skill_leverage({"content": 5}, stream, domain_expertise=["seo"])
    assert boosted > base


def test_brief_methods_are_stack_streams_not_static_abc():
    profile = nick_like_profile()
    streams = load_catalog(CATALOG_DIR)
    brief = build_decision_brief(profile, streams)
    method_ids = [m["id"] for m in brief["methods_compared"]]
    assert "A" not in method_ids
    assert "Passive-only dashboard" not in " ".join(m["name"] for m in brief["methods_compared"])
    assert brief["options"], "expected options"
    # Unreachable capital streams must not be primary
    primary = brief["options"][0]["stream_id"]
    assert primary not in {"str_rental", "house_hack", "longterm_rental_pm"}
    assert primary != "online_course", "stack-aware brief should not default to generic course spam"
    option_ids = {o["stream_id"] for o in brief["options"]}
    assert "affiliate_niche_site" in option_ids or "micro_saas" in option_ids or "stock_video" in option_ids
    assert "Surplus guidance" in brief["markdown"] or brief.get("surplus_allocation_guidance")
    assert "Methods compared (on your stack)" in brief["markdown"]
    assert any("Why this fits" in line for line in brief["markdown"].splitlines())
    assert "cos_contract" in brief


def test_brief_skips_unreachable_alts():
    profile = nick_like_profile()
    streams = load_catalog(CATALOG_DIR)
    brief = build_decision_brief(profile, streams)
    option_ids = {o["stream_id"] for o in brief["options"]}
    assert "str_rental" not in option_ids
    assert "house_hack" not in option_ids


def test_inventory_markdown_merge_does_not_invent_money(tmp_path):
    md = tmp_path / "inv.md"
    md.write_text(
        "# Inventory\n\nFACT Insta360 camera\nFACT BrightLocal WORK\nFACT panostitch-pro\n"
        "Director of AI Justify Local SEO GBP\n",
        encoding="utf-8",
    )
    profile = Profile(**json.loads((FIXTURE_DIR / "profile_a.json").read_text(encoding="utf-8")))
    before_debt = profile.financial.high_interest_debt_usd
    before_liq = profile.deployable_capital
    inv = parse_inventory_markdown(md)
    merged = merge_inventory_into_profile(profile, inv)
    assert merged.financial.high_interest_debt_usd == before_debt
    assert merged.deployable_capital == before_liq
    assert merged.stack.assets
    assert any(a.name.startswith("Insta360") for a in merged.stack.assets)


def test_plan_store_and_drift_api_helpers(tmp_path, monkeypatch):
    import pia.tracker as tracker

    monkeypatch.setattr(tracker, "DB_PATH", tmp_path / "runs.db")
    tracker.set_plan("online_course", 500.0, 8.0, profile_id="nick-test")
    plan = tracker.get_plan("online_course")
    assert plan["plan_monthly_net"] == 500.0
    # No logs → no drift alerts
    assert tracker.check_drift("online_course") == []
    for _ in range(3):
        tracker.log_income("online_course", gross=10.0, fees=0.0, hours=1.0, profile_id="nick-test")
    alerts = tracker.check_drift("online_course")
    assert any("INCOME DRIFT" in a for a in alerts)
