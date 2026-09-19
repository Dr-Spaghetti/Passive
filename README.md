# Passive Income Analyzer

An educational planning tool that ranks income-stream ideas against capital, time,
risk, skills, and constraints. It is not financial, legal, or tax advice.

## Quick start

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\pia.exe serve
```

Open `http://127.0.0.1:8000`. The dashboard supports structured and private
offline natural-language intake, ranking, portfolio allocation, scenario
projections, and static playbooks with no API key.

Optional provider-backed intake and customized playbooks use `ANTHROPIC_API_KEY`; copy
`.env.example` to `.env`, add the key, and restart the server. Never commit `.env`.

## CLI

```powershell
.\.venv\Scripts\pia.exe --help
.\.venv\Scripts\pia.exe analyze
.\.venv\Scripts\pia.exe runs
.\.venv\Scripts\pia.exe log hysa
.\.venv\Scripts\pia.exe drift hysa --plan-net 25 --plan-hours 1
```



## Stack inventory (FACT JSON)

Validated JSON is the source of truth for stack-aware scoring. WORK-lane SaaS/gear
is never personal deployable capital unless `personal_use_ok` is confirmed.
Markdown parse remains an optional migration path only.

```bash
# CoS brief with curated inventory
pia brief --profile /path/to/profile.json --inventory /path/to/inventory.json

# CRUD (writes JSON only)
pia inventory list --file stack.json
pia inventory add --file stack.json --name BrightLocal --lane work --status fact --tag seo
pia inventory update --file stack.json --name BrightLocal --no-personal-use-ok
pia inventory import-md --from nick-inventory.md --to nick-inventory.json
```

Sample fixture: `tests/fixtures/nick_stack_inventory.json`. Educational tooling only —
do not invent money, gear, or deploy numbers.

## Maximize posture

By default pia **maximizes executable upside under real constraints**. Dollar
targets (`target_monthly_passive_usd`) and deadlines are optional stretch
scoreboards for gap reporting — they do not demote streams or change
Start/Support/Kill. Set `"maximize_executable_upside": false` on a profile to
restore legacy low-ceiling soft penalties.

```bash
pia brief --profile profiles/nick.template.json
# commitment sections ON by default; use --no-commitment for decision-only
```



## Debt ledger (C2)

Track user-entered high-interest debt balances (educational only — never invents amounts).
Prefer explicit `--balance` entries. Payment-only rows do **not** invent a remaining balance.
When the latest explicit balance is `$0`, the next brief clears the `high_interest_debt_usd`
input path so the debt gate can clear.

```bash
pia debt log --profile-id nick --balance 2500 --notes "statement"
pia debt log --profile-id nick --payment 200 --notes "payment only (no invented remainder)"
pia debt log --profile-id nick --balance 0 --notes "paid off"
pia debt show --profile-id nick

# API
# POST /api/debt  {"profile_id":"nick","balance_usd":0,"notes":"paid off"}
# GET  /api/debt?profile_id=nick
```

## Verification

```powershell
.\.venv\Scripts\python.exe -m pytest -q
Invoke-WebRequest http://127.0.0.1:8000/health
```

`/health` reports server readiness and catalog availability. The web suite verifies
the landing page, valid and invalid analysis requests, the projection scenarios,
and the no-key playbook fallback.
