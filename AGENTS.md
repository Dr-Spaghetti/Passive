# Passive Income Analyzer - Agent Handoff

Educational planning tool that ranks passive-income stream ideas against capital, time, risk, skills, and constraints. Not financial, legal, or tax advice.

## Repo layout

- `src/pia/` - package
  - `cli.py`, `storage.py`, `tracker.py` - CLI layer and persistence
  - `engine/` - `scorer.py` (fit/RAS/disqualification), `portfolio.py`, `projector.py`
  - `schemas/` - `profile.py`, `stream.py` (the core data models)
  - `ai/` - `intake.py`, `playbooks.py` (optional Anthropic-backed; offline fallback otherwise)
  - `catalog/` - `loader.py` (income-stream catalog)
  - `output/` - `checklist.py`, `exporter.py`, `renderer.py`
  - `web/` - `server.py` (FastAPI dashboard)
- `catalog/`, `docs/`, `tests/` - supporting material
- `.venv/` - virtualenv; entry point `.venv/Scripts/pia.exe`

## Key invariants

- Scoring engine only in `src/pia/engine/scorer.py`. See skill `pia-scoring-invariants`.
- AI intake/playbooks and offline fallback: see skill `pia-ai-intake`.
- Never commit `.env` (holds `ANTHROPIC_API_KEY`).
- Educational scope: no financial/legal/tax advice claims.


## Maximize posture (default ON)

`Profile.maximize_executable_upside` defaults to `True`. Under maximize mode:

- `target_monthly_passive_usd` and `target_deadline_months` are **stretch scoreboard / gap reporting only**.
- They must **not** change ranking order, Start/Support/Kill picks, or soft-penalize `low_ceiling` streams.
- Informational `low_ceiling` flags and feasibility gap % are OK; feasibility `unreachable` becomes `stretch_gap` (illustrative pressure, not a playbook verdict).
- Opt out by setting `maximize_executable_upside: false` on the profile JSON.

CLI: `pia brief --profile …` emits commitment Start/Support/Kill/feasibility/7-day by default (`--no-commitment` for decision-only).

## Common commands

```powershell
.\.venv\Scripts\pia.exe serve
.\.venv\Scripts\pia.exe analyze
.\.venv\Scripts\pia.exe runs
.\.venv\Scripts\pia.exe log <stream>
.\.venv\Scripts\pia.exe drift <stream> --plan-net 25 --plan-hours 1
```

Open `http://127.0.0.1:8000`. `pia serve` launches the dashboard.

## Verification

```powershell
.\.venv\Scripts\python.exe -m pytest -q
Invoke-WebRequest http://127.0.0.1:8000/health
```

`/health` reports server readiness and catalog availability. The web suite covers landing page, valid/invalid analysis, projection scenarios, and the no-key playbook fallback.

## Scope boundaries

Keep the educational framing. Preserve deterministic offline behavior (rankings are reproducible). Do not weaken disqualification logic (maintenance over budget or exclusion matches). Do not add speculative absolute claims about income guarantees.