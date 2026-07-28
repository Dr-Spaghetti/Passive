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

## Verification

```powershell
.\.venv\Scripts\python.exe -m pytest -q
Invoke-WebRequest http://127.0.0.1:8000/health
```

`/health` reports server readiness and catalog availability. The web suite verifies
the landing page, valid and invalid analysis requests, the projection scenarios,
and the no-key playbook fallback.
