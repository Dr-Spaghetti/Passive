from __future__ import annotations
import math
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
) -> float:
    if not stream.skills_leveraged:
        return 50.0
    best = max((user_skills.get(k, 0) for k in stream.skills_leveraged), default=0)
    return min(100.0, 20 + 8 * best)


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


WEIGHTS = {
    "capital":        0.18,
    "maintenance":    0.18,
    "setup":          0.10,
    "risk":           0.15,
    "skill":          0.14,
    "goal":           0.12,
    "time_to_dollar": 0.08,
    "diversification":0.05,
}

from pia.schemas.profile import Profile
from pia.schemas.stream import ScoredStream


PREFERENCE_PENALTIES = {
    "public_face": {"optional": 6.0, "required": 15.0},
    "customer_support": {"light": 5.0, "ongoing": 12.0},
}


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

    maint_disq, maint_score = score_maintenance_fit(
        maintenance_budget, stream, return_disqualify=True
    )
    if maint_disq:
        return ScoredStream(
            stream=stream,
            disqualified=True,
            disqualify_reason=f"Maintenance {stream.maintenance_hours_per_month.steady}h/mo exceeds budget {maintenance_budget}h/mo",
        )

    for exc in profile.risk.exclusions:
        if exc in stream.exclusions_match:
            return ScoredStream(
                stream=stream,
                disqualified=True,
                disqualify_reason=f"Stream matches user exclusion: {exc}",
            )

    setup_budget = max(profile.time.setup_hours_per_week_90d * 12, 1)
    factors = {
        "capital":        score_capital_fit(capital, stream),
        "maintenance":    maint_score,
        "setup":          min(100.0, 100 * (1 - stream.setup.hours / setup_budget)),
        "risk":           score_risk_alignment(user_risk, profile.risk.exclusions, stream, profile.risk.liquidity_need),
        "skill":          score_skill_leverage(skills_dict, stream),
        "goal":           score_goal_alignment(profile.goals.primary, stream),
        "time_to_dollar": score_time_to_first_dollar(deadline_days, stream),
        "diversification":score_diversification_value(selected_tags, stream),
    }

    fit_before_preferences = sum(WEIGHTS[k] * v for k, v in factors.items())
    preference_penalty, preference_explain = preference_tradeoffs(profile, stream)
    fit = max(0.0, fit_before_preferences - preference_penalty)

    if stream.yield_.unit == "annual_pct_on_capital":
        yield_normalized = min(stream.yield_.base / 30, 1.0) * 100
    else:
        yield_normalized = min(stream.yield_.base / 2000, 1.0) * 100

    ras = fit * (yield_normalized / (1 + stream.risk_composite))
    effort_yield = (stream.yield_.base * capital / 12) / max(1, stream.maintenance_hours_per_month.steady)

    liquidity_penalty = LIQUIDITY_NEED_PENALTIES.get(profile.risk.liquidity_need, {}).get(stream.risk.liquidity, 0.0)

    explain = [
        f"Fit: {fit:.0f}/100 — best factors: {sorted(factors.items(), key=lambda x: -x[1])[:2]}",
        *preference_explain,
        f"Main risk: {stream.risk.flags[0] if stream.risk.flags else 'see risk profile'}",
        f"First action: {stream.startup_checklist[0] if stream.startup_checklist else 'See playbook'}",
    ]
    if liquidity_penalty > 0:
        explain.append(
            f"Ranked lower because you may need cash within {profile.risk.liquidity_need} "
            f"but this stream has {stream.risk.liquidity} liquidity."
        )

    return ScoredStream(
        stream=stream,
        fit_score=round(fit, 1),
        ras=round(ras, 1),
        effort_yield=round(effort_yield, 2),
        explain=explain,
        capital_suggested_usd=min(capital, stream.capital_usd.typical) if stream.capital_usd.typical > 0 else capital * 0.1,
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
