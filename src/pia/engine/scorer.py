from __future__ import annotations
import math
import re
from pia.schemas.stream import Stream


def score_capital_fit(capital: float, stream: Stream) -> float:
    L = stream.capital_usd.min
    T = stream.capital_usd.typical
    S = stream.capital_usd.scale_tiers[-1] if stream.capital_usd.scale_tiers else T * 10

    if capital < L:
        return 100 * (capital / max(L, 1)) * 0.5
    if capital <= T:
        return 70 + 30 * (capital - L) / max(T - L, 1)
    if capital <= S:
        return 100.0
    return 90.0


def score_maintenance_fit(
    monthly_hours_budget: float,
    stream: Stream,
    return_disqualify: bool = False,
):
    hs = stream.maintenance_hours_per_month.steady
    hu = max(monthly_hours_budget, 0.1)
    disqualified = hs > hu * 1.15
    # Penalize streams that consume >50% of time budget
    score = max(0.0, min(100.0, 100.0 - 50.0 * max(0.0, (hs / hu) - 0.5)))
    if return_disqualify:
        return disqualified, score
    return score


LIQUIDITY_NEED_PENALTIES = {
    "days":   {"high": 0.0, "med": 15.0, "low": 35.0},
    "months": {"high": 0.0, "med": 5.0,  "low": 15.0},
    "years":  {"high": 0.0, "med": 0.0,  "low": 0.0},
}


def score_risk_alignment(
    user_risk: int,
    user_exclusions: list[str],
    stream: Stream,
    liquidity_need: str = "months",
) -> float:
    for exc in user_exclusions:
        if exc in stream.exclusions_match:
            return 5.0

    max_composite = math.ceil(user_risk / 3.5)
    composite = stream.risk_composite

    if composite <= max_composite:
        base = 100.0
    else:
        overage = composite - max_composite
        base = max(0.0, 100.0 - overage * 35)

    base -= LIQUIDITY_NEED_PENALTIES.get(liquidity_need, {}).get(stream.risk.liquidity, 0.0)

    return max(0.0, min(100.0, base))


def score_skill_leverage(
    user_skills: dict[str, int],
    stream: Stream,
    domain_expertise: list[str] | None = None,
) -> float:
    """Multi-skill coverage + optional domain_expertise boost (not single-max only)."""
    if not stream.skills_leveraged:
        base = 50.0
    else:
        levels = [user_skills.get(k, 0) for k in stream.skills_leveraged]
        best = max(levels) if levels else 0
        mean = sum(levels) / len(levels)
        # Blend max (depth) with mean (coverage) so multi-skill streams reward breadth.
        base = min(100.0, 15 + 7 * best + 3 * mean)

    domain_boost = 0.0
    domains = [d.lower() for d in (domain_expertise or [])]
    if domains:
        haystack = " ".join(
            [
                stream.stream_id,
                stream.name,
                stream.category,
                " ".join(stream.skills_leveraged),
                " ".join(stream.correlation_tags),
                " ".join(stream.tool_stack_examples),
                " ".join(stream.prerequisites),
            ]
        ).lower()
        hits = [d for d in domains if d in haystack or any(tok in haystack for tok in re.split(r"[\s/_-]+", d) if len(tok) > 2)]
        domain_boost = min(20.0, 6.0 * len(hits))
    return min(100.0, base + domain_boost)


def score_goal_alignment(primary_goal: str, stream: Stream) -> float:
    score = 50.0
    tags = stream.correlation_tags
    pi = stream.passivity_index

    if primary_goal == "cash_flow":
        if pi >= 7:
            score += 20
        if stream.yield_.unit == "monthly_usd_at_typical":
            score += 15
        if stream.category == "paper":
            score += 10

    elif primary_goal == "wealth":
        if "equity" in tags or stream.category == "paper":
            score += 25
        if stream.scalability in ("exponential_product", "linear_capital"):
            score += 10

    elif primary_goal == "freedom":
        if pi >= 7:
            score += 25
        if stream.maintenance_hours_per_month.steady <= 2:
            score += 15

    elif primary_goal == "tax_efficiency":
        if "qualified_dividends" in stream.tax_character:
            score += 20
        if "cap_gains" in stream.tax_character:
            score += 10

    return min(100.0, max(0.0, score))


def score_time_to_first_dollar(target_deadline_days: int, stream: Stream) -> float:
    d_base = stream.time_to_first_dollar_days.base
    D = max(90, target_deadline_days / 2)
    return 100.0 * math.exp(-d_base / D)


def score_diversification_value(
    selected_tags: list[str],
    stream: Stream,
) -> float:
    if not stream.correlation_tags:
        return 50.0
    new_tags = set(stream.correlation_tags) - set(selected_tags)
    overlap = set(stream.correlation_tags) & set(selected_tags)
    score = 50.0 + 10 * len(new_tags) - 5 * len(overlap)
    return min(100.0, max(0.0, score))


# Stack keywords that map inventory tags → stream relevance
STACK_KEYWORD_GROUPS: dict[str, list[str]] = {
    # Prefer Nick's real lanes: JL SEO/GBP and 360/pano capture over generic "course" spam
    "seo": ["seo", "gbp", "citation", "brightlocal", "local falcon", "affiliate_niche", "maps audit"],
    "ai": ["ai_ml", "llm", "chatgpt", "anthropic", "runway", "higgsfield"],
    "video_360": ["insta360", "360", "pano", "panorama", "panostitch", "stock_video", "stock video"],
    "software": ["micro_saas", "white_label", "vercel", "saas", "typescript", "python tool"],
    "content": ["newsletter", "kdp", "ebook", "faceless_youtube", "youtube"],
}

# Extra boost when stream_id itself is a lane exemplar
LANE_EXEMPLAR_STREAMS: dict[str, list[str]] = {
    "seo": ["affiliate_niche_site"],
    "video_360": ["stock_video", "ai_art_stock"],
    "software": ["micro_saas", "white_label_saas", "notion_templates"],
    "content": ["faceless_youtube", "paid_newsletter", "amazon_kdp", "ebooks"],
    "ai": ["ai_art_stock", "ai_music_stock", "micro_saas"],
}

# Generic digital-product spam to hard-demote when PERSONAL/PRODUCT stack lanes exist
GENERIC_DIGITAL_SPAM = {"online_course", "printables", "amazon_kdp", "ebooks", "print_on_demand"}
HARD_DEMOTE_PENALTY = 40.0
TEACHING_INTENT_KEYWORDS = ("teach", "course", "udemy", "instructor", "tutorial", "curriculum")


def _profile_has_priority_stack_lanes(profile_l: set[str]) -> bool:
    """True when profile has seo OR video_360 OR software lane tags (same detection as group_hits)."""
    has_seo = any(any(x in t for x in ("seo", "gbp", "citation", "brightlocal", "falcon", "maps")) for t in profile_l)
    has_video = any(any(x in t for x in ("insta360", "360", "pano", "panorama", "panostitch")) for t in profile_l)
    has_software = any(
        any(x in t for x in ("saas", "vercel", "github", "typescript", "python", "micro_saas", "software"))
        for t in profile_l
    )
    return has_seo or has_video or has_software


def profile_indicates_teaching(profile: "Profile") -> bool:
    """True when goals / domain_expertise / stack tags clearly indicate teaching/courses."""
    bits: list[str] = []
    bits.extend(profile.skills.domain_expertise or [])
    bits.append(getattr(profile.goals, "primary", "") or "")
    bits.extend(getattr(profile.goals, "secondary", None) or [])
    bits.extend(sorted(profile.stack_tags()))
    for asset in profile.stack.assets:
        bits.append(asset.name)
        bits.extend(asset.tags)
        if asset.notes:
            bits.append(asset.notes)
    hay = " ".join(str(b).lower() for b in bits)
    return any(k in hay for k in TEACHING_INTENT_KEYWORDS)


def score_stack_match(
    profile_tags: set[str],
    stream: Stream,
    *,
    teaching_goal: bool = False,
) -> tuple[float, list[str]]:
    """Score how well PERSONAL/PRODUCT (and confirmed WORK) stack fits the stream."""
    if not profile_tags:
        return 40.0, []

    notes: list[str] = []
    haystack_parts = [
        stream.stream_id,
        stream.name,
        stream.category,
        " ".join(stream.skills_leveraged),
        " ".join(stream.correlation_tags),
        " ".join(stream.tool_stack_examples),
        " ".join(stream.prerequisites),
        " ".join(stream.startup_checklist),
    ]
    haystack = " ".join(haystack_parts).lower()
    profile_l = {t.lower() for t in profile_tags}

    # Avoid ultra-generic tags that false-match "screen recording software" etc.
    weak_tags = {"software", "video", "ai", "content", "product", "personal", "work"}
    direct_hits = []
    for tag in profile_l:
        if len(tag) < 3 or tag in weak_tags:
            continue
        if tag in haystack or any(tag == part or tag in part for part in re.split(r"[^a-z0-9]+", haystack) if part):
            direct_hits.append(tag)

    group_hits = []
    for group, keys in STACK_KEYWORD_GROUPS.items():
        profile_has = any(
            t == k or k in t or t in k
            for t in profile_l
            for k in keys
        ) or any(
            t in ("seo", "gbp", "citation", "insta360", "pano", "panorama", "panostitch", "local seo")
            for t in profile_l
        ) and group in ("seo", "video_360")
        # Refine profile_has per group
        if group == "seo":
            profile_has = any(any(x in t for x in ("seo", "gbp", "citation", "brightlocal", "falcon", "maps")) for t in profile_l)
        elif group == "video_360":
            profile_has = any(any(x in t for x in ("insta360", "360", "pano", "panorama", "panostitch")) for t in profile_l)
        elif group == "software":
            profile_has = any(any(x in t for x in ("saas", "vercel", "github", "typescript", "python", "micro_saas", "software")) for t in profile_l)
        elif group == "ai":
            profile_has = any(any(x in t for x in ("ai", "llm", "runway", "higgsfield", "chatgpt", "anthropic")) for t in profile_l)
        elif group == "content":
            profile_has = any(any(x in t for x in ("content", "copywriting", "youtube", "newsletter")) for t in profile_l)

        stream_has = any(k in haystack for k in keys) or stream.stream_id in LANE_EXEMPLAR_STREAMS.get(group, [])
        if group == "seo":
            stream_has = stream_has or "seo" in haystack or stream.stream_id == "affiliate_niche_site"
        if group == "video_360":
            stream_has = stream_has or stream.stream_id in ("stock_video",) or "360" in haystack or "pano" in haystack
        if profile_has and stream_has:
            group_hits.append(group)

    # Exemplar bonus: stream is a canonical outlet for a matched lane
    exemplar_bonus = 0.0
    for group in group_hits:
        if stream.stream_id in LANE_EXEMPLAR_STREAMS.get(group, []):
            exemplar_bonus += 12.0

    # Soft / hard demotion for generic digital products when stack lanes exist
    generic_penalty = 0.0
    lane_priority = {"seo", "video_360"} & set(group_hits)
    has_priority_lanes = _profile_has_priority_stack_lanes(profile_l)
    if (
        stream.stream_id in GENERIC_DIGITAL_SPAM
        and has_priority_lanes
        and not teaching_goal
    ):
        # Hard demote: prefer SEO/SaaS/360 exemplars over generic digital spam
        generic_penalty = HARD_DEMOTE_PENALTY
        notes.append(
            "Hard-demoted generic digital product — prefer stack exemplars (SEO/SaaS/360) unless teaching is an explicit goal."
        )
    elif stream.stream_id == "online_course" and (
        any(any(x in t for x in ("seo", "gbp", "insta360", "pano", "panorama")) for t in profile_l)
    ):
        # Soft penalty retained for compatibility when hard-demote does not apply
        generic_penalty = 18.0
        notes.append(
            "Generic course path soft-penalized — prefer SEO/360 stack exemplars unless teaching is the explicit lane."
        )

    score = 30.0 + 10.0 * min(4, len(set(direct_hits))) + 14.0 * min(3, len(set(group_hits)))
    score = score + exemplar_bonus - generic_penalty
    score = max(5.0, min(100.0, score))

    if group_hits:
        notes.insert(0, f"Stack lane fit: {', '.join(sorted(set(group_hits)))}")
    if direct_hits:
        notes.append(f"Matched inventory tags: {', '.join(sorted(set(direct_hits))[:5])}")
    if exemplar_bonus and not any("exemplar" in n.lower() for n in notes):
        notes.append(f"Lane exemplar boost for `{stream.stream_id}`.")
    if not notes:
        notes.append("No strong PERSONAL/PRODUCT stack match — ranked on generic skill fit only.")
    return score, notes


WEIGHTS = {
    "capital":         0.16,
    "maintenance":     0.16,
    "setup":           0.09,
    "risk":            0.13,
    "skill":           0.12,
    "goal":            0.10,
    "time_to_dollar":  0.07,
    "diversification": 0.05,
    "stack":           0.12,
}

assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9

from pia.schemas.profile import Profile
from pia.schemas.stream import ScoredStream


PREFERENCE_PENALTIES = {
    "public_face": {"optional": 6.0, "required": 15.0},
    "customer_support": {"light": 5.0, "ongoing": 12.0},
}

# Streams treated as higher-risk capital deployment under an active debt gate
DEBT_GATE_RISKY_CATEGORIES = {"real_asset", "local_physical", "credit_alt"}
LOW_CEILING_MONTHLY_USD = 100.0  # base monthly_usd_at_typical below this = low ceiling vs aggressive goals


def preference_tradeoffs(profile: Profile, stream: Stream) -> tuple[float, list[str]]:
    """Return personal-fit penalties without turning preferences into exclusions."""
    penalty = 0.0
    explanations: list[str] = []

    if profile.constraints.no_public_face:
        face_penalty = PREFERENCE_PENALTIES["public_face"].get(stream.public_face_requirement, 0.0)
        penalty += face_penalty
        if stream.public_face_requirement == "required":
            explanations.append("Ranked lower because it typically requires a public face.")
        elif stream.public_face_requirement == "optional":
            explanations.append("Ranked slightly lower because it can benefit from a public face.")

    if profile.constraints.no_customer_support:
        support_penalty = PREFERENCE_PENALTIES["customer_support"].get(stream.customer_support_requirement, 0.0)
        penalty += support_penalty
        if stream.customer_support_requirement == "ongoing":
            explanations.append("Ranked lower because it typically requires ongoing customer support.")
        elif stream.customer_support_requirement == "light":
            explanations.append("Ranked slightly lower because it typically needs light customer support.")

    return penalty, explanations


def _monthly_yield_ceiling(stream: Stream, capital: float) -> float:
    """Rough educational ceiling estimate for goal/low-ceiling flags (not advice)."""
    y = stream.yield_
    if y.unit == "monthly_usd_at_typical":
        return float(y.base)
    if y.unit == "annual_pct_on_capital":
        return float(capital) * (y.base / 100.0) / 12.0
    return float(y.base)


def score_stream(
    profile: Profile,
    stream: Stream,
    selected_tags: list[str],
) -> ScoredStream:
    capital = profile.deployable_capital
    maintenance_budget = profile.monthly_maintenance_budget
    user_risk = profile.effective_risk_score
    deadline_days = profile.financial.target_deadline_months * 30
    skills_dict = profile.skills.model_dump(exclude={"domain_expertise"})
    domain_expertise = list(profile.skills.domain_expertise or [])

    # --- Hard disqualifiers (preserve + capital floor) ---
    maint_disq, maint_score = score_maintenance_fit(
        maintenance_budget, stream, return_disqualify=True
    )
    if maint_disq:
        return ScoredStream(
            stream=stream,
            disqualified=True,
            disqualify_reason=(
                f"Maintenance {stream.maintenance_hours_per_month.steady}h/mo exceeds "
                f"budget {maintenance_budget}h/mo"
            ),
            reachability_flags=["maintenance_over_budget"],
        )

    for exc in profile.risk.exclusions:
        if exc in stream.exclusions_match:
            return ScoredStream(
                stream=stream,
                disqualified=True,
                disqualify_reason=f"Stream matches user exclusion: {exc}",
                reachability_flags=["exclusion_match"],
            )

    # Capital hard-DQ: cannot fund catalog minimum from liquid + one month surplus midpoint
    surplus = profile.monthly_surplus_point
    fundable = capital + surplus
    if stream.capital_usd.min > fundable:
        return ScoredStream(
            stream=stream,
            disqualified=True,
            disqualify_reason=(
                f"Capital ${capital:,.0f} (+~${surplus:,.0f}/mo surplus) below stream minimum "
                f"${stream.capital_usd.min:,.0f} — unreachable with current liquid/surplus"
            ),
            unreachable_capital=True,
            reachability_flags=["unreachable_capital"],
        )

    setup_budget = max(profile.time.setup_hours_per_week_90d * 12, 1)
    stack_tags = profile.stack_tags()
    stack_score, stack_notes = score_stack_match(
        stack_tags,
        stream,
        teaching_goal=profile_indicates_teaching(profile),
    )

    factors = {
        "capital":         score_capital_fit(capital, stream),
        "maintenance":     maint_score,
        "setup":           min(100.0, 100 * (1 - stream.setup.hours / setup_budget)),
        "risk":            score_risk_alignment(
            user_risk, profile.risk.exclusions, stream, profile.risk.liquidity_need
        ),
        "skill":           score_skill_leverage(skills_dict, stream, domain_expertise),
        "goal":            score_goal_alignment(profile.goals.primary, stream),
        "time_to_dollar":  score_time_to_first_dollar(deadline_days, stream),
        "diversification": score_diversification_value(selected_tags, stream),
        "stack":           stack_score,
    }

    fit_before_preferences = sum(WEIGHTS[k] * v for k, v in factors.items())
    preference_penalty, preference_explain = preference_tradeoffs(profile, stream)
    fit = max(0.0, fit_before_preferences - preference_penalty)

    debt_gate_demoted = False
    debt_explain: list[str] = []
    if profile.has_debt_gate:
        # Ranking policy (not message-only): demote principal-at-risk / capital-heavy paths
        if stream.category in DEBT_GATE_RISKY_CATEGORIES or stream.risk.principal_loss in ("med", "high"):
            fit = max(0.0, fit - 18.0)
            debt_gate_demoted = True
            debt_explain.append(
                "Debt gate: demoted — prioritize high-interest paydown before capital-at-risk streams."
            )
        elif stream.capital_usd.typical >= 1000 and capital < stream.capital_usd.typical:
            fit = max(0.0, fit - 8.0)
            debt_gate_demoted = True
            debt_explain.append(
                "Debt gate: soft demotion — surplus should favor debt paydown over locking new capital."
            )

    # Low-ceiling soft penalty when chasing aggressive cash_flow targets
    ceiling = _monthly_yield_ceiling(stream, capital)
    target = profile.financial.target_monthly_passive_usd or 0.0
    low_ceiling = False
    ceiling_explain: list[str] = []
    if (
        profile.goals.primary == "cash_flow"
        and stream.yield_.unit == "monthly_usd_at_typical"
        and stream.yield_.base < LOW_CEILING_MONTHLY_USD
        and target >= 1000
    ):
        low_ceiling = True
        fit = max(0.0, fit - 12.0)
        ceiling_explain.append(
            f"Low ceiling vs goal: catalog base ~${stream.yield_.base:,.0f}/mo "
            f"vs target ${target:,.0f}/mo — weak as a primary path."
        )

    if stream.yield_.unit == "annual_pct_on_capital":
        yield_normalized = min(stream.yield_.base / 30, 1.0) * 100
    else:
        yield_normalized = min(stream.yield_.base / 2000, 1.0) * 100

    ras = fit * (yield_normalized / (1 + stream.risk_composite))
    effort_yield = (stream.yield_.base * capital / 12) / max(1, stream.maintenance_hours_per_month.steady)

    liquidity_penalty = LIQUIDITY_NEED_PENALTIES.get(profile.risk.liquidity_need, {}).get(
        stream.risk.liquidity, 0.0
    )

    reachability_flags: list[str] = []
    # Soft warning only — hard unreachable is already DQ'd above
    thin_capital = capital < stream.capital_usd.typical * 0.25 and stream.capital_usd.typical > 0
    if thin_capital:
        reachability_flags.append("thin_capital_vs_typical")
    unreachable_capital = False
    missing_prereq = False
    # Soft flag: real_asset streams imply property capital even when somehow scored
    if stream.category == "real_asset" and capital < stream.capital_usd.min:
        missing_prereq = True
        reachability_flags.append("missing_capital_prereq")
    if low_ceiling:
        reachability_flags.append("low_ceiling")
    if debt_gate_demoted:
        reachability_flags.append("debt_gate_demoted")

    why_stack = ""
    if stack_notes and "No strong" not in stack_notes[0]:
        why_stack = stack_notes[0]
    skill_hits = [k for k in stream.skills_leveraged if skills_dict.get(k, 0) >= 6]
    why_fit_bits = []
    if skill_hits:
        why_fit_bits.append("skills " + ", ".join(f"{k}={skills_dict[k]}" for k in skill_hits[:4]))
    if why_stack:
        why_fit_bits.append(why_stack)
    if domain_expertise:
        matched_domains = [d for d in domain_expertise if d.lower() in " ".join(stack_notes).lower() or d.lower() in stream.stream_id or d.lower() in stream.name.lower()]
        if matched_domains:
            why_fit_bits.append("domain " + ", ".join(matched_domains[:3]))

    explain = [
        f"Fit: {fit:.0f}/100 — best factors: {sorted(factors.items(), key=lambda x: -x[1])[:2]}",
        *preference_explain,
        *debt_explain,
        *ceiling_explain,
        *stack_notes[:2],
        (
            "Why this fits your stack: " + "; ".join(why_fit_bits)
            if why_fit_bits
            else "Why this fits: generic catalog fit — add stack inventory / domain_expertise for sharper why-copy."
        ),
        f"Main risk: {stream.risk.flags[0] if stream.risk.flags else 'see risk profile'}",
        f"First action: {stream.startup_checklist[0] if stream.startup_checklist else 'See playbook'}",
    ]
    if liquidity_penalty > 0:
        explain.append(
            f"Ranked lower because you may need cash within {profile.risk.liquidity_need} "
            f"but this stream has {stream.risk.liquidity} liquidity."
        )
    if profile.has_debt_gate and not debt_explain:
        explain.append(
            "Debt gate active: keep new capital deployment minimal; surplus guidance favors paydown."
        )

    return ScoredStream(
        stream=stream,
        fit_score=round(fit, 1),
        ras=round(ras, 1),
        effort_yield=round(effort_yield, 2),
        explain=explain,
        capital_suggested_usd=(
            min(capital, stream.capital_usd.typical)
            if stream.capital_usd.typical > 0
            else capital * 0.1
        ),
        unreachable_capital=unreachable_capital,
        missing_prereq=missing_prereq,
        low_ceiling=low_ceiling,
        debt_gate_demoted=debt_gate_demoted,
        stack_match_score=round(stack_score, 1),
        stack_match_notes=stack_notes,
        reachability_flags=reachability_flags,
    )


def rank_streams(
    profile: Profile,
    streams: list[Stream],
) -> list[ScoredStream]:
    selected_tags: list[str] = []
    scored: list[ScoredStream] = []
    for s in streams:
        result = score_stream(profile, s, selected_tags)
        if not result.disqualified:
            selected_tags.extend(s.correlation_tags)
        scored.append(result)
    scored.sort(key=lambda x: (not x.disqualified, x.ras), reverse=True)
    return scored
