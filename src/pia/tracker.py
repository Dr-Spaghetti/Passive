from __future__ import annotations
import sqlite3
from datetime import date

from pia.storage import DB_PATH


def init_tracker() -> None:
    DB_PATH.parent.mkdir(exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS income_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT, stream_id TEXT, gross_usd REAL,
                fees_usd REAL, net_usd REAL, hours REAL,
                metrics TEXT, notes TEXT
            )
        """)


def log_income(stream_id: str, gross: float, fees: float, hours: float, notes: str = "") -> None:
    init_tracker()
    net = gross - fees
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO income_log (date,stream_id,gross_usd,fees_usd,net_usd,hours,metrics,notes) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (date.today().isoformat(), stream_id, gross, fees, net, hours, "{}", notes),
        )


def list_income_logs(limit: int = 25) -> list[dict]:
    """Return the most recent tracked income entries for the dashboard."""
    init_tracker()
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            "SELECT id, date, stream_id, gross_usd, fees_usd, net_usd, hours, notes "
            "FROM income_log ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [
        {
            "id": row[0],
            "date": row[1],
            "stream_id": row[2],
            "gross_usd": row[3],
            "fees_usd": row[4],
            "net_usd": row[5],
            "hours": row[6],
            "notes": row[7],
        }
        for row in rows
    ]


def check_drift(stream_id: str, plan_monthly_net: float, plan_monthly_hours: float) -> list[str]:
    """Returns list of alert strings. Empty = no drift."""
    init_tracker()
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            "SELECT net_usd, hours FROM income_log WHERE stream_id=? ORDER BY date DESC LIMIT 12",
            (stream_id,),
        ).fetchall()

    if not rows:
        return []

    alerts = []
    recent_nets = [r[0] for r in rows[:3]]
    recent_hours = [r[1] for r in rows[:4]]

    if len(recent_nets) >= 3 and all(n < plan_monthly_net * 0.5 for n in recent_nets):
        alerts.append(f"⚠ INCOME DRIFT: {stream_id} has been <50% of plan for 3 consecutive months.")

    if len(recent_hours) >= 4 and all(h > plan_monthly_hours * 1.5 for h in recent_hours):
        alerts.append(f"⚠ TIME DRIFT: {stream_id} has been >1.5x planned hours for 4 consecutive weeks.")

    return alerts
