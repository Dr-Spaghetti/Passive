"""JSON inventory source-of-truth + WORK lane rules + CLI CRUD."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from pia.catalog.inventory import (
    add_asset,
    import_markdown_to_json,
    list_assets,
    load_inventory,
    load_inventory_json,
    merge_inventory_into_profile,
    remove_asset,
    save_inventory_json,
    update_asset,
    validate_inventory,
    work_blocked_assets,
)
from pia.cli import cli
from pia.engine.scorer import rank_streams, score_stream
from pia.catalog.loader import load_catalog
from pia.output.decision_brief import build_decision_brief
from pia.schemas.profile import Profile, StackAsset, StackInventory

FIXTURE_DIR = Path(__file__).parent / "fixtures"
NICK_INV = FIXTURE_DIR / "nick_stack_inventory.json"
CATALOG_DIR = Path(__file__).parent.parent / "catalog" / "streams"


def test_load_inventory_json_validates_schema():
    inv = load_inventory_json(NICK_INV)
    assert inv.assets
    assert any(a.name == "BrightLocal" for a in inv.assets)
    assert all(a.status in {"fact", "unknown", "weak_fact"} for a in inv.assets)


def test_load_inventory_prefers_json_path():
    inv = load_inventory(NICK_INV)
    assert inv.source.endswith("nick_stack_inventory.json") or "nick_stack_inventory" in inv.source


def test_invalid_json_raises():
    with pytest.raises(ValueError, match="Invalid inventory|Unsupported|must be"):
        validate_inventory({"no_assets_key": True})


def test_work_blocked_without_personal_use_ok():
    inv = load_inventory_json(NICK_INV)
    blocked = {a.name for a in work_blocked_assets(inv)}
    assert "BrightLocal" in blocked
    assert "Local Falcon" in blocked
    assert "Runway AI" in blocked
    assert "Higgsfield" in blocked
    # skills transferable / personal_use_ok true → not blocked
    assert "Justify Local AI/SEO skills" not in blocked
    assert "Insta360 camera" not in blocked


def test_merge_json_excludes_work_saas_from_stack_tags():
    profile = Profile(**json.loads((FIXTURE_DIR / "profile_a.json").read_text(encoding="utf-8")))
    before_liq = profile.deployable_capital
    before_debt = profile.financial.high_interest_debt_usd
    inv = load_inventory_json(NICK_INV)
    merged = merge_inventory_into_profile(profile, inv)
    tags = merged.stack_tags()
    assert "brightlocal" not in tags
    assert "local falcon" not in tags
    assert "runway" not in tags
    assert "higgsfield" not in tags
    assert "seo" in tags  # from personal_use_ok skills
    assert "panostitch" in tags or "pano" in tags
    # never invent money
    assert merged.deployable_capital == before_liq
    assert merged.financial.high_interest_debt_usd == before_debt
    assert any("WORK blocked" in n for n in merged.stack.notes)


def test_unknown_status_excluded_from_deployable():
    inv = StackInventory(
        assets=[
            StackAsset(name="Mystery drone", lane="personal", status="unknown", tags=["drone"]),
            StackAsset(name="pia", lane="personal", status="fact", tags=["software", "pia"]),
        ]
    )
    deployable = list_assets(inv, deployable_only=True)
    assert [a.name for a in deployable] == ["pia"]


def test_crud_add_update_remove_roundtrip(tmp_path):
    path = tmp_path / "inv.json"
    inv = StackInventory(assets=[], notes=["test"], source=str(path))
    inv = add_asset(inv, name="BrightLocal", lane="work", status="fact", tags=["seo"], personal_use_ok=False)
    save_inventory_json(inv, path)
    loaded = load_inventory_json(path)
    assert len(loaded.assets) == 1
    loaded = update_asset(loaded, "BrightLocal", personal_use_ok=True, status="weak_fact")
    assert loaded.assets[0].personal_use_ok is True
    assert loaded.assets[0].status == "weak_fact"
    loaded = remove_asset(loaded, "BrightLocal")
    assert loaded.assets == []
    save_inventory_json(loaded, path)
    assert load_inventory_json(path).assets == []


def test_scorer_does_not_credit_work_only_gear_tags():
    """WORK SaaS tags must not boost stack_match unless personal_use_ok."""
    base = {
        "profile_id": "lane-test",
        "created_at": "2026-09-19",
        "financial": {
            "liquid_deployable_usd": {"min": 0, "max": 0},
            "monthly_surplus_usd": {"min": 200, "max": 500},
            "emergency_fund_months": 1,
            "high_interest_debt_usd": 0,
            "target_monthly_passive_usd": 1000,
            "target_deadline_months": 12,
        },
        "time": {"setup_hours_per_week_90d": 10, "maintenance_hours_per_month_steady": 10},
        "risk": {"score_1_to_10": 5, "exclusions": []},
        "skills": {"content": 5, "domain_expertise": []},
        "goals": {"primary": "cash_flow"},
        "stack": {
            "assets": [
                {
                    "name": "BrightLocal",
                    "lane": "work",
                    "status": "fact",
                    "personal_use_ok": False,
                    "tags": ["seo", "gbp", "brightlocal", "citation"],
                }
            ]
        },
    }
    blocked = Profile(**base)
    assert "brightlocal" not in blocked.stack_tags()
    assert "seo" not in blocked.stack_tags()

    allowed = Profile(
        **{
            **base,
            "stack": {
                "assets": [
                    {
                        "name": "BrightLocal",
                        "lane": "work",
                        "status": "fact",
                        "personal_use_ok": True,
                        "tags": ["seo", "gbp", "brightlocal"],
                    }
                ]
            },
        }
    )
    assert "brightlocal" in allowed.stack_tags()
    streams = load_catalog(CATALOG_DIR)
    affiliate = next(s for s in streams if s.stream_id == "affiliate_niche_site")
    score_blocked = score_stream(blocked, affiliate, [])
    score_allowed = score_stream(allowed, affiliate, [])
    assert score_allowed.stack_match_score > score_blocked.stack_match_score


def test_brief_stack_notes_cite_json_inventory_not_work_saas_as_capital():
    profile = Profile(**json.loads((FIXTURE_DIR / "profile_a.json").read_text(encoding="utf-8")))
    inv = load_inventory_json(NICK_INV)
    merged = merge_inventory_into_profile(profile, inv)
    brief = build_decision_brief(merged, load_catalog(CATALOG_DIR))
    md = brief["markdown"]
    assert "personal_use_ok" in md or "WORK-lane" in md
    # BrightLocal may appear in blocked notes but must not be listed as deployable Stack (work) line
    # deployable notes use Stack (lane): names — BrightLocal is work + not personal_use_ok
    for line in md.splitlines():
        if line.startswith("- Stack (work):"):
            assert "BrightLocal" not in line


def test_cli_inventory_crud(tmp_path):
    path = tmp_path / "stack.json"
    runner = CliRunner()
    r = runner.invoke(
        cli,
        [
            "inventory", "add", "--file", str(path),
            "--name", "Local Falcon", "--lane", "work", "--status", "fact",
            "--tag", "seo", "--no-personal-use-ok",
        ],
    )
    assert r.exit_code == 0, r.output
    r = runner.invoke(cli, ["inventory", "list", "--file", str(path), "--json"])
    assert r.exit_code == 0
    rows = json.loads(r.output)
    assert rows[0]["name"] == "Local Falcon"
    assert rows[0]["personal_use_ok"] is False
    r = runner.invoke(
        cli,
        ["inventory", "update", "--file", str(path), "--name", "Local Falcon", "--status", "unknown"],
    )
    assert r.exit_code == 0
    r = runner.invoke(cli, ["inventory", "remove", "--file", str(path), "--name", "Local Falcon"])
    assert r.exit_code == 0
    assert load_inventory_json(path).assets == []


def test_cli_import_md_migration(tmp_path):
    md = tmp_path / "inv.md"
    md.write_text("# FACT\nInsta360\nBrightLocal WORK\npanostitch\nVercel\n", encoding="utf-8")
    out = tmp_path / "out.json"
    runner = CliRunner()
    r = runner.invoke(cli, ["inventory", "import-md", "--from", str(md), "--to", str(out)])
    assert r.exit_code == 0, r.output
    inv = load_inventory_json(out)
    assert inv.assets
    assert any("migration" in n.lower() or "Migrated" in n for n in inv.notes)


def test_markdown_still_loads_as_migration_path(tmp_path):
    md = tmp_path / "old.md"
    md.write_text("FACT Insta360\nFACT BrightLocal\n", encoding="utf-8")
    inv = load_inventory(md)
    assert any(a.name.startswith("Insta360") for a in inv.assets)
