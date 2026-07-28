from __future__ import annotations

import json
from pathlib import Path

import pytest

from fastapi.testclient import TestClient

from pia.web.server import app


client = TestClient(app)
FIXTURE_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def isolate_web_database(tmp_path, monkeypatch):
    import pia.storage as storage
    import pia.tracker as tracker

    db_path = tmp_path / "web-runs.db"
    monkeypatch.setattr(storage, "DB_PATH", db_path)
    monkeypatch.setattr(tracker, "DB_PATH", db_path)


def profile_payload(name: str = "b") -> dict:
    return json.loads((FIXTURE_DIR / f"profile_{name}.json").read_text(encoding="utf-8"))


def test_health_and_homepage_are_available():
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert health.json()["catalog_streams"] > 0

    home = client.get("/")
    assert home.status_code == 200
    assert "Passive Income Analyzer" in home.text
    assert "Private local parsing works offline" in home.text


def test_analyze_returns_a_complete_safe_result():
    response = client.post("/api/analyze", json={"profile": profile_payload()})
    assert response.status_code == 200
    body = response.json()
    assert body["ranked_streams"]
    assert len(body["projection_series"]["base"]) == 24
    assert body["monthly_projections"]["bear"] <= body["monthly_projections"]["base"]
    assert body["monthly_projections"]["base"] <= body["monthly_projections"]["bull"]
    assert all(item["allocation_usd"] >= 0 for item in body["portfolio"]["allocations"])
    first_stream = body["ranked_streams"][0]
    assert first_stream["public_face_requirement"] in {"none", "optional", "required"}
    assert first_stream["customer_support_requirement"] in {"none", "light", "ongoing"}
    assert "yield_as_of" in first_stream
    assert "data_freshness" in first_stream
    assert "sources_note" in first_stream

    # The scenario chart must aggregate each paper allocation at that stream's
    # own yield, rather than applying one representative yield to the whole mix.
    streams = {stream["stream_id"]: stream for stream in body["ranked_streams"]}
    for scenario in ("bear", "base", "bull"):
        expected = sum(
            round(
                allocation["allocation_usd"]
                * streams[allocation["stream_id"]][f"yield_{scenario}"]
                / 100
                / 12,
                2,
            )
            for allocation in body["portfolio"]["allocations"]
            if streams[allocation["stream_id"]]["category"] == "paper"
            and streams[allocation["stream_id"]]["yield_unit"] == "annual_pct_on_capital"
        )
        assert body["monthly_projections"][scenario] == round(expected, 2)

    saved = client.get("/api/runs")
    assert saved.status_code == 200
    assert saved.json()["runs"][0]["profile_id"] == body["profile_id"]


def test_analyze_rejects_invalid_financial_ranges():
    payload = profile_payload()
    payload["financial"]["liquid_deployable_usd"] = {"min": 5000, "max": 1000}
    response = client.post("/api/analyze", json={"profile": payload})
    assert response.status_code == 422
    assert "minimum cannot exceed maximum" in response.json()["detail"]


def test_playbook_has_a_useful_offline_fallback(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    response = client.post(
        "/api/playbook/hysa", json={"profile": profile_payload()}
    )
    assert response.status_code == 200
    assert "Startup Checklist" in response.json()["content"]


def test_intake_requires_a_description():
    response = client.post("/api/intake", json={"text": "  "})
    assert response.status_code == 422


def test_offline_intake_is_useful_without_a_provider_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    response = client.post(
        "/api/intake",
        json={
            "text": (
                "I have $12,000 to invest, 6 months emergency fund, and no debt. "
                "I can spend 8 hours per week and 3 hours per month. "
                "My target is $750 per month within 18 months. I am moderate risk, "
                "have software and marketing skills, and want no public face or customer support."
            )
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["intake_source"] == "offline"
    assert body["financial"]["liquid_deployable_usd"] == {"min": 12_000, "max": 12_000, "point": 12_000}
    assert body["financial"]["emergency_fund_months"] == 6
    assert body["financial"]["target_monthly_passive_usd"] == 750
    assert body["financial"]["target_deadline_months"] == 18
    assert body["time"]["setup_hours_per_week_90d"] == 8
    assert body["time"]["maintenance_hours_per_month_steady"] == 3
    assert body["skills"]["software"] == 6
    assert body["constraints"]["no_public_face"] is True
    assert body["constraints"]["no_customer_support"] is True


def test_intake_falls_back_when_the_provider_is_unavailable(monkeypatch):
    import pia.ai.intake as intake

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(intake, "_provider_intake", lambda *_args: (_ for _ in ()).throw(RuntimeError("quota")))
    response = client.post("/api/intake", json={"text": "I have $5,000 to invest and can work 4 hours a week."})

    assert response.status_code == 200
    assert response.json()["intake_source"] == "offline_fallback"


def test_playbook_falls_back_when_the_provider_is_unavailable(monkeypatch):
    import pia.ai.playbooks as playbooks

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(playbooks, "_provider_playbook", lambda *_args: (_ for _ in ()).throw(RuntimeError("quota")))
    response = client.post("/api/playbook/hysa", json={"profile": profile_payload()})

    assert response.status_code == 200
    assert "Built-in practical playbook" in response.json()["content"]


def test_stream_catalog_has_dashboard_fields():
    response = client.get("/api/streams")
    assert response.status_code == 200
    hysa = next(stream for stream in response.json() if stream["stream_id"] == "hysa")
    assert hysa["passivity_index"] == 10
    assert hysa["yield_base"] > 0
    assert hysa["public_face_requirement"] == "none"
    assert hysa["customer_support_requirement"] == "none"
    assert hysa["yield_as_of"]
    assert hysa["data_freshness"]
    assert hysa["sources_note"]


def test_reverse_solver_endpoint_validates_and_calculates():
    response = client.post(
        "/api/reverse-solve",
        json={"target_monthly_usd": 1_000, "months": 24, "annual_yield_pct": 5, "monthly_contrib": 100},
    )
    assert response.status_code == 200
    assert response.json()["required_principal"] > 0

    invalid = client.post(
        "/api/reverse-solve",
        json={"target_monthly_usd": 0, "months": 24, "annual_yield_pct": 5, "monthly_contrib": 100},
    )
    assert invalid.status_code == 422


def test_tracker_log_rejects_unknown_stream():
    response = client.post(
        "/api/tracker",
        json={"stream_id": "not-a-stream", "gross_usd": 100, "fees_usd": 0, "hours": 1},
    )
    assert response.status_code == 404
