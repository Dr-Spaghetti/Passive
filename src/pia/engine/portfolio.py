from __future__ import annotations
from dataclasses import dataclass, field
from pia.schemas.profile import Profile
from pia.schemas.stream import ScoredStream


@dataclass
class AllocationItem:
    stream_id: str
    stream_name: str
    tier: str
    phase: str
    allocation_usd: float
    allocation_pct: float
    passivity_index: int
    ras: float


@dataclass
class PortfolioAllocation:
    allocations: list[AllocationItem] = field(default_factory=list)
    total_deployed: float = 0.0
    debt_gate_active: bool = False
    debt_gate_message: str = ""
    surplus_allocation_guidance: str = ""
    phase_summary: dict[str, float] = field(default_factory=dict)
    max_risky_allocation_pct: float = 100.0


CORE_CATEGORIES = {"paper", "real_asset"}
LOCAL_CATEGORIES = {"local_physical"}
RISKY_UNDER_DEBT = {"real_asset", "local_physical", "credit_alt"}


def surplus_guidance(profile: Profile) -> str:
    """Educational surplus split while high-interest debt remains. Not advice."""
    if not profile.has_debt_gate:
        return ""
    surplus = profile.monthly_surplus_point
    debt = profile.financial.high_interest_debt_usd
    debt_share = max(0.0, surplus * 0.60)
    buffer_share = max(0.0, surplus * 0.30)
    explore_share = max(0.0, surplus * 0.10)
    return (
        f"Surplus allocation guidance (educational): with ${debt:,.0f} high-interest debt and "
        f"~${surplus:,.0f}/mo surplus midpoint — earmark >=60% (~${debt_share:,.0f}) to debt paydown, "
        f"~30% (~${buffer_share:,.0f}) to emergency-fund buffer, "
        f"<=10% (~${explore_share:,.0f}) to low-capital skill experiments. "
        "Not financial advice."
    )


def build_portfolio(
    profile: Profile,
    ranked: list[ScoredStream],
) -> PortfolioAllocation:
    alloc = PortfolioAllocation()
    capital = profile.deployable_capital
    risk = profile.effective_risk_score

    if profile.has_debt_gate:
        alloc.debt_gate_active = True
        alloc.max_risky_allocation_pct = 10.0
        alloc.debt_gate_message = (
            f"DEBT GATE: ${profile.financial.high_interest_debt_usd:,.0f} high-interest debt detected. "
            "Prioritize aggressive paydown before deploying capital into income streams. "
            "Recommended: allocate >=60% of monthly surplus to debt. Max risky allocation capped at 10%."
        )
        alloc.surplus_allocation_guidance = surplus_guidance(profile)
        # Haircut deployable capital while debt gate is active
        capital = capital * 0.4

    qualified = [
        r for r in ranked
        if not r.disqualified and not r.unreachable_capital
    ]
    if profile.has_debt_gate:
        # Ranking/portfolio policy: skip capital-at-risk categories while debt gate is on
        # unless they somehow have zero capital need and were not demoted heavily.
        filtered = []
        for r in qualified:
            if r.stream.category in RISKY_UNDER_DEBT and r.stream.capital_usd.min > 0:
                continue
            if r.missing_prereq:
                continue
            filtered.append(r)
        qualified = filtered

    if not qualified:
        return alloc

    if risk <= 3:
        core_target, satellite_target, local_target = 0.70, 0.20, 0.10
    elif risk <= 5:
        core_target, satellite_target, local_target = 0.55, 0.30, 0.15
    else:
        core_target, satellite_target, local_target = 0.40, 0.45, 0.15

    core_budget = capital * core_target
    satellite_budget = capital * satellite_target
    local_budget = capital * local_target

    core_spent = satellite_spent = local_spent = 0.0
    risky_spent = 0.0
    risky_cap = capital * (alloc.max_risky_allocation_pct / 100.0) if alloc.debt_gate_active else capital
    tag_exposure: dict[str, float] = {}
    items: list[AllocationItem] = []

    for scored in qualified:
        s = scored.stream
        if core_spent + satellite_spent + local_spent >= capital:
            break

        if s.category in CORE_CATEGORIES:
            tier = "core"
            budget_remaining = core_budget - core_spent
        elif s.category in LOCAL_CATEGORIES:
            tier = "local"
            budget_remaining = local_budget - local_spent
        else:
            tier = "satellite"
            budget_remaining = satellite_budget - satellite_spent

        if budget_remaining <= 0:
            continue

        is_risky = s.category in RISKY_UNDER_DEBT or s.risk.principal_loss in ("med", "high")
        if alloc.debt_gate_active and is_risky and risky_spent >= risky_cap:
            continue

        max_stream = min(capital * 0.35, budget_remaining)
        suggested = scored.capital_suggested_usd if scored.capital_suggested_usd > 0 else capital * 0.1
        amount = min(suggested, max_stream)
        if alloc.debt_gate_active and is_risky:
            amount = min(amount, max(0.0, risky_cap - risky_spent))

        for tag in s.correlation_tags:
            already = tag_exposure.get(tag, 0)
            if capital > 0 and (already + amount) / capital > 0.45:
                amount = max(0, capital * 0.45 - already)

        if amount <= 0:
            continue

        if scored.stream.setup.calendar_weeks <= 1 and amount <= 500:
            phase = "P0"
        elif scored.stream.setup.calendar_weeks <= 12:
            phase = "P1"
        elif scored.stream.setup.calendar_weeks <= 52:
            phase = "P2"
        else:
            phase = "P3"

        items.append(AllocationItem(
            stream_id=s.stream_id,
            stream_name=s.name,
            tier=tier,
            phase=phase,
            allocation_usd=round(amount, 2),
            allocation_pct=0.0,
            passivity_index=s.passivity_index,
            ras=scored.ras,
        ))

        if tier == "core":
            core_spent += amount
        elif tier == "local":
            local_spent += amount
        else:
            satellite_spent += amount
        if is_risky:
            risky_spent += amount

        for tag in s.correlation_tags:
            tag_exposure[tag] = tag_exposure.get(tag, 0) + amount

    total = sum(i.allocation_usd for i in items)
    for item in items:
        item.allocation_pct = round(item.allocation_usd / total * 100, 1) if total > 0 else 0.0

    alloc.allocations = items
    alloc.total_deployed = round(total, 2)
    alloc.phase_summary = {
        phase: round(sum(i.allocation_usd for i in items if i.phase == phase), 2)
        for phase in ("P0", "P1", "P2", "P3")
    }
    return alloc
