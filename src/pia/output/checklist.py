from __future__ import annotations
from pia.schemas.stream import ScoredStream
from pia.output.renderer import DISCLAIMER


def render_90day_checklist(scored: list[ScoredStream]) -> str:
    lines = [
        "# 90-Day Execution Checklist\n",
        "Copy this to your task manager. Check off daily.\n",
    ]
    qualified = [s for s in scored if not s.disqualified][:5]

    lines.append("## Week 1: Accounts & Setup")
    lines.append("- [ ] Create `runs/tracker.csv` and log all streams")
    for s in qualified:
        if s.stream.startup_checklist:
            lines.append(f"- [ ] [{s.stream.name}] {s.stream.startup_checklist[0]}")

    lines.append("\n## Weeks 2-4: Launch")
    for s in qualified:
        for step in s.stream.startup_checklist[1:3]:
            lines.append(f"- [ ] [{s.stream.name}] {step}")

    lines.append("\n## Month 2: First Revenue Check")
    for s in qualified:
        lines.append(f"- [ ] [{s.stream.name}] Log first income in tracker")
        if s.stream.kpis:
            lines.append(f"  - KPI: {s.stream.kpis[0]}")

    lines.append("\n## Month 3: Kill or Double Down")
    for s in qualified:
        lines.append(f"- [ ] [{s.stream.name}] Check kill criteria:")
        for k in s.stream.kill_criteria[:2]:
            lines.append(f"  - {k}")

    lines.append("\n## Revisit Triggers")
    lines.append("- [ ] Re-run analysis if income <50% of base plan for 2 months")
    lines.append("- [ ] Re-run analysis at month 6 and month 12")
    lines.append("- [ ] Re-run if a platform changes fees >20% or policy materially")

    lines.append(DISCLAIMER)
    return "\n".join(lines)
