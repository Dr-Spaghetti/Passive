from __future__ import annotations

from typing import Any

from pia.engine.portfolio import build_portfolio
from pia.engine.scorer import rank_streams
from pia.schemas.profile import Profile
from pia.schemas.stream import ScoredStream, Stream

DISCLAIMER = (
    "Educational planning only — not financial, legal, or tax advice. "
    "Verify current yields and requirements before allocating capital or time."
)


def stream_is_stale(stream: Stream) -> bool:
    """Prefer Stream.is_stale (data_freshness); do not infer solely from yield.as_of."""
    return bool(getattr(stream, "is_stale", False))


def _option_payload(scored: ScoredStream) -> dict[str, Any]:
    s = scored.stream
    checklist = list(s.startup_checklist or [])[:3]
    kills = list(s.kill_criteria or [])[:2]
    return {
        "stream_id": s.stream_id,
        "name": s.name,
        "category": s.category,
        "fit_score": scored.fit_score,
        "ras": scored.ras,
        "passivity_index": s.passivity_index,
        "passivity_label": s.passivity_label,
        "capital_suggested_usd": scored.capital_suggested_usd,
        "time_to_first_dollar_days": {
            "bear": s.time_to_first_dollar_days.bear,
            "base": s.time_to_first_dollar_days.base,
            "bull": s.time_to_first_dollar_days.bull,
        },
        "yield": {
            "bear": s.yield_.bear,
            "base": s.yield_.base,
            "bull": s.yield_.bull,
            "unit": s.yield_.unit,
            "as_of": s.yield_.as_of,
        },
        "explain": scored.explain,
        "week1_actions": checklist,
        "kill_criteria": kills,
        "stale": stream_is_stale(s),
    }


def select_options(ranked: list[ScoredStream]) -> dict[str, ScoredStream | None]:
    """Pick primary + up to two alternatives across categories when possible."""
    qualified = [r for r in ranked if not r.disqualified]
    if not qualified:
        return {"primary": None, "alt_a": None, "alt_b": None}

    passive_ok = [r for r in qualified if r.stream.passivity_index >= 6]
    pool = passive_ok or qualified
    primary = max(pool, key=lambda r: r.ras)

    rest = [r for r in qualified if r.stream.stream_id != primary.stream.stream_id]
    alt_a = None
    for r in sorted(rest, key=lambda x: x.ras, reverse=True):
        if r.stream.category != primary.stream.category:
            alt_a = r
            break
    if alt_a is None and rest:
        alt_a = max(rest, key=lambda x: x.ras)

    used = {primary.stream.stream_id}
    if alt_a:
        used.add(alt_a.stream.stream_id)
    remaining = [r for r in qualified if r.stream.stream_id not in used]
    alt_b = max(remaining, key=lambda x: x.fit_score) if remaining else None

    return {"primary": primary, "alt_a": alt_a, "alt_b": alt_b}


def catalog_freshness_report(streams: list[Stream]) -> dict[str, Any]:
    rows = []
    stale_n = 0
    for s in streams:
        stale = stream_is_stale(s)
        stale_n += int(stale)
        rows.append(
            {
                "stream_id": s.stream_id,
                "as_of": s.yield_.as_of if s.yield_ else None,
                "data_freshness": getattr(s, "data_freshness", "") or None,
                "stale": stale,
            }
        )
    return {"total": len(streams), "stale_count": stale_n, "streams": rows}


def build_decision_brief(
    profile: Profile,
    streams: list[Stream],
    *,
    stack_notes: list[str] | None = None,
) -> dict[str, Any]:
    ranked = rank_streams(profile, streams)
    alloc = build_portfolio(profile, ranked)
    picks = select_options(ranked)

    options: list[dict[str, Any]] = []
    labels = [("primary", "Recommended start"), ("alt_a", "Strong alternative"), ("alt_b", "Third option")]
    for key, label in labels:
        scored = picks.get(key)
        if scored is None:
            continue
        payload = _option_payload(scored)
        payload["role"] = key
        payload["role_label"] = label
        options.append(payload)

    week_actions: list[str] = []
    if options:
        for i, step in enumerate(options[0].get("week1_actions") or [], 1):
            week_actions.append(f"Day {i*2 - 1}–{i*2}: {step}")
    week_actions.append("End of week: log any time/money spent in Income Tracker (or `pia log <stream_id>`).")
    week_actions.append("Talk to CoS with results — keep, swap to an alt, or re-brief.")

    stale_flags = [o["stream_id"] for o in options if o.get("stale")]
    freshness = catalog_freshness_report(streams)

    brief = {
        "disclaimer": DISCLAIMER,
        "profile_id": profile.profile_id,
        "goal": {
            "primary": profile.goals.primary,
            "target_monthly_passive_usd": profile.financial.target_monthly_passive_usd,
            "deadline_months": profile.financial.target_deadline_months,
        },
        "debt_gate_active": alloc.debt_gate_active,
        "debt_gate_message": alloc.debt_gate_message,
        "options": options,
        "portfolio_summary": {
            "total_deployed": alloc.total_deployed,
            "phase_summary": alloc.phase_summary,
            "allocation_count": len(alloc.allocations),
        },
        "seven_day_plan": week_actions,
        "catalog_freshness": {
            "stale_in_options": stale_flags,
            "catalog_stale_count": freshness["stale_count"],
            "catalog_total": freshness["total"],
        },
        "stack_notes": stack_notes
        or [
            "CoS is the front door: state goals/outputs; CoS compares methods across your stack.",
            "pia remains the scoring/projection engine (fit, RAS, disqualify, portfolio).",
            "Optional later: Jarvis-Pro skill calling the same brief API for local agent runs.",
        ],
        "methods_compared": [
            {
                "id": "A",
                "name": "Passive-only dashboard",
                "verdict": "rejected_as_primary_ux",
                "note": "Strong engine; weak as the only interface for goal→execution.",
            },
            {
                "id": "B",
                "name": "Jarvis-Pro hub",
                "verdict": "secondary",
                "note": "Use for local agent workforce; not the daily front door for this goal.",
            },
            {
                "id": "C",
                "name": "CoS hub + pia engine",
                "verdict": "winner",
                "note": "Talk goals to CoS; brief uses pia rankings; track and re-brief weekly.",
            },
        ],
    }
    brief["markdown"] = render_brief_markdown(brief)
    return brief


def render_brief_markdown(brief: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Passive income decision brief")
    lines.append("")
    lines.append(f"> {brief['disclaimer']}")
    lines.append("")
    lines.append(f"**Profile:** `{brief['profile_id']}`  ")
    g = brief["goal"]
    lines.append(
        f"**Goal:** {g.get('primary')} · target ${g.get('target_monthly_passive_usd', 0):,.0f}/mo "
        f"in {g.get('deadline_months')} months"
    )
    lines.append("")
    if brief.get("debt_gate_active"):
        lines.append(f"**Debt gate:** {brief.get('debt_gate_message')}")
        lines.append("")

    lines.append("## Methods compared")
    for m in brief.get("methods_compared") or []:
        lines.append(f"- **{m['id']} — {m['name']}** ({m['verdict']}): {m['note']}")
    lines.append("")

    if not brief.get("options"):
        lines.append("## No qualified streams")
        lines.append("Every stream was disqualified. Relax maintenance hours, capital, or exclusions and re-run.")
        return "\n".join(lines)

    lines.append("## Options")
    for o in brief["options"]:
        stale = " · **STALE catalog yield — verify**" if o.get("stale") else ""
        lines.append(f"### {o['role_label']}: {o['name']} (`{o['stream_id']}`){stale}")
        lines.append(
            f"- Fit **{o['fit_score']}** · RAS **{o['ras']}** · Passivity **{o['passivity_index']}** ({o['passivity_label']})"
        )
        lines.append(
            f"- Category `{o['category']}` · Suggested capital ~${o.get('capital_suggested_usd') or 0:,.0f}"
        )
        ttf = o.get("time_to_first_dollar_days") or {}
        lines.append(
            f"- Time to first dollar (days): bear {ttf.get('bear')} / base {ttf.get('base')} / bull {ttf.get('bull')}"
        )
        y = o.get("yield") or {}
        lines.append(
            f"- Yield ({y.get('unit')}, as of {y.get('as_of')}): "
            f"{y.get('bear')} / {y.get('base')} / {y.get('bull')}"
        )
        if o.get("explain"):
            explain = o["explain"]
            why = "; ".join(explain) if isinstance(explain, list) else str(explain)
            lines.append(f"- Why: {why}")
        if o.get("week1_actions"):
            lines.append("- First moves:")
            for a in o["week1_actions"]:
                lines.append(f"  - {a}")
        if o.get("kill_criteria"):
            lines.append("- Kill if:")
            for k in o["kill_criteria"]:
                lines.append(f"  - {k}")
        lines.append("")

    lines.append("## 7-day plan (start with Recommended)")
    for step in brief.get("seven_day_plan") or []:
        lines.append(f"- {step}")
    lines.append("")

    cf = brief.get("catalog_freshness") or {}
    lines.append("## Catalog freshness")
    lines.append(
        f"- Catalog stale: **{cf.get('catalog_stale_count')}** / {cf.get('catalog_total')} streams"
    )
    if cf.get("stale_in_options"):
        lines.append(f"- Stale among options: {', '.join(cf['stale_in_options'])}")
    lines.append("")

    lines.append("## Stack notes")
    for n in brief.get("stack_notes") or []:
        lines.append(f"- {n}")
    lines.append("")
    ps = brief.get("portfolio_summary") or {}
    lines.append(
        f"_Engine portfolio deploy ~${ps.get('total_deployed', 0):,.0f} across "
        f"{ps.get('allocation_count', 0)} line items (phases {ps.get('phase_summary')})._"
    )
    return "\n".join(lines)
