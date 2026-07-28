from __future__ import annotations
import os


def generate_playbook(profile: "Profile", stream: "Stream") -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return _static_playbook(stream)

    try:
        return _provider_playbook(profile, stream, api_key)
    except Exception:
        return _static_playbook(stream, provider_unavailable=True)


def _provider_playbook(profile: "Profile", stream: "Stream", api_key: str) -> str:
    """Generate a playbook with Anthropic; callers own fallback behavior."""
    from anthropic import Anthropic
    client = Anthropic(api_key=api_key)

    prompt = (
        f"Write a practical 90-day launch playbook for someone starting '{stream.name}'.\n\n"
        f"Profile context:\n"
        f"- Capital available: ${profile.deployable_capital:,.0f}\n"
        f"- Risk tolerance: {profile.effective_risk_score}/10\n"
        f"- Primary goal: {profile.goals.primary}\n"
        f"- Setup hours/week: {profile.time.setup_hours_per_week_90d}\n"
        f"- Maintenance budget: {profile.monthly_maintenance_budget}h/mo\n\n"
        f"Stream details:\n"
        f"- Passivity index: {stream.passivity_index}/10\n"
        f"- Yield: {stream.yield_.bear}–{stream.yield_.bull}% ({stream.yield_.unit})\n"
        f"- Startup checklist: {', '.join(stream.startup_checklist[:3])}\n"
        f"- Kill criteria: {', '.join(stream.kill_criteria[:2])}\n\n"
        "Format as markdown with sections: Overview, Week 1–4 Actions, Month 2–3 Milestones, "
        "KPIs to Track, Kill Criteria. Be specific and actionable. No hype. "
        "Do not use 'guaranteed' or 'risk-free'. End with a disclaimer that this is not financial advice."
    )

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


def _static_playbook(stream: "Stream", provider_unavailable: bool = False) -> str:
    lines = [
        f"# {stream.name} — 90-Day Playbook",
        "",
        "*(Built-in practical playbook.)*" if provider_unavailable else "*(AI playbook unavailable — set ANTHROPIC_API_KEY in .env for full playbook)*",
        "",
        "## Startup Checklist",
    ]
    for item in stream.startup_checklist:
        lines.append(f"- [ ] {item}")
    lines.extend([
        "",
        "## KPIs",
    ])
    for kpi in stream.kpis:
        lines.append(f"- {kpi}")
    lines.extend([
        "",
        "## Kill Criteria",
    ])
    for crit in stream.kill_criteria:
        lines.append(f"- {crit}")
    lines.extend([
        "",
        "---",
        "*This is educational content only — not financial advice.*",
    ])
    return "\n".join(lines)
