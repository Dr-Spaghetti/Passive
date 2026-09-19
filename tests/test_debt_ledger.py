from __future__ import annotations

import json
from datetime import date

import pia.tracker as tracker
from pia.schemas.profile import Financial, Profile
from pia.output.commitment_brief import build_commitment_brief, render_commitment_markdown
from pia.output.decision_brief import build_decision_brief, render_brief_markdown
from pia.catalog.loader import load_catalog
from pathlib import Path as _Path

from fastapi.testclient import TestClient
from pia.web.server import app

CATALOG = _Path(__file__).resolve().parents[1] / "catalog" / "streams"


def _profile(debt: float = 2500.0) -> Profile:
    return Profile(
        profile_id="nick-test",
        created_at="2026-09-19",
        financial=Financial(high_interest_debt_usd=debt),
    )


def test_log_debt_prefers_explicit_balance(tmp_path, monkeypatch):
    monkeypatch.setattr(tracker, "DB_PATH", tmp_path / "runs.db")
    row = tracker.log_debt(profile_id="nick-test", balance_usd=1800.0, notes="statement")
    assert row["balance_usd"] == 1800.0
    assert row["period_key"]  # YYYY-MM
    rows = tracker.list_debt_logs(profile_id="nick-test")
    assert len(rows) == 1
    assert rows[0]["balance_usd"] == 1800.0


def test_payment_only_does_not_invent_remaining_balance(tmp_path, monkeypatch):
    monkeypatch.setattr(tracker, "DB_PATH", tmp_path / "runs.db")
    tracker.log_debt(profile_id="nick-test", payment_usd=200.0, notes="payment only")
    snap = tracker.debt_ledger_snapshot("nick-test")
    assert snap["balance_usd"] is None
    assert snap["gate_status"] == "unknown"
    assert "never invent" in snap["note"].lower() or "do not invent" in snap["note"].lower() or "payment-only" in snap["note"].lower()


def test_balance_zero_clears_debt_gate_on_brief_profile(tmp_path, monkeypatch):
    monkeypatch.setattr(tracker, "DB_PATH", tmp_path / "runs.db")
    p = _profile(2500.0)
    assert p.has_debt_gate is True
    tracker.log_debt(profile_id="nick-test", balance_usd=0.0, notes="paid off")
    working, meta = tracker.apply_debt_ledger_to_profile(p)
    assert working.has_debt_gate is False
    assert working.financial.high_interest_debt_usd == 0.0
    assert meta["gate_status"] == "cleared"
    assert meta["cleared_high_interest_debt_input"] is True
    # Original profile money field untouched (caller owns persistence)
    assert p.financial.high_interest_debt_usd == 2500.0


def test_positive_balance_syncs_user_entered_amount(tmp_path, monkeypatch):
    monkeypatch.setattr(tracker, "DB_PATH", tmp_path / "runs.db")
    p = _profile(2500.0)
    tracker.log_debt(profile_id="nick-test", balance_usd=900.0)
    working, meta = tracker.apply_debt_ledger_to_profile(p)
    assert working.financial.high_interest_debt_usd == 900.0
    assert working.has_debt_gate is True
    assert meta["gate_status"] == "active"
    assert meta["applied_balance_usd"] == 900.0


def test_commitment_and_decision_briefs_surface_ledger(tmp_path, monkeypatch):
    monkeypatch.setattr(tracker, "DB_PATH", tmp_path / "runs.db")
    streams = load_catalog(CATALOG)
    p = _profile(1200.0)
    tracker.log_debt(profile_id="nick-test", balance_usd=1200.0, notes="open")
    decision = build_decision_brief(p, streams)
    commitment = build_commitment_brief(p, streams)
    assert decision["debt_ledger"]["gate_status"] == "active"
    assert decision["debt_ledger"]["balance_usd"] == 1200.0
    assert commitment["debt_ledger"]["gate_status"] == "active"
    assert "Debt ledger" in decision["markdown"] or "Debt ledger" in render_brief_markdown(decision)
    assert "Debt ledger" in render_commitment_markdown(commitment)

    tracker.log_debt(profile_id="nick-test", balance_usd=0.0, notes="cleared")
    decision2 = build_decision_brief(p, streams)
    commitment2 = build_commitment_brief(p, streams)
    assert decision2["debt_gate_active"] is False
    assert decision2["debt_ledger"]["gate_status"] == "cleared"
    assert commitment2["debt_gate_active"] is False
    assert commitment2["debt_ledger"]["cleared_high_interest_debt_input"] is True
    md = render_commitment_markdown(commitment2)
    assert "cleared" in md.lower()


def test_api_debt_post_and_get(tmp_path, monkeypatch):
    monkeypatch.setattr(tracker, "DB_PATH", tmp_path / "web-debt.db")
    import pia.storage as storage
    monkeypatch.setattr(storage, "DB_PATH", tmp_path / "web-debt.db")
    client = TestClient(app)
    bad = client.post("/api/debt", json={"profile_id": "nick-test"})
    assert bad.status_code == 422
    ok = client.post(
        "/api/debt",
        json={"profile_id": "nick-test", "balance_usd": 500.0, "notes": "api"},
    )
    assert ok.status_code == 200
    body = ok.json()
    assert body["entry"]["balance_usd"] == 500.0
    assert body["snapshot"]["gate_status"] == "active"
    listed = client.get("/api/debt", params={"profile_id": "nick-test"})
    assert listed.status_code == 200
    assert listed.json()["entries"][0]["balance_usd"] == 500.0


def test_cli_debt_log_and_show(tmp_path, monkeypatch):
    monkeypatch.setattr(tracker, "DB_PATH", tmp_path / "cli-debt.db")
    from click.testing import CliRunner
    from pia.cli import cli

    runner = CliRunner()
    r = runner.invoke(
        cli,
        ["debt", "log", "--profile-id", "nick-test", "--balance", "100", "--notes", "cli"],
    )
    assert r.exit_code == 0, r.output
    assert "100" in r.output
    r2 = runner.invoke(cli, ["debt", "show", "--profile-id", "nick-test"])
    assert r2.exit_code == 0, r2.output
    data = json.loads(r2.output)
    assert data["snapshot"]["balance_usd"] == 100.0
    assert data["entries"][0]["notes"] == "cli"
