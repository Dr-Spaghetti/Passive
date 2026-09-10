from __future__ import annotations
from pia.schemas.stream import ScoredStream
from pia.engine.portfolio import PortfolioAllocation

DISCLAIMER = (
    "\n---\n"
    "**Disclaimer:** This output is educational analysis only. It is not financial, investment, "
    "tax, or legal advice. Income results vary widely; many streams earn $0 after costs. "
    "Yields, fees, and platform rules change. You are solely responsible for your decisions "
    "and compliance with laws and platform terms. Consult licensed professionals before "
    "material capital deployment.\n"
)


def render_ranked_table(scored: list[ScoredStream]) -> str:
    rows = [
        "| # | Stream | Passivity | Fit | RAS | Status |",
        "|---|--------|-----------|-----|-----|--------|",
    ]
    for i, s in enumerate(scored, 1):
        label = s.stream.passivity_label
        if s.stream.passivity_index < 5:
            label += " (semi-active)"
        status = "✗ disqualified" if s.disqualified else "✓"
        reason = f" — {s.disqualify_reason}" if s.disqualified else ""
        stale = " [UNVERIFIED — verify before allocating]" if s.stream.is_stale else ""
        rows.append(
            f"| {i} | {s.stream.name}{stale} | {s.stream.passivity_index}/10 {label} | "
            f"{s.fit_score:.0f} | {s.ras:.0f} | {status}{reason} |"
        )
    rows.append("\n" + DISCLAIMER)
    return "\n".join(rows)


def render_portfolio_blueprint(
    alloc: PortfolioAllocation,
    monthly_projections: dict[str, float],
) -> str:
    lines = ["## Portfolio Blueprint\n"]

    if alloc.debt_gate_active:
        lines.append(f"> {alloc.debt_gate_message}\n")
        if getattr(alloc, "surplus_allocation_guidance", ""):
            lines.append(f"> {alloc.surplus_allocation_guidance}\n")

    lines.append(f"**Total Deployed:** ${alloc.total_deployed:,.0f}\n")
    lines.append("### Projected Monthly Income at Month 12")
    lines.append(f"- Bear: ${monthly_projections.get('bear', 0):,.0f}/mo")
    lines.append(f"- Base: ${monthly_projections.get('base', 0):,.0f}/mo")
    lines.append(f"- Bull: ${monthly_projections.get('bull', 0):,.0f}/mo\n")

    lines.append("### Allocations\n")
    lines.append("| Stream | Tier | Phase | Amount | % | Passivity |")
    lines.append("|--------|------|-------|--------|---|-----------|")
    for item in alloc.allocations:
        lines.append(
            f"| {item.stream_name} | {item.tier} | {item.phase} | "
            f"${item.allocation_usd:,.0f} | {item.allocation_pct:.1f}% | {item.passivity_index}/10 |"
        )

    lines.append("\n### Phase Summary")
    for phase, amount in alloc.phase_summary.items():
        if amount > 0:
            lines.append(f"- {phase}: ${amount:,.0f}")

    lines.append(DISCLAIMER)
    return "\n".join(lines)


def render_tracker_csv(scored: list[ScoredStream]) -> str:
    lines = ["Date,Stream,Gross_USD,Fees_USD,Net_USD,Hours,vs_Plan_Net,vs_Plan_Hours,Notes"]
    qualified = [s for s in scored if not s.disqualified][:8]
    for s in qualified:
        lines.append(f"YYYY-MM-DD,{s.stream.name},0,0,0,0,{s.stream.yield_.base},target_tbd,")
    return "\n".join(lines)


def render_exec_summary(
    profile_id: str,
    alloc: PortfolioAllocation,
    monthly_projections: dict[str, float],
    top_streams: list[ScoredStream],
    week1_actions: list[str],
) -> str:
    lines = [
        f"# Passive Income Analysis — Executive Summary\n",
        f"**Profile:** {profile_id}\n",
        "## Projected Monthly Income at Month 12",
        "| Scenario | Monthly Income |",
        "|----------|---------------|",
        f"| Bear     | ${monthly_projections.get('bear', 0):,.0f} |",
        f"| Base     | ${monthly_projections.get('base', 0):,.0f} |",
        f"| Bull     | ${monthly_projections.get('bull', 0):,.0f} |\n",
        "## Top Recommended Streams",
    ]
    for s in top_streams[:5]:
        if not s.disqualified:
            lines.append(
                f"- **{s.stream.name}** (PI {s.stream.passivity_index}/10, RAS {s.ras:.0f}) — "
                f"{s.explain[0] if s.explain else ''}"
            )
    lines.append("\n## Week 1 Actions")
    for action in week1_actions:
        lines.append(f"- [ ] {action}")
    lines.append(DISCLAIMER)
    return "\n".join(lines)
