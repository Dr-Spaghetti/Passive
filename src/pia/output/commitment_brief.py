"""Commitment Brief v2 — single Start + Support + Kill, feasibility, stack 7-day plan.

Educational planning only — not financial advice.

Maximize posture (default): ``target_monthly_passive_usd`` / deadline are stretch
scoreboard / gap reporting only — they must not demote or exclude Start/Support/Kill.

Teaching toggle mechanism
-------------------------
When ``teaching_intent=True``, we append domain_expertise tag ``teaching`` (and a
stack note) so ``profile_indicates_teaching`` / ``score_stack_match(teaching_goal=…)``
lift the hard-demote on GENERIC_DIGITAL_SPAM (online_course, KDP, printables, etc.).
Default remains buried unless the user opts in via the UI checkbox / API flag.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from pia.engine.portfolio import surplus_guidance
from pia.engine.scorer import LANE_EXEMPLAR_STREAMS, GENERIC_DIGITAL_SPAM, rank_streams
from pia.output.decision_brief import _option_payload, select_options
from pia.schemas.profile import Profile
from pia.schemas.stream import ScoredStream, Stream

DISCLAIMER = (
    "Educational planning only — not financial, legal, or tax advice. "
    "Verify current yields and requirements before allocating capital or time."
)

PREFERRED_START_IDS = (
    "micro_saas",
    "affiliate_niche_site",
    "white_label_saas",
    "stock_video",
)

ALL_EXEMPLARS = {sid for ids in LANE_EXEMPLAR_STREAMS.values() for sid in ids}


def apply_teaching_intent(profile: Profile, teaching_intent: bool) -> Profile:
    """Return a profile copy with teaching markers when toggle is on.

    Mechanism: append domain_expertise ``teaching`` (matches TEACHING_INTENT_KEYWORDS
    substring ``teach``) plus a stack note so scorer's ``profile_indicates_teaching``
    returns True and hard-demote is lifted.
    """
    if not teaching_intent:
        return profile
    data = profile.model_dump()
    expertise = list(data.get("skills", {}).get("domain_expertise") or [])
    if "teaching" not in [e.lower() for e in expertise]:
        expertise.append("teaching")
    data["skills"]["domain_expertise"] = expertise
    stack = data.get("stack") or {}
    notes = list(stack.get("notes") or [])
    marker = "teaching_intent=True (user opted into courses/KDP/printables)"
    if marker not in notes:
        notes.append(marker)
    stack["notes"] = notes
    data["stack"] = stack
    return Profile(**data)


def _is_start_eligible(scored: ScoredStream) -> bool:
    if scored.disqualified:
        return False
    if "unreachable_capital" in scored.reachability_flags:
        return False
    if scored.debt_gate_demoted and scored.stream.category in {
        "real_asset",
        "local_physical",
        "credit_alt",
        "paper",
    }:
        # Debt gate: Start must be skill/time experiment (low capital digital/attention)
        return False
    return True


def _start_key(r: ScoredStream, *, maximize: bool = True) -> tuple:
    lane_note = " ".join(r.stack_match_notes).lower()
    preferred = 1 if r.stream.stream_id in PREFERRED_START_IDS else 0
    exemplar = 1 if "exemplar" in lane_note or r.stream.stream_id in ALL_EXEMPLARS else 0
    spam = 1 if (
        "hard-demoted" in lane_note
        or r.stream.stream_id in GENERIC_DIGITAL_SPAM
    ) else 0
    # Prefer low-capital when debt gate demoted anything capital-heavy
    low_cap = 1 if (r.stream.capital_usd.min or 0) <= 200 else 0
    ceiling_rank = 1 if maximize else (0 if r.low_ceiling else 1)
    return (
        0 if r.debt_gate_demoted else 1,
        ceiling_rank,
        0 if spam else 1,
        preferred,
        exemplar,
        low_cap,
        r.stack_match_score,
        r.ras,
        r.fit_score,
    )


def pick_commitment(
    ranked: list[ScoredStream],
    *,
    debt_gate_active: bool,
    maximize: bool = True,
) -> dict[str, Any]:
    """Pick exactly 1 Start (or none) + up to 2 Support from ranked streams.

    Under maximize (default), low_ceiling must not demote Start or exclude Support.
    """
    qualified = [r for r in ranked if _is_start_eligible(r)]
    if not qualified:
        qualified = [r for r in ranked if not r.disqualified]

    start: ScoredStream | None = None
    support: list[ScoredStream] = []

    def key(r: ScoredStream) -> tuple:
        return _start_key(r, maximize=maximize)

    if debt_gate_active:
        # Prefer skill/time digital experiments under debt
        skillish = [
            r for r in qualified
            if r.stream.category in {"digital", "attention"}
            and (r.stream.capital_usd.min or 0) <= 500
            and not r.debt_gate_demoted
        ]
        pool = skillish or [
            r for r in qualified
            if (r.stream.capital_usd.min or 0) <= 500 and not r.debt_gate_demoted
        ] or qualified
    else:
        pool = qualified

    if pool:
        start = max(pool, key=key)

    if start is not None:
        rest = [r for r in qualified if r.stream.stream_id != start.stream.stream_id]
        # Prefer different category / non-spam for Support
        ranked_rest = sorted(rest, key=key, reverse=True)
        for r in ranked_rest:
            if len(support) >= 2:
                break
            note = " ".join(r.stack_match_notes).lower()
            if "hard-demoted" in note and r.stream.stream_id in GENERIC_DIGITAL_SPAM:
                continue
            # Legacy only: skip low-ceiling fillers unless exemplar/preferred
            if (
                not maximize
                and r.low_ceiling
                and "exemplar" not in note
                and r.stream.stream_id not in PREFERRED_START_IDS
            ):
                continue
            support.append(r)

    return {"start": start, "support": support}


def _monthly_yield_at_steady(scored: ScoredStream, deployable: float) -> dict[str, float]:
    """Illustrative monthly USD from yield unit — no compound magic."""
    y = scored.stream.yield_
    unit = (y.unit or "").lower()
    if unit in {"monthly_usd_at_typical", "monthly_usd"}:
        return {"bear": float(y.bear), "base": float(y.base), "bull": float(y.bull)}
    if unit in {"annual_pct_on_capital", "annual_pct"}:
        # Paper/yield %: deployable * rate / 12
        cap = max(0.0, deployable)
        return {
            "bear": cap * float(y.bear) / 100.0 / 12.0,
            "base": cap * float(y.base) / 100.0 / 12.0,
            "bull": cap * float(y.bull) / 100.0 / 12.0,
        }
    # Unknown unit — treat as monthly USD cautiously
    return {"bear": float(y.bear), "base": float(y.base), "bull": float(y.bull)}


def build_feasibility(
    profile: Profile,
    start: ScoredStream | None,
) -> dict[str, Any]:
    target = float(profile.financial.target_monthly_passive_usd or 0)
    deadline = int(profile.financial.target_deadline_months or 0)
    deployable = float(profile.deployable_capital or 0)
    surplus = float(profile.monthly_surplus_point or 0)

    maximize = bool(profile.maximize_executable_upside)
    if start is None:
        return {
            "target_monthly": target,
            "deadline_months": deadline,
            "deployable_usd": deployable,
            "surplus_midpoint_usd": surplus,
            "projected_base_at_deadline": 0.0,
            "projected_bear_at_deadline": 0.0,
            "pct_of_target_base": 0.0,
            "status": "stretch_gap" if maximize else "unreachable",
            "scoreboard_only": maximize,
            "note": (
                "No Start selected under current real constraints (often debt/capital block). "
                "Stretch scoreboard gap only — does not change playbook. "
                "Illustrative educational planning, not a forecast or strategy verdict."
            ),
        }

    yields = _monthly_yield_at_steady(start, deployable)
    ttf_days = float(start.stream.time_to_first_dollar_days.base or 0)
    ttf_months = ttf_days / 30.0
    # Steady-state monthly after time_to_first_dollar; if deadline < ttf, project 0
    if deadline <= 0:
        projected_base = 0.0
        projected_bear = 0.0
    elif deadline < ttf_months:
        # Not yet at steady state by deadline — fraction of ramp (linear illustrative)
        frac = max(0.0, deadline / max(ttf_months, 1e-6))
        projected_base = yields["base"] * frac * 0.25  # early ramp haircut
        projected_bear = yields["bear"] * frac * 0.25
    else:
        projected_base = yields["base"]
        projected_bear = yields["bear"]

    pct = (projected_base / target * 100.0) if target > 0 else 0.0
    if pct >= 80:
        status = "on_track"
    elif pct >= 25:
        status = "stretch"
    else:
        # Maximize: large gap is stretch/gap pressure on the scoreboard, not a playbook verdict.
        status = "stretch_gap" if maximize else "unreachable"

    unit = start.stream.yield_.unit
    note = (
        f"Illustrative stretch-scoreboard gap only (not a forecast or strategy verdict): "
        f"treating `{start.stream.stream_id}` yield unit `{unit}` as steady monthly after "
        f"~{ttf_days:.0f}d to first dollar, under deployable ${deployable:,.0f} + surplus "
        f"midpoint ${surplus:,.0f}/mo. No compounding assumed. "
        "target_monthly / deadline do not change Start/Support/Kill under maximize mode. "
        "Educational planning only."
        if maximize
        else (
            f"Illustrative only (not a forecast): treating `{start.stream.stream_id}` "
            f"yield unit `{unit}` as steady monthly after ~{ttf_days:.0f}d to first dollar, "
            f"under deployable ${deployable:,.0f} + surplus midpoint ${surplus:,.0f}/mo. "
            "No compounding assumed. Educational planning only."
        )
    )
    return {
        "target_monthly": target,
        "deadline_months": deadline,
        "deployable_usd": deployable,
        "surplus_midpoint_usd": surplus,
        "start_stream_id": start.stream.stream_id,
        "yield_unit": unit,
        "steady_monthly_bear": yields["bear"],
        "steady_monthly_base": yields["base"],
        "steady_monthly_bull": yields["bull"],
        "projected_base_at_deadline": round(projected_base, 2),
        "projected_bear_at_deadline": round(projected_bear, 2),
        "pct_of_target_base": round(pct, 1),
        "status": status,
        "scoreboard_only": maximize,
        "note": note,
    }


def _stack_tag_list(profile: Profile) -> list[str]:
    return sorted(profile.stack_tags())


def build_first_7_days(profile: Profile, start: ScoredStream | None) -> list[str]:
    if start is None:
        return [
            "No Start this month — clear debt/capital block first (see debt_plan).",
            "Log surplus allocation toward debt (≥60%) and emergency buffer (~30%).",
            "Keep ≤10% for skill experiments only after paydown plan is set.",
            "Re-run brief after updating liquid capital or debt balance.",
            "Talk to CoS with updated money fields only from you — never invent.",
        ]

    sid = start.stream.stream_id
    tags = _stack_tag_list(profile)
    tag_snip = ", ".join(tags[:6]) if tags else "your skills"

    if sid in {"micro_saas", "white_label_saas"}:
        return [
            f"Day 1: Pick ONE JL-adjacent pain (citation audit / GBP health / local SEO maps gap) using stack tags: {tag_snip}.",
            "Day 2: Write a one-sentence offer + who pays $29–99/mo (law firm ops / local biz owner).",
            "Day 3: Scaffold MVP on Vercel (Dr-Spaghetti shipping stack) — auth + one report endpoint.",
            "Day 4: Seed with synthetic/demo GBP or citation data; ship a shareable preview URL.",
            "Day 5: Define 'one paying user' success: invoice or Stripe test + real feedback call.",
            "Day 6: Outreach to 5 warm JL-adjacent contacts (no company SaaS as your capital).",
            "Day 7: Kill or keep — if no conversation booked, narrow pain and re-ship; log hours in pia tracker.",
        ]
    if sid == "affiliate_niche_site":
        return [
            f"Day 1: Choose ONE JL keyword cluster (GBP audit, citation build, local SEO checklist) from tags: {tag_snip}.",
            "Day 2: Register one site / subdomain; set up analytics + Search Console.",
            "Day 3: Outline 5 pillar pages angled at BrightLocal/GBP buyer intent (educational, not scraping WORK tools).",
            "Day 4: Write & publish page 1 with affiliate-safe disclosures.",
            "Day 5: Internal link + simple lead magnet (checklist PDF).",
            "Day 6: Submit to index; pitch 2 partner newsletters in local SEO niche.",
            "Day 7: Review impressions plan; kill cluster if no searchable angle — log time only.",
        ]
    if sid in {"stock_video", "ai_art_stock"}:
        return [
            f"Day 1: Confirm Insta360/pano capture batch plan using stack: {tag_snip}.",
            "Day 2: Shoot or export 20–40 clips (exteriors, GBP-style storefronts, pano stills) — personal_use_ok only.",
            "Day 3: Keyword + category metadata spreadsheet for Pond5 / Shutterstock.",
            "Day 4: Upload first batch; verify model/property releases where needed.",
            "Day 5: Upload second batch; A/B titles for local-business / travel 360 queries.",
            "Day 6: Set weekly capture cadence (2 hrs) — debt-safe time box, not new gear spend.",
            "Day 7: Review rejects; kill low-demand tags; log hours in pia tracker.",
        ]

    # Default: rewrite first checklist item to cite stack tags
    checklist = list(start.stream.startup_checklist or [])[:5]
    actions: list[str] = []
    if checklist:
        actions.append(
            f"Day 1 (stack-aware): {checklist[0]} — anchor to your stack tags: {tag_snip}."
        )
        for i, step in enumerate(checklist[1:], start=2):
            actions.append(f"Day {i}: {step}")
    while len(actions) < 5:
        n = len(actions) + 1
        actions.append(f"Day {n}: Execute next startup checklist item for `{sid}`; log time/money.")
    actions.append("End of week: pia log + decide keep / swap Support / re-brief with CoS.")
    return actions[:7]


def build_kill_summary(
    ranked: list[ScoredStream],
    start: ScoredStream | None,
    support: list[ScoredStream],
    *,
    maximize: bool = True,
) -> list[str]:
    keep = {s.stream.stream_id for s in support}
    if start is not None:
        keep.add(start.stream.stream_id)

    groups: dict[str, list[str]] = {
        "capital_block": [],
        "debt_inappropriate": [],
        "hard_demoted_generic": [],
        "low_ceiling": [],
        "disqualified": [],
        "not_now": [],
    }
    for r in ranked:
        sid = r.stream.stream_id
        if sid in keep:
            continue
        name = r.stream.name
        label = f"{name} (`{sid}`)"
        notes = " ".join(r.stack_match_notes).lower()
        if r.disqualified or r.unreachable_capital:
            reason = (r.disqualify_reason or "capital/constraint DQ")[:80]
            groups["capital_block" if r.unreachable_capital else "disqualified"].append(
                f"{label}: {reason}"
            )
        elif r.debt_gate_demoted:
            groups["debt_inappropriate"].append(f"{label}: debt-gate demoted")
        elif "hard-demoted" in notes or sid in GENERIC_DIGITAL_SPAM:
            groups["hard_demoted_generic"].append(
                f"{label}: generic digital spam (enable teaching toggle to reconsider)"
            )
        elif r.low_ceiling and not maximize:
            # Legacy only: dollar-target kill. Under maximize, low_ceiling is not a Kill reason.
            groups["low_ceiling"].append(f"{label}: low ceiling vs target")
        else:
            groups["not_now"].append(f"{label}: not selected this month")

    lines: list[str] = []
    titles = {
        "capital_block": "Capital DQ",
        "disqualified": "Disqualified",
        "debt_inappropriate": "Debt-inappropriate",
        "hard_demoted_generic": "Hard-demoted generics",
        "low_ceiling": "Low ceiling",
        "not_now": "Not now",
    }
    for key, title in titles.items():
        items = groups[key][:6]
        if not items:
            continue
        # One-liners, not a table
        for item in items[:3]:
            lines.append(f"{title}: {item}")
        extra = len(groups[key]) - 3
        if extra > 0:
            lines.append(f"{title}: +{extra} more")
    return lines[:18]


def build_debt_plan(profile: Profile, start: ScoredStream | None) -> dict[str, Any] | None:
    if not profile.has_debt_gate:
        return None
    surplus = float(profile.monthly_surplus_point or 0)
    debt = float(profile.financial.high_interest_debt_usd or 0)
    debt_share = round(surplus * 0.60, 2)
    buffer_share = round(surplus * 0.30, 2)
    explore_share = round(surplus * 0.10, 2)
    start_note = (
        f"Start (`{start.stream.stream_id}`) is a time-box skill experiment — not a capital deployment."
        if start is not None
        else "No Start — debt/capital block; focus surplus on paydown before new experiments."
    )
    return {
        "active": True,
        "high_interest_debt_usd": debt,
        "surplus_midpoint_usd": surplus,
        "split": {
            "debt_paydown_pct": 60,
            "debt_paydown_usd": debt_share,
            "emergency_buffer_pct": 30,
            "emergency_buffer_usd": buffer_share,
            "risky_experiments_pct": 10,
            "risky_experiments_usd": explore_share,
        },
        "guidance": surplus_guidance(profile),
        "start_is_time_box_only": True,
        "note": start_note + " Educational only — not financial advice.",
    }


def build_commitment_brief(
    profile: Profile,
    streams: list[Stream],
    *,
    teaching_intent: bool = False,
) -> dict[str, Any]:
    """Build Commitment Brief v2 dict with nested ``commitment`` block."""
    working = apply_teaching_intent(profile, teaching_intent)
    ranked = rank_streams(working, streams)
    debt_gate_active = working.has_debt_gate
    maximize = bool(working.maximize_executable_upside)
    picks = pick_commitment(
        ranked, debt_gate_active=debt_gate_active, maximize=maximize
    )

    # Fallback: if pick_commitment found nothing, reuse CoS select_options primary
    if picks["start"] is None:
        legacy = select_options(ranked, maximize=maximize)
        picks["start"] = legacy.get("primary")
        support = []
        for key in ("alt_a", "alt_b"):
            alt = legacy.get(key)
            if alt is not None:
                support.append(alt)
        picks["support"] = support[:2]

    start = picks["start"]
    support = picks["support"]

    # Explicit no-Start when debt + no skillish reachable
    no_start_reason = None
    if start is None and debt_gate_active:
        no_start_reason = (
            "no Start — debt/capital block: prioritize ≥60% surplus to high-interest debt; "
            "re-brief after paydown or when a $0-min skill experiment clears the gate."
        )

    start_payload = None
    if start is not None:
        start_payload = _option_payload(start)
        start_payload["role"] = "start"
        start_payload["role_label"] = "Start this month"

    support_payload = []
    for s in support:
        p = _option_payload(s)
        p["role"] = "support"
        p["role_label"] = "Support (parked — don't start yet)"
        support_payload.append(p)

    feasibility = build_feasibility(working, start)
    first_7 = build_first_7_days(working, start)
    kill_summary = build_kill_summary(ranked, start, support, maximize=maximize)
    debt_plan = build_debt_plan(working, start)

    commitment = {
        "start": start_payload,
        "support": support_payload,
        "kill_summary": kill_summary,
        "feasibility": feasibility,
        "first_7_days": first_7,
        "debt_plan": debt_plan,
        "teaching_intent": bool(teaching_intent),
        "no_start_reason": no_start_reason,
        "maximize_executable_upside": maximize,
    }

    return {
        "disclaimer": DISCLAIMER,
        "profile_id": working.profile_id,
        "maximize_executable_upside": maximize,
        "goal": {
            "primary": working.goals.primary,
            "target_monthly_passive_usd": working.financial.target_monthly_passive_usd,
            "deadline_months": working.financial.target_deadline_months,
            "role": "stretch_scoreboard",
            "note": (
                "Optional stretch scoreboard / gap reporting only — does not change "
                "ranking or Start/Support/Kill under maximize mode."
                if maximize
                else "Legacy: dollar target may soft-penalize low-ceiling streams."
            ),
        },
        "debt_gate_active": debt_gate_active,
        "surplus_allocation_guidance": surplus_guidance(working) if debt_gate_active else "",
        "teaching_intent": bool(teaching_intent),
        "teaching_intent_mechanism": (
            "Appends domain_expertise 'teaching' so scorer profile_indicates_teaching "
            "lifts GENERIC_DIGITAL_SPAM hard-demote."
        ),
        "commitment": commitment,
        # Convenience mirrors for UI
        "start": start_payload,
        "support": support_payload,
        "kill_summary": kill_summary,
        "feasibility": feasibility,
        "first_7_days": first_7,
        "debt_plan": debt_plan,
    }


def render_commitment_markdown(brief: dict[str, Any]) -> str:
    """Markdown for CLI / export: Start, Support, Kill, feasibility, 7-day plan."""
    lines: list[str] = []
    lines.append("# Passive income commitment brief")
    lines.append("")
    lines.append(f"> {brief.get('disclaimer', DISCLAIMER)}")
    lines.append("")
    lines.append(f"**Profile:** `{brief.get('profile_id')}`  ")
    g = brief.get("goal") or {}
    maximize = brief.get("maximize_executable_upside", True)
    lines.append(
        f"**Goal (stretch scoreboard):** {g.get('primary')} · "
        f"${g.get('target_monthly_passive_usd', 0):,.0f}/mo in {g.get('deadline_months')} months"
        + (" · maximize mode ON" if maximize else " · maximize OFF")
    )
    if g.get("note"):
        lines.append(f"_{g['note']}_")
    lines.append("")
    if brief.get("debt_gate_active"):
        lines.append(f"**Debt gate:** active")
        if brief.get("surplus_allocation_guidance"):
            lines.append(f"**Surplus guidance:** {brief['surplus_allocation_guidance']}")
        lines.append("")

    c = brief.get("commitment") or brief
    start = c.get("start")
    lines.append("## Start")
    lines.append("")
    if start:
        lines.append(
            f"**{start.get('name')}** (`{start.get('stream_id')}`) — "
            f"fit {start.get('fit_score')}, RAS {start.get('ras')}, "
            f"stack {start.get('stack_match_score')}"
        )
        why = start.get("why_fit") or ""
        if why:
            lines.append(f"- {why}")
    else:
        reason = c.get("no_start_reason") or "No Start under current constraints."
        lines.append(f"_{reason}_")
    lines.append("")

    lines.append("## Support")
    lines.append("")
    support = c.get("support") or []
    if not support:
        lines.append("_None parked this month._")
    else:
        for s in support:
            lines.append(
                f"- **{s.get('name')}** (`{s.get('stream_id')}`) — "
                f"fit {s.get('fit_score')}, RAS {s.get('ras')}"
            )
    lines.append("")

    lines.append("## Kill / not now")
    lines.append("")
    for item in c.get("kill_summary") or []:
        lines.append(f"- {item}")
    if not c.get("kill_summary"):
        lines.append("_No kill lines._")
    lines.append("")

    feas = c.get("feasibility") or {}
    lines.append("## Feasibility (illustrative gap / scoreboard)")
    lines.append("")
    lines.append(
        f"- Status: **{feas.get('status')}** · "
        f"{feas.get('pct_of_target_base', 0)}% of stretch target "
        f"(${feas.get('target_monthly', 0):,.0f}/mo by {feas.get('deadline_months')} mo)"
    )
    lines.append(
        f"- Projected base at deadline (illustrative): "
        f"${feas.get('projected_base_at_deadline', 0):,.0f}"
    )
    if feas.get("note"):
        lines.append(f"- Note: {feas['note']}")
    lines.append("")

    lines.append("## First 7 days")
    lines.append("")
    for step in c.get("first_7_days") or []:
        lines.append(f"- {step}")
    lines.append("")
    lines.append("_Educational planning only — not financial advice._")
    lines.append("")
    return "\n".join(lines)
