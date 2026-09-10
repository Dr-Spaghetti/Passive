from __future__ import annotations

from typing import Any

from pia.engine.portfolio import build_portfolio, surplus_guidance
from pia.engine.scorer import rank_streams
from pia.schemas.profile import Profile
from pia.schemas.stream import ScoredStream, Stream

DISCLAIMER = (
    "Educational planning only — not financial, legal, or tax advice. "
    "Verify current yields and requirements before allocating capital or time."
)

# What CoS needs to call pia brief / re-brief / track
COS_CONTRACT = {
    "loop": [
        "1. Confirm/update Profile JSON (money fields only from Nick — never invent).",
        "2. Optional: merge stack inventory via `pia brief --profile … --inventory …`.",
        "3. Run `pia brief --profile PATH` or POST /api/brief with {\"profile\": {...}}.",
        "4. Present winner + 2 alts with stack why-copy; execute monthly.",
        "5. Log reality: `pia log <stream_id>` or POST /api/tracker.",
        "6. Persist plan: POST /api/plan or `pia plan set`; weekly `pia drift` / POST /api/drift.",
        "7. On drift or goal change → re-brief (same profile path).",
    ],
    "endpoints": {
        "brief_cli": "pia brief --profile PATH [--inventory PATH] [--json]",
        "brief_api": "POST /api/brief",
        "tracker_api": "GET|POST /api/tracker",
        "plan_api": "POST /api/plan , GET /api/plan/{stream_id}",
        "drift_api": "POST /api/drift",
        "drift_cli": "pia drift <stream_id> [--plan-net N --plan-hours N]",
    },
    "rules": [
        "WORK-lane SaaS/gear is NOT personal capital unless personal_use_ok.",
        "Debt gate active → surplus guidance + risky allocation cap; do not push capital-heavy alts.",
        "Educational only — no financial advice claims.",
    ],
}


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
        "unreachable_capital": scored.unreachable_capital,
        "missing_prereq": scored.missing_prereq,
        "low_ceiling": scored.low_ceiling,
        "debt_gate_demoted": scored.debt_gate_demoted,
        "stack_match_score": scored.stack_match_score,
        "stack_match_notes": scored.stack_match_notes,
        "reachability_flags": scored.reachability_flags,
    }


def _is_brief_eligible(scored: ScoredStream) -> bool:
    if scored.disqualified:
        return False
    if "unreachable_capital" in scored.reachability_flags:
        return False
    return True


def select_options(ranked: list[ScoredStream]) -> dict[str, ScoredStream | None]:
    """Pick primary + up to two alternatives; prefer reachable + stack-fit; skip weak fillers."""
    qualified = [r for r in ranked if _is_brief_eligible(r)]
    if not qualified:
        # Fall back to any non-DQ so brief is not empty, but mark later
        qualified = [r for r in ranked if not r.disqualified]

    if not qualified:
        return {"primary": None, "alt_a": None, "alt_b": None}

    def option_key(r: ScoredStream) -> tuple:
        # Prefer stack-lane exemplars (SEO / 360 / software) over generic high-RAS courses
        lane_note = " ".join(r.stack_match_notes).lower()
        exemplar = 1 if "exemplar" in lane_note else 0
        generic_course_penalty = 1 if r.stream.stream_id == "online_course" and "soft-penalized" in lane_note else 0
        return (
            0 if r.low_ceiling else 1,
            0 if r.debt_gate_demoted else 1,
            0 if generic_course_penalty else 1,
            exemplar,
            r.stack_match_score,
            r.ras,
            r.fit_score,
        )

    passive_ok = [r for r in qualified if r.stream.passivity_index >= 6]
    pool = passive_ok or qualified
    primary = max(pool, key=option_key)

    rest = [r for r in qualified if r.stream.stream_id != primary.stream.stream_id]
    # Prefer different category for alt_a
    def _allow_as_alt(r: ScoredStream) -> bool:
        if not r.low_ceiling:
            return True
        # Keep stack exemplars visible even if catalog base yield is modest
        return "exemplar" in " ".join(r.stack_match_notes).lower()

    alt_a = None
    for r in sorted(rest, key=option_key, reverse=True):
        if r.stream.category != primary.stream.category and _allow_as_alt(r):
            alt_a = r
            break
    if alt_a is None:
        candidates = [r for r in rest if _allow_as_alt(r)] or rest
        if candidates:
            alt_a = max(candidates, key=option_key)

    used = {primary.stream.stream_id}
    if alt_a:
        used.add(alt_a.stream.stream_id)
    remaining = [r for r in qualified if r.stream.stream_id not in used]
    # Third option: prefer stack match over pure fit; avoid low-ceiling fillers when possible
    remaining_strong = [r for r in remaining if not r.low_ceiling] or remaining
    alt_b = max(remaining_strong, key=option_key) if remaining_strong else None

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


def _methods_on_stack(
    profile: Profile,
    picks: dict[str, ScoredStream | None],
    ranked: list[ScoredStream],
) -> list[dict[str, Any]]:
    """Compare income methods using this profile's stack — not static UX A/B/C."""
    methods: list[dict[str, Any]] = []
    labels = {
        "primary": "winner",
        "alt_a": "strong_alternative",
        "alt_b": "third_option",
    }
    for key, verdict in labels.items():
        scored = picks.get(key)
        if scored is None:
            continue
        stack_note = "; ".join(scored.stack_match_notes[:2]) if scored.stack_match_notes else "generic skill fit"
        fail_notes = []
        if scored.debt_gate_demoted:
            fail_notes.append("debt gate demotion")
        if scored.low_ceiling:
            fail_notes.append("low yield ceiling vs target")
        if scored.unreachable_capital:
            fail_notes.append("thin capital vs typical")
        methods.append(
            {
                "id": scored.stream.stream_id,
                "name": scored.stream.name,
                "verdict": verdict,
                "note": (
                    f"Stack: {stack_note}. Fit {scored.fit_score}, RAS {scored.ras}, "
                    f"passivity {scored.stream.passivity_index}."
                    + (f" Caveats: {', '.join(fail_notes)}." if fail_notes else "")
                ),
                "stack_match_score": scored.stack_match_score,
            }
        )

    # Surface top disqualified / failed constraints for CoS transparency
    dq = [r for r in ranked if r.disqualified][:5]
    for r in dq:
        methods.append(
            {
                "id": r.stream.stream_id,
                "name": r.stream.name,
                "verdict": "disqualified",
                "note": r.disqualify_reason or "Disqualified by constraints",
                "stack_match_score": r.stack_match_score,
            }
        )
    return methods


def _default_stack_notes(profile: Profile) -> list[str]:
    notes = [
        "CoS is the front door: state goals/outputs; CoS compares methods across your stack.",
        "pia remains the scoring/projection engine (fit, RAS, disqualify, portfolio).",
        "WORK-lane company SaaS/gear is not personal capital unless personal_use_ok is confirmed.",
    ]
    deployable = profile.deployable_stack_assets()
    if deployable:
        by_lane: dict[str, list[str]] = {}
        for a in deployable:
            by_lane.setdefault(a.lane, []).append(a.name)
        for lane, names in sorted(by_lane.items()):
            notes.append(f"Stack ({lane}): {', '.join(names[:8])}")
    elif profile.skills.domain_expertise:
        notes.append(
            "Domain expertise: " + ", ".join(profile.skills.domain_expertise[:8])
        )
    else:
        notes.append(
            "No stack inventory merged — pass `--inventory` or set profile.stack for sharper rankings."
        )
    if profile.stack.notes:
        notes.extend(profile.stack.notes[:3])
    return notes


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
    week_actions.append(
        "End of week: log any time/money spent (`pia log <stream_id>` or POST /api/tracker)."
    )
    week_actions.append(
        "Set plan baselines (`pia plan set` / POST /api/plan), then weekly drift check."
    )
    week_actions.append("Talk to CoS with results — keep, swap to an alt, or re-brief.")

    stale_flags = [o["stream_id"] for o in options if o.get("stale")]
    freshness = catalog_freshness_report(streams)
    disqualified = [
        {
            "stream_id": r.stream.stream_id,
            "name": r.stream.name,
            "reason": r.disqualify_reason,
            "reachability_flags": r.reachability_flags,
        }
        for r in ranked
        if r.disqualified
    ]

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
        "surplus_allocation_guidance": alloc.surplus_allocation_guidance or surplus_guidance(profile),
        "options": options,
        "disqualified_sample": disqualified[:8],
        "portfolio_summary": {
            "total_deployed": alloc.total_deployed,
            "phase_summary": alloc.phase_summary,
            "allocation_count": len(alloc.allocations),
            "max_risky_allocation_pct": alloc.max_risky_allocation_pct,
        },
        "seven_day_plan": week_actions,
        "catalog_freshness": {
            "stale_in_options": stale_flags,
            "catalog_stale_count": freshness["stale_count"],
            "catalog_total": freshness["total"],
        },
        "stack_notes": stack_notes or _default_stack_notes(profile),
        "methods_compared": _methods_on_stack(profile, picks, ranked),
        "cos_contract": COS_CONTRACT,
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
    if brief.get("surplus_allocation_guidance"):
        lines.append(f"**Surplus guidance:** {brief['surplus_allocation_guidance']}")
        lines.append("")

    lines.append("## Methods compared (on your stack)")
    for m in brief.get("methods_compared") or []:
        lines.append(f"- **{m['id']} — {m['name']}** ({m['verdict']}): {m['note']}")
    lines.append("")

    if not brief.get("options"):
        lines.append("## No qualified streams")
        lines.append(
            "Every stream was disqualified. Relax maintenance hours, capital, or exclusions and re-run."
        )
        if brief.get("disqualified_sample"):
            lines.append("")
            lines.append("### Why methods failed constraints")
            for d in brief["disqualified_sample"]:
                lines.append(f"- `{d['stream_id']}`: {d['reason']}")
        return "\n".join(lines)

    lines.append("## Options")
    for o in brief["options"]:
        stale = " · **STALE catalog yield — verify**" if o.get("stale") else ""
        flags = o.get("reachability_flags") or []
        flag_txt = f" · flags: {', '.join(flags)}" if flags else ""
        lines.append(f"### {o['role_label']}: {o['name']} (`{o['stream_id']}`){stale}")
        lines.append(
            f"- Fit **{o['fit_score']}** · RAS **{o['ras']}** · Passivity **{o['passivity_index']}** "
            f"({o['passivity_label']}) · Stack match **{o.get('stack_match_score', 0)}**{flag_txt}"
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

    if brief.get("disqualified_sample"):
        lines.append("## Why other methods fail your constraints")
        for d in brief["disqualified_sample"][:6]:
            lines.append(f"- `{d['stream_id']}` ({d['name']}): {d['reason']}")
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

    lines.append("## CoS loop (re-brief contract)")
    for step in (brief.get("cos_contract") or {}).get("loop") or []:
        lines.append(f"- {step}")
    lines.append("")

    ps = brief.get("portfolio_summary") or {}
    lines.append(
        f"_Engine portfolio deploy ~${ps.get('total_deployed', 0):,.0f} across "
        f"{ps.get('allocation_count', 0)} line items (phases {ps.get('phase_summary')}; "
        f"risky cap {ps.get('max_risky_allocation_pct')}%)._"
    )
    return "\n".join(lines)
