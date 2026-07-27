from __future__ import annotations
import json
import uuid
from datetime import date
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import click
from rich.console import Console
from rich.table import Table

from pia.schemas.profile import Profile, Financial, Range, TimeProfile, Risk, Skills, Goals, Constraints
from pia.catalog.loader import load_catalog
from pia.engine.scorer import rank_streams
from pia.engine.portfolio import build_portfolio
from pia.engine.projector import project_paper, reverse_solve
from pia.output.renderer import render_ranked_table, render_portfolio_blueprint, render_exec_summary
from pia.output.exporter import new_run_dir, export_run

console = Console()
CATALOG_DIR = Path(__file__).parent.parent.parent / "catalog" / "streams"


@click.group()
def cli():
    """Passive Income Analyzer - scores streams, builds portfolios, exports plans."""
    pass


@cli.command()
@click.option("--acknowledge-risk", is_flag=True, default=False,
              help="Required to include high-risk streams (crypto, adult, P2P)")
def analyze(acknowledge_risk):
    """Interactive profile intake -> full analysis -> export artifacts."""
    console.rule("[bold]Passive Income Analyzer v0.1[/bold]")
    console.print("This tool is for [bold]educational planning only[/bold] — not financial advice.\n")

    profile_id = click.prompt("Profile name / ID", default=f"profile-{uuid.uuid4().hex[:6]}")

    console.print("\n[bold cyan]Step 1: Capital[/bold cyan]")
    capital_min = click.prompt("Deployable liquid capital — minimum ($)", type=float, default=0.0)
    capital_max = click.prompt("Deployable liquid capital — maximum ($)", type=float, default=capital_min)
    emergency_months = click.prompt("Emergency fund (months of expenses)", type=float, default=0.0)
    debt_usd = click.prompt("High-interest debt balance ($, 0 if none)", type=float, default=0.0)
    target_monthly = click.prompt("Target monthly passive income ($)", type=float, default=1000.0)
    deadline_months = click.prompt("Target deadline (months)", type=int, default=24)

    console.print("\n[bold cyan]Step 2: Time[/bold cyan]")
    setup_hrs = click.prompt("Available setup hours/week for next 90 days", type=float, default=5.0)
    maint_hrs = click.prompt("Available maintenance hours/month (steady state)", type=float, default=4.0)

    console.print("\n[bold cyan]Step 3: Risk[/bold cyan]")
    risk_score = click.prompt("Risk tolerance (1=very conservative, 10=aggressive)", type=int, default=5)
    exclusions_raw = click.prompt(
        "Exclude categories? (crypto, adult, p2p, leveraged_re — comma-sep or blank)",
        default=""
    )
    exclusions = [e.strip() for e in exclusions_raw.split(",") if e.strip()]
    if not acknowledge_risk:
        for risky in ("crypto", "p2p", "leveraged_re", "adult"):
            if risky not in exclusions:
                exclusions.append(risky)
        console.print("[dim]High-risk categories auto-excluded. Use --acknowledge-risk to include.[/dim]")

    console.print("\n[bold cyan]Step 4: Skills (0–10)[/bold cyan]")
    skills_data = {}
    for skill in ("ai_ml", "content", "video", "software", "marketing", "real_estate"):
        skills_data[skill] = click.prompt(f"  {skill}", type=int, default=0)

    console.print("\n[bold cyan]Step 5: Goals[/bold cyan]")
    primary_goal = click.prompt(
        "Primary goal",
        type=click.Choice(["cash_flow", "wealth", "freedom", "legacy", "tax_efficiency"]),
        default="cash_flow",
    )
    no_face = click.confirm("Prefer no public face / anonymous?", default=False)
    no_support = click.confirm("Prefer no customer support requirements?", default=False)

    profile = Profile(
        profile_id=profile_id,
        created_at=date.today().isoformat(),
        financial=Financial(
            liquid_deployable_usd=Range(min=capital_min, max=capital_max),
            emergency_fund_months=emergency_months,
            high_interest_debt_usd=debt_usd,
            target_monthly_passive_usd=target_monthly,
            target_deadline_months=deadline_months,
        ),
        time=TimeProfile(
            setup_hours_per_week_90d=setup_hrs,
            maintenance_hours_per_month_steady=maint_hrs,
        ),
        risk=Risk(score_1_to_10=risk_score, exclusions=exclusions),
        skills=Skills(**skills_data),
        goals=Goals(primary=primary_goal),
        constraints=Constraints(no_public_face=no_face, no_customer_support=no_support),
    )

    if profile.has_debt_gate:
        console.print(f"\n[bold red]DEBT GATE:[/bold red] ${debt_usd:,.0f} high-interest debt detected.")
        console.print("Recommend: prioritize aggressive paydown before deploying capital into income streams.\n")

    if profile.financial.emergency_fund_months < 3:
        console.print("[yellow]Emergency fund < 3 months. Risk score capped at 4 for new illiquid bets.[/yellow]\n")

    with console.status("Loading catalog and scoring streams..."):
        streams = load_catalog(CATALOG_DIR)
        ranked = rank_streams(profile, streams)

    console.rule("Ranked Opportunities")
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("#", width=3)
    table.add_column("Stream", width=32)
    table.add_column("PI", width=4)
    table.add_column("RAS", width=6)
    table.add_column("Status")
    for i, r in enumerate(ranked[:15], 1):
        status = "[red]disqualified[/red]" if r.disqualified else "[green]✓[/green]"
        table.add_row(str(i), r.stream.name, str(r.stream.passivity_index), f"{r.ras:.0f}", status)
    console.print(table)

    alloc = build_portfolio(profile, ranked)

    if alloc.debt_gate_active:
        console.print(f"\n[bold red]{alloc.debt_gate_message}[/bold red]\n")

    monthly_proj = {"bear": 0.0, "base": 0.0, "bull": 0.0}
    for item in alloc.allocations:
        match = next((r for r in ranked if r.stream.stream_id == item.stream_id), None)
        if match and match.stream.category == "paper":
            proj = project_paper(item.allocation_usd, match.stream.yield_.base, 0, 12, reinvest=False)
            for scenario in ("bear", "base", "bull"):
                income_key = f"income_month_12"
                if income_key in proj[scenario]:
                    monthly_proj[scenario] += proj[scenario][income_key]

    run_dir = new_run_dir(profile_id)
    qualified_top5 = [r for r in ranked if not r.disqualified][:5]
    week1 = [r.stream.startup_checklist[0] for r in qualified_top5 if r.stream.startup_checklist]

    artifacts = {
        "profile.json": profile.model_dump_json(indent=2),
        "ranked_table.md": render_ranked_table(ranked),
        "portfolio_blueprint.md": render_portfolio_blueprint(alloc, monthly_proj),
        "exec_summary.md": render_exec_summary(profile_id, alloc, monthly_proj, qualified_top5, week1),
    }
    export_run(run_dir, artifacts)
    console.print(f"\n[bold green]Done![/bold green] Run saved to: {run_dir}")
    console.print(f"  Bear/Base/Bull monthly (paper): ${monthly_proj['bear']:,.0f} / ${monthly_proj['base']:,.0f} / ${monthly_proj['bull']:,.0f}")


@cli.command()
def chat():
    """Describe your situation in plain English -> profile extracted by AI -> run analysis."""
    console.print("Describe your financial situation, time, skills, and income goals.")
    console.print("(Be as detailed or vague as you like — ranges are fine.)\n")
    text = click.edit(text="Describe your situation here...")
    if not text or text.strip() == "Describe your situation here...":
        console.print("[red]No input provided.[/red]")
        return
    try:
        from pia.ai.intake import intake_from_text
        with console.status("Extracting profile with AI..."):
            profile = intake_from_text(text)
        console.print(f"[green]Profile extracted:[/green] {profile.profile_id}")
        console.print(profile.model_dump_json(indent=2))
        if click.confirm("\nRun full analysis with this profile?"):
            with console.status("Scoring streams..."):
                streams = load_catalog(CATALOG_DIR)
                ranked = rank_streams(profile, streams)
            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("#", width=3)
            table.add_column("Stream", width=32)
            table.add_column("PI", width=4)
            table.add_column("RAS", width=6)
            table.add_column("Status")
            for i, r in enumerate(ranked[:10], 1):
                status = "[red]disq[/red]" if r.disqualified else "[green]✓[/green]"
                table.add_row(str(i), r.stream.name, str(r.stream.passivity_index), f"{r.ras:.0f}", status)
            console.print(table)
    except RuntimeError as e:
        console.print(f"[red]{e}[/red]")


if __name__ == "__main__":
    cli()
