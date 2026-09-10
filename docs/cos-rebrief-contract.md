# CoS ↔ pia re-brief contract

Educational planning only — not financial advice. Never invent Nick's money numbers.

## Loop

1. Confirm/update Profile JSON (money fields only from Nick).
2. Optional: merge stack inventory: `pia brief --profile PATH --inventory pia-ops/stack/….md`
3. Run `pia brief --profile PATH` or `POST /api/brief` with `{"profile": {...}}`.
4. Present winner + 2 alts with stack why-copy; execute monthly.
5. Log reality: `pia log <stream_id>` or `POST /api/tracker`.
6. Persist plan: `pia plan set` / `POST /api/plan`; weekly `pia drift` / `POST /api/drift`.
7. On drift or goal change → re-brief.

## Rules

- WORK-lane company SaaS/gear is **not** personal capital unless `personal_use_ok`.
- Debt gate active → surplus guidance + risky allocation cap; capital-heavy streams hard-DQ when min > liquid+surplus.
- `pia cos-contract` and `GET /api/cos-contract` print the machine-readable contract.
