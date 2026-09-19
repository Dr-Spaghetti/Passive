from __future__ import annotations
import json
import sqlite3
from datetime import date, datetime, timedelta
from typing import Any

from pia.storage import DB_PATH


def init_tracker() -> None:
    DB_PATH.parent.mkdir(exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS income_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT, stream_id TEXT, gross_usd REAL,
                fees_usd REAL, net_usd REAL, hours REAL,
                metrics TEXT, notes TEXT,
                profile_id TEXT DEFAULT '',
                period_key TEXT DEFAULT ''
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS stream_plans (
                stream_id TEXT PRIMARY KEY,
                profile_id TEXT,
                plan_monthly_net REAL,
                plan_monthly_hours REAL,
                updated_at TEXT,
                notes TEXT DEFAULT ''
            )
        """)
        # Best-effort migrations for older DBs
        cols = {row[1] for row in conn.execute("PRAGMA table_info(income_log)").fetchall()}
        if "profile_id" not in cols:
            conn.execute("ALTER TABLE income_log ADD COLUMN profile_id TEXT DEFAULT ''")
        if "period_key" not in cols:
            conn.execute("ALTER TABLE income_log ADD COLUMN period_key TEXT DEFAULT ''")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS debt_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT,
                profile_id TEXT DEFAULT '',
                balance_usd REAL,
                payment_usd REAL,
                notes TEXT DEFAULT '',
                period_key TEXT DEFAULT ''
            )
        """)


def _period_key(when: date | None = None) -> str:
    d = when or date.today()
    return d.strftime("%Y-%m")


def log_income(
    stream_id: str,
    gross: float,
    fees: float,
    hours: float,
    notes: str = "",
    *,
    profile_id: str = "",
    metrics: dict[str, Any] | None = None,
    when: date | None = None,
) -> None:
    init_tracker()
    net = gross - fees
    d = when or date.today()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO income_log "
            "(date,stream_id,gross_usd,fees_usd,net_usd,hours,metrics,notes,profile_id,period_key) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                d.isoformat(),
                stream_id,
                gross,
                fees,
                net,
                hours,
                json.dumps(metrics or {}),
                notes,
                profile_id,
                _period_key(d),
            ),
        )


def list_income_logs(limit: int = 25, profile_id: str | None = None) -> list[dict]:
    """Return the most recent tracked income entries for the dashboard."""
    init_tracker()
    with sqlite3.connect(DB_PATH) as conn:
        if profile_id:
            rows = conn.execute(
                "SELECT id, date, stream_id, gross_usd, fees_usd, net_usd, hours, notes, "
                "profile_id, period_key, metrics "
                "FROM income_log WHERE profile_id=? ORDER BY id DESC LIMIT ?",
                (profile_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, date, stream_id, gross_usd, fees_usd, net_usd, hours, notes, "
                "profile_id, period_key, metrics "
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
            "profile_id": row[8] or "",
            "period_key": row[9] or "",
            "metrics": json.loads(row[10] or "{}"),
        }
        for row in rows
    ]


def set_plan(
    stream_id: str,
    plan_monthly_net: float,
    plan_monthly_hours: float,
    *,
    profile_id: str = "",
    notes: str = "",
) -> dict:
    init_tracker()
    now = datetime.now().astimezone().isoformat()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO stream_plans "
            "(stream_id, profile_id, plan_monthly_net, plan_monthly_hours, updated_at, notes) "
            "VALUES (?,?,?,?,?,?)",
            (stream_id, profile_id, plan_monthly_net, plan_monthly_hours, now, notes),
        )
    return get_plan(stream_id) or {}


def get_plan(stream_id: str) -> dict | None:
    init_tracker()
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT stream_id, profile_id, plan_monthly_net, plan_monthly_hours, updated_at, notes "
            "FROM stream_plans WHERE stream_id=?",
            (stream_id,),
        ).fetchone()
    if not row:
        return None
    return {
        "stream_id": row[0],
        "profile_id": row[1],
        "plan_monthly_net": row[2],
        "plan_monthly_hours": row[3],
        "updated_at": row[4],
        "notes": row[5],
    }


def list_plans(profile_id: str | None = None) -> list[dict]:
    init_tracker()
    with sqlite3.connect(DB_PATH) as conn:
        if profile_id:
            rows = conn.execute(
                "SELECT stream_id, profile_id, plan_monthly_net, plan_monthly_hours, updated_at, notes "
                "FROM stream_plans WHERE profile_id=? ORDER BY stream_id",
                (profile_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT stream_id, profile_id, plan_monthly_net, plan_monthly_hours, updated_at, notes "
                "FROM stream_plans ORDER BY stream_id"
            ).fetchall()
    return [
        {
            "stream_id": r[0],
            "profile_id": r[1],
            "plan_monthly_net": r[2],
            "plan_monthly_hours": r[3],
            "updated_at": r[4],
            "notes": r[5],
        }
        for r in rows
    ]


def _parse_log_date(value: str) -> date | None:
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def check_drift(
    stream_id: str,
    plan_monthly_net: float | None = None,
    plan_monthly_hours: float | None = None,
) -> list[str]:
    """Returns list of alert strings. Empty = no drift.

    Prefers stored plan baselines when plan_* args are omitted.
    Uses dated periods when possible (calendar months for income; ~7-day buckets for hours).
    """
    init_tracker()
    plan = get_plan(stream_id)
    if plan_monthly_net is None and plan:
        plan_monthly_net = float(plan["plan_monthly_net"])
    if plan_monthly_hours is None and plan:
        plan_monthly_hours = float(plan["plan_monthly_hours"])
    if plan_monthly_net is None or plan_monthly_hours is None:
        return ["No plan baselines — set via `pia plan set` or pass --plan-net/--plan-hours."]

    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            "SELECT date, net_usd, hours, period_key FROM income_log "
            "WHERE stream_id=? ORDER BY date DESC, id DESC LIMIT 24",
            (stream_id,),
        ).fetchall()

    if not rows:
        return []

    alerts: list[str] = []

    # Income drift: last 3 distinct calendar months (or last 3 rows if undated collapse)
    by_month: dict[str, list[float]] = {}
    for d, net, _hours, period in rows:
        key = period or (d[:7] if d else "")
        if not key:
            continue
        by_month.setdefault(key, []).append(float(net))
    month_keys = sorted(by_month.keys(), reverse=True)[:3]
    if len(month_keys) >= 3:
        month_nets = [sum(by_month[k]) for k in month_keys]
        if all(n < plan_monthly_net * 0.5 for n in month_nets):
            alerts.append(
                f"⚠ INCOME DRIFT: {stream_id} has been <50% of plan for 3 consecutive months."
            )
    else:
        recent_nets = [float(r[1]) for r in rows[:3]]
        if len(recent_nets) >= 3 and all(n < plan_monthly_net * 0.5 for n in recent_nets):
            alerts.append(
                f"⚠ INCOME DRIFT: {stream_id} has been <50% of plan for 3 consecutive months."
            )

    # Time drift: group into ~week buckets by date when possible
    week_hours: dict[str, float] = {}
    for d, _net, hours, _period in rows:
        parsed = _parse_log_date(d) if d else None
        if parsed:
            week_id = parsed - timedelta(days=parsed.weekday())
            key = week_id.isoformat()
        else:
            key = d or "unknown"
        week_hours[key] = week_hours.get(key, 0.0) + float(hours)
    week_keys = sorted(week_hours.keys(), reverse=True)[:4]
    if len(week_keys) >= 4 and all(week_hours[k] > plan_monthly_hours * 1.5 for k in week_keys):
        alerts.append(
            f"⚠ TIME DRIFT: {stream_id} has been >1.5x planned hours for 4 consecutive weeks."
        )
    else:
        recent_hours = [float(r[2]) for r in rows[:4]]
        if len(recent_hours) >= 4 and all(h > plan_monthly_hours * 1.5 for h in recent_hours):
            # Fallback row-count semantics (preserves prior tests)
            alerts.append(
                f"⚠ TIME DRIFT: {stream_id} has been >1.5x planned hours for 4 consecutive weeks."
            )

    return alerts


def log_debt(
    *,
    profile_id: str = "",
    balance_usd: float | None = None,
    payment_usd: float | None = None,
    notes: str = "",
    when: date | None = None,
) -> dict:
    """Append a debt ledger entry. Prefer explicit balance_usd; never invent amounts.

    At least one of balance_usd or payment_usd must be provided (user-entered only).
    """
    if balance_usd is None and payment_usd is None:
        raise ValueError("Provide balance_usd and/or payment_usd (user-entered; never invent).")
    if balance_usd is not None and balance_usd < 0:
        raise ValueError("balance_usd cannot be negative")
    if payment_usd is not None and payment_usd < 0:
        raise ValueError("payment_usd cannot be negative")
    init_tracker()
    d = when or date.today()
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute(
            "INSERT INTO debt_log "
            "(date, profile_id, balance_usd, payment_usd, notes, period_key) "
            "VALUES (?,?,?,?,?,?)",
            (
                d.isoformat(),
                profile_id or "",
                balance_usd,
                payment_usd,
                notes,
                _period_key(d),
            ),
        )
        row_id = cur.lastrowid
    return {
        "id": row_id,
        "date": d.isoformat(),
        "profile_id": profile_id or "",
        "balance_usd": balance_usd,
        "payment_usd": payment_usd,
        "notes": notes,
        "period_key": _period_key(d),
    }


def list_debt_logs(limit: int = 25, profile_id: str | None = None) -> list[dict]:
    """Return recent debt ledger entries (newest first)."""
    init_tracker()
    with sqlite3.connect(DB_PATH) as conn:
        if profile_id is not None:
            rows = conn.execute(
                "SELECT id, date, profile_id, balance_usd, payment_usd, notes, period_key "
                "FROM debt_log WHERE profile_id=? ORDER BY id DESC LIMIT ?",
                (profile_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, date, profile_id, balance_usd, payment_usd, notes, period_key "
                "FROM debt_log ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
    return [
        {
            "id": r[0],
            "date": r[1],
            "profile_id": r[2] or "",
            "balance_usd": r[3],
            "payment_usd": r[4],
            "notes": r[5] or "",
            "period_key": r[6] or "",
        }
        for r in rows
    ]


def latest_debt_balance_entry(profile_id: str = "") -> dict | None:
    """Latest row with an explicit balance_usd for profile_id (preferred over payments)."""
    init_tracker()
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT id, date, profile_id, balance_usd, payment_usd, notes, period_key "
            "FROM debt_log WHERE profile_id=? AND balance_usd IS NOT NULL "
            "ORDER BY date DESC, id DESC LIMIT 1",
            (profile_id or "",),
        ).fetchone()
    if not row:
        return None
    return {
        "id": row[0],
        "date": row[1],
        "profile_id": row[2] or "",
        "balance_usd": row[3],
        "payment_usd": row[4],
        "notes": row[5] or "",
        "period_key": row[6] or "",
    }


def debt_ledger_snapshot(profile_id: str = "") -> dict:
    """Summarize ledger for briefs: last explicit balance + gate status. Never invents money."""
    latest = latest_debt_balance_entry(profile_id)
    recent = list_debt_logs(limit=5, profile_id=profile_id or "")
    if latest is None:
        return {
            "latest_balance_entry": None,
            "recent_entries": recent,
            "gate_status": "unknown",
            "balance_usd": None,
            "note": (
                "No explicit balance entry in debt ledger — brief uses profile "
                "high_interest_debt_usd only; payment-only rows do not invent a remaining balance."
            ),
        }
    bal = float(latest["balance_usd"])
    if bal <= 0:
        gate = "cleared"
        note = (
            "User-entered debt ledger balance is $0 — debt gate can clear; "
            "high_interest_debt_usd input path cleared for this brief."
        )
    else:
        gate = "active"
        note = (
            f"User-entered debt ledger balance ${bal:,.2f} — debt gate active. "
            "Educational tracking only; not financial advice."
        )
    return {
        "latest_balance_entry": latest,
        "recent_entries": recent,
        "gate_status": gate,
        "balance_usd": bal,
        "note": note,
    }


def apply_debt_ledger_to_profile(profile: Any) -> tuple[Any, dict]:
    """Return (profile_for_scoring, ledger_meta).

    If the latest explicit ledger balance is 0, clear high_interest_debt_usd on a
    copy so has_debt_gate is false. If balance > 0, sync that user-entered balance
    onto the copy. Payment-only rows never invent a remaining balance.
    """
    from copy import deepcopy

    meta = debt_ledger_snapshot(getattr(profile, "profile_id", "") or "")
    bal = meta.get("balance_usd")
    if bal is None:
        # No explicit balance — leave profile money fields untouched
        if getattr(profile, "has_debt_gate", False):
            meta["gate_status"] = "active"
            meta["note"] = (
                "Debt gate follows profile.financial.high_interest_debt_usd "
                "(no explicit ledger balance yet)."
            )
        else:
            meta["gate_status"] = "cleared"
            meta["note"] = (
                "No high-interest debt on profile and no ledger balance entry."
            )
        meta["cleared_high_interest_debt_input"] = False
        meta["applied_balance_usd"] = None
        return profile, meta

    working = deepcopy(profile)
    # Sync only user-entered explicit balance — never invent from payments
    working.financial.high_interest_debt_usd = float(bal)
    meta["applied_balance_usd"] = float(bal)
    meta["cleared_high_interest_debt_input"] = float(bal) <= 0
    if float(bal) <= 0:
        meta["gate_status"] = "cleared"
        meta["note"] = (
            "User-entered ledger balance $0 — cleared high_interest_debt_usd for this brief; "
            "debt gate inactive. Educational only."
        )
    else:
        meta["gate_status"] = "active"
        meta["note"] = (
            f"Applied user-entered ledger balance ${float(bal):,.2f} to brief scoring. "
            "Educational only — not financial advice."
        )
    return working, meta

