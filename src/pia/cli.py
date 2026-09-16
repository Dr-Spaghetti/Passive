from __future__ import annotations
import json
import sys
import uuid
from datetime import date
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

if sys.platform == "win32":
    # Windows consoles default to the system codepage (e.g. cp1252), which can't
    # encode rich's box-drawing/checkmark characters. Force UTF-8 regardless of
    # the console's codepage so `pia analyze`'s tables render without crashing.
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass

import click
from rich.console import Console
from rich.table import Table

from pia.schemas.profile import Profile, Financial, Range, TimeProfile, Risk, Skills, Goals, Constraints
from pia.catalog.loader import load_catalog
from pia.engine.scorer import rank_streams
from pia.engine.portfolio import build_portfolio
from pia.engine.projector import project_paper, reverse_solve
from pia.output.renderer import (
    render_ranked_table,
    render_portfolio_blueprint,
    render_exec_summary,
    render_tracker_csv,
)
from pia.output.checklist import render_90day_checklist
from pia.output.exporter import new_run_dir, export_run
from pia.output.decision_brief import build_decision_brief, catalog_freshness_report, COS_CONTRACT
from pia.output.commitment_brief import build_commitment_brief, render_commitment_markdown
from pia.catalog.inventory import load_inventory, merge_inventory_into_profile

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
            proj = project_paper(
                item.allocation_usd,
                match.stream.yield_.base,
                0,
                12,
                reinvest=False,
                scenario_yields={
                    "bear": match.stream.yield_.bear,
                    "base": match.stream.yield_.base,
                    "bull": match.stream.yield_.bull,
                },
            )
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
        "checklist_90day.md": render_90day_checklist(ranked),
        "tracker.csv": render_tracker_csv(ranked),
    }

    top_qualified = [r for r in ranked if not r.disqualified][:3]
    if top_qualified and click.confirm(f"\nGenerate AI playbooks for top {len(top_qualified)} streams? (uses Claude API)"):
        from pia.ai.playbooks import generate_playbook
        for scored in top_qualified:
            with console.status(f"Generating playbook: {scored.stream.name}..."):
                pb = generate_playbook(profile, scored.stream)
            artifacts[f"playbook_{scored.stream.stream_id}.md"] = pb

    export_run(run_dir, artifacts)

    from pia.storage import save_run
    save_run(
        run_id=run_dir.name,
        profile_id=profile_id,
        profile_json=artifacts["profile.json"],
        top5_ids=[r.stream.stream_id for r in qualified_top5],
        total_deployed=alloc.total_deployed,
        projected_base=monthly_proj["base"],
    )

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


@cli.command(name="runs")
def list_runs_cmd():
    """List all saved analysis runs."""
    from pia.storage import list_runs
    runs = list_runs()
    if not runs:
        console.print("No runs yet. Run `pia analyze` first.")
        return
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Date")
    table.add_column("Profile")
    table.add_column("Projected Base/mo")
    for r in runs:
        table.add_row(r["date"], r["profile_id"], f"${r['projected_base']:,.0f}")
    console.print(table)


@cli.command()
@click.argument("stream_id")
@click.option("--profile-id", default="", help="Optional profile_id for tracker rows")
def log(stream_id, profile_id):
    """Log actual income for a stream."""
    from pia.tracker import log_income
    gross = click.prompt("Gross income ($)", type=float)
    fees = click.prompt("Fees/costs ($)", type=float, default=0.0)
    hours = click.prompt("Hours spent", type=float, default=0.0)
    notes = click.prompt("Notes (optional)", default="")
    log_income(stream_id, gross, fees, hours, notes, profile_id=profile_id)
    console.print(f"[green]Logged: ${gross - fees:.2f} net for {stream_id}[/green]")


@cli.command()
@click.argument("stream_id")
@click.option("--plan-net", type=float, default=None, help="Planned monthly net (optional if stored via pia plan set)")
@click.option("--plan-hours", type=float, default=None, help="Planned monthly hours (optional if stored)")
def drift(stream_id, plan_net, plan_hours):
    """Check a stream for income or time drift vs plan."""
    from pia.tracker import check_drift
    alerts = check_drift(stream_id, plan_net, plan_hours)
    if alerts:
        for a in alerts:
            style = "red" if a.startswith("⚠") else "yellow"
            console.print(f"[{style}]{a}[/{style}]")
    else:
        console.print(f"[green]{stream_id}: no drift detected.[/green]")


@cli.group()
def plan():
    """Persist plan baselines for weekly drift checks."""
    pass


@plan.command("set")
@click.argument("stream_id")
@click.option("--plan-net", type=float, required=True)
@click.option("--plan-hours", type=float, required=True)
@click.option("--profile-id", default="")
@click.option("--notes", default="")
def plan_set(stream_id, plan_net, plan_hours, profile_id, notes):
    """Store plan baselines used by `pia drift` / POST /api/drift."""
    from pia.tracker import set_plan
    row = set_plan(stream_id, plan_net, plan_hours, profile_id=profile_id, notes=notes)
    console.print(f"[green]Plan saved for {stream_id}:[/green] {row}")


@plan.command("show")
@click.argument("stream_id", required=False)
@click.option("--profile-id", default=None)
def plan_show(stream_id, profile_id):
    """Show one plan or list plans."""
    from pia.tracker import get_plan, list_plans
    if stream_id:
        row = get_plan(stream_id)
        if not row:
            console.print(f"[yellow]No plan for {stream_id}[/yellow]")
            return
        console.print(json.dumps(row, indent=2))
    else:
        console.print(json.dumps(list_plans(profile_id), indent=2))


@cli.command()
@click.option("--profile", "profile_path", required=True, type=click.Path(exists=True, dir_okay=False, path_type=Path),
              help="Path to Profile JSON")
@click.option("--inventory", "inventory_path", default=None,
              type=click.Path(exists=True, dir_okay=False, path_type=Path),
              help="Optional stack inventory JSON or pia-ops markdown (WORK≠personal capital)")
@click.option("--json", "as_json", is_flag=True, default=False, help="Print full brief as JSON")
@click.option(
    "--commitment/--no-commitment",
    default=True,
    show_default=True,
    help="Emit Start/Support/Kill/feasibility/7-day like API commitment path (default ON)",
)
def brief(profile_path: Path, inventory_path: Path | None, as_json: bool, commitment: bool):
    """Build a decision/commitment brief from a saved profile JSON (CoS hub entrypoint)."""
    profile = Profile(**json.loads(profile_path.read_text(encoding="utf-8")))
    if inventory_path is not None:
        inv = load_inventory(inventory_path)
        profile = merge_inventory_into_profile(profile, inv)
        console.print(f"[dim]Merged stack inventory from {inventory_path} "
                      f"({len(profile.stack.assets)} assets)[/dim]")
    streams = load_catalog(CATALOG_DIR)
    brief_data = build_decision_brief(profile, streams)
    artifacts = {"decision_brief.md": brief_data["markdown"]}
    if commitment:
        cb = build_commitment_brief(profile, streams, teaching_intent=False)
        cb_md = render_commitment_markdown(cb)
        cb["markdown"] = cb_md
        brief_data["commitment_brief"] = cb
        brief_data["commitment"] = cb.get("commitment")
        artifacts["commitment_brief.md"] = cb_md
    run_dir = new_run_dir(profile.profile_id)
    if as_json:
        import contextlib
        import io
        with contextlib.redirect_stdout(io.StringIO()):
            export_run(run_dir, artifacts)
        click.echo(json.dumps(brief_data, indent=2))
    else:
        export_run(run_dir, artifacts)
        if commitment and "commitment_brief" in brief_data:
            console.print(brief_data["commitment_brief"]["markdown"])
            console.print(f"[dim]Saved commitment_brief.md + decision_brief.md -> {run_dir}[/dim]")
        else:
            console.print(brief_data["markdown"])
            console.print(f"[dim]Saved decision_brief.md -> {run_dir}[/dim]")


@cli.command("cos-contract")
def cos_contract_cmd():
    """Print the CoS ↔ pia re-brief / tracker contract."""
    console.print(json.dumps(COS_CONTRACT, indent=2))


@cli.command()
def freshness():
    """Print catalog freshness report (stale yields / data_freshness)."""
    streams = load_catalog(CATALOG_DIR)
    report = catalog_freshness_report(streams)
    console.print(f"Catalog streams: {report['total']}  stale: {report['stale_count']}")
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Stream")
    table.add_column("as_of")
    table.add_column("data_freshness")
    table.add_column("Stale")
    for row in report["streams"]:
        stale = "[red]yes[/red]" if row["stale"] else "[green]no[/green]"
        table.add_row(
            row["stream_id"],
            str(row.get("as_of") or ""),
            str(row.get("data_freshness") or ""),
            stale,
        )
    console.print(table)


@cli.command()
@click.option("--host", default="127.0.0.1", show_default=True)
@click.option("--port", default=8000, type=int, show_default=True)
def serve(host, port):
    """Run the local web dashboard."""
    import uvicorn

    uvicorn.run("pia.web.server:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    cli()
