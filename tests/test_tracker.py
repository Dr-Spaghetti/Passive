from __future__ import annotations
import sqlite3
import pia.tracker as tracker


def test_log_income_computes_net(tmp_path, monkeypatch):
    monkeypatch.setattr(tracker, "DB_PATH", tmp_path / "runs.db")
    tracker.log_income("hysa", gross=100.0, fees=10.0, hours=2.0, notes="test")
    with sqlite3.connect(tracker.DB_PATH) as conn:
        row = conn.execute(
            "SELECT stream_id, gross_usd, fees_usd, net_usd, hours, notes FROM income_log"
        ).fetchone()
    assert row == ("hysa", 100.0, 10.0, 90.0, 2.0, "test")


def test_check_drift_no_data_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(tracker, "DB_PATH", tmp_path / "runs.db")
    assert tracker.check_drift("nonexistent", 100.0, 5.0) == []


def test_check_drift_income_drift_fires_after_3_low_months(tmp_path, monkeypatch):
    monkeypatch.setattr(tracker, "DB_PATH", tmp_path / "runs.db")
    for _ in range(3):
        tracker.log_income("stream-x", gross=10.0, fees=0.0, hours=1.0)
    alerts = tracker.check_drift("stream-x", plan_monthly_net=100.0, plan_monthly_hours=5.0)
    assert any("INCOME DRIFT" in a for a in alerts)


def test_check_drift_time_drift_fires_after_4_high_hour_weeks(tmp_path, monkeypatch):
    monkeypatch.setattr(tracker, "DB_PATH", tmp_path / "runs.db")
    for _ in range(4):
        tracker.log_income("stream-y", gross=200.0, fees=0.0, hours=10.0)
    alerts = tracker.check_drift("stream-y", plan_monthly_net=100.0, plan_monthly_hours=5.0)
    assert any("TIME DRIFT" in a for a in alerts)


def test_check_drift_no_alerts_when_on_plan(tmp_path, monkeypatch):
    monkeypatch.setattr(tracker, "DB_PATH", tmp_path / "runs.db")
    for _ in range(4):
        tracker.log_income("stream-z", gross=100.0, fees=0.0, hours=5.0)
    alerts = tracker.check_drift("stream-z", plan_monthly_net=100.0, plan_monthly_hours=5.0)
    assert alerts == []


def test_check_drift_only_2_low_months_does_not_fire(tmp_path, monkeypatch):
    monkeypatch.setattr(tracker, "DB_PATH", tmp_path / "runs.db")
    for _ in range(2):
        tracker.log_income("stream-w", gross=10.0, fees=0.0, hours=1.0)
    alerts = tracker.check_drift("stream-w", plan_monthly_net=100.0, plan_monthly_hours=5.0)
    assert alerts == []


def test_list_income_logs_returns_newest_entries(tmp_path, monkeypatch):
    monkeypatch.setattr(tracker, "DB_PATH", tmp_path / "runs.db")
    tracker.log_income("hysa", gross=20.0, fees=1.0, hours=0.5, notes="first")
    tracker.log_income("tbills", gross=30.0, fees=0.0, hours=0.25, notes="second")
    logs = tracker.list_income_logs()
    assert [entry["stream_id"] for entry in logs] == ["tbills", "hysa"]
    assert logs[0]["net_usd"] == 30.0
