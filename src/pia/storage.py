from __future__ import annotations
import json
import os
import sqlite3
from pathlib import Path
from datetime import date

DB_PATH = Path(os.environ.get("PIA_DB_PATH", Path(__file__).parent.parent.parent / "runs" / "runs.db"))


def init_db() -> None:
    DB_PATH.parent.mkdir(exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY,
                profile_id TEXT,
                created_at TEXT,
                profile_json TEXT,
                top5_ids TEXT,
                total_deployed REAL,
                projected_base REAL
            )
        """)


def save_run(
    run_id: str,
    profile_id: str,
    profile_json: str,
    top5_ids: list[str],
    total_deployed: float,
    projected_base: float,
) -> None:
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO runs VALUES (?,?,?,?,?,?,?)",
            (
                run_id,
                profile_id,
                date.today().isoformat(),
                profile_json,
                json.dumps(top5_ids),
                total_deployed,
                projected_base,
            ),
        )


def list_runs() -> list[dict]:
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            "SELECT run_id, profile_id, created_at, projected_base FROM runs ORDER BY created_at DESC"
        ).fetchall()
    return [{"run_id": r[0], "profile_id": r[1], "date": r[2], "projected_base": r[3]} for r in rows]
