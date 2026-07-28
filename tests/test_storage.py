from __future__ import annotations
import json
import pia.storage as storage


def test_save_and_list_runs(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "DB_PATH", tmp_path / "runs.db")
    storage.save_run(
        run_id="run-1",
        profile_id="profile-a",
        profile_json=json.dumps({"profile_id": "profile-a"}),
        top5_ids=["hysa", "tbills"],
        total_deployed=1000.0,
        projected_base=50.0,
    )
    runs = storage.list_runs()
    assert len(runs) == 1
    assert runs[0]["run_id"] == "run-1"
    assert runs[0]["profile_id"] == "profile-a"
    assert runs[0]["projected_base"] == 50.0


def test_save_run_replaces_existing_run_id(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "DB_PATH", tmp_path / "runs.db")
    storage.save_run("run-1", "profile-a", "{}", [], 0.0, 10.0)
    storage.save_run("run-1", "profile-a", "{}", [], 0.0, 99.0)
    runs = storage.list_runs()
    assert len(runs) == 1
    assert runs[0]["projected_base"] == 99.0


def test_list_runs_returns_all_saved_runs(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "DB_PATH", tmp_path / "runs.db")
    storage.save_run("run-a", "p", "{}", [], 0.0, 1.0)
    storage.save_run("run-b", "p", "{}", [], 0.0, 2.0)
    runs = storage.list_runs()
    assert {r["run_id"] for r in runs} == {"run-a", "run-b"}


def test_list_runs_empty_when_no_runs(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "DB_PATH", tmp_path / "runs.db")
    assert storage.list_runs() == []
