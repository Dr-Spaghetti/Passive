---
name: pia-scoring-invariants
description: Apply the canonical scoring engine for the Passive Income Analyzer. Use when tuning, testing, or reasoning about fit score, RAs, effort/yield, disqualification, preferences, or portfolio ranking.
---

# PIA Scoring Invariants

Use whenever a stream's fit score, ranking, or disqualification is in question, or when changing `WEIGHTS` in `src/pia/engine/scorer.py`. The engine is deterministic: same inputs, same outputs. If this skill and the code disagree, the code wins.

## Canonical flow (`score_stream`)

Starting from a `Profile` and a `Stream`:

1. **Disqualification check first.** Hard DQs:
   - Maintenance hours/mo above budget (`score_maintenance_fit` with `return_disqualify=True`)
   - Stream matches any `profile.risk.exclusions` via `exclusions_match`
   - **Capital floor:** `deployable_capital < stream.capital_usd.min` → unreachable_capital DQ
   Disqualified streams never get a usable fit/RAS for ranking winners.
2. **Nine score factors**, combined with `WEIGHTS` (must sum to 1.0):
   - `capital` 0.16, `maintenance` 0.16, `setup` 0.09, `risk` 0.13, `skill` 0.12,
     `goal` 0.10, `time_to_dollar` 0.07, `diversification` 0.05, `stack` 0.12
3. **Skill factor** uses multi-skill coverage (max + mean) plus optional `domain_expertise` boost.
4. **Stack factor** matches PERSONAL/PRODUCT (and WORK only if `personal_use_ok`) inventory tags to stream metadata. Company SaaS without `personal_use_ok` does not count as personal capital.
5. **Debt-gate ranking policy** (when `high_interest_debt_usd > 0`): demote capital-at-risk / principal-loss streams; portfolio also caps risky share at 10% and publishes surplus guidance (>=60% paydown educational split).
6. **Preference penalties** from `preference_tradeoffs` (public face and customer support) are subtracted from the weighted fit. They lower rank but never turn a stream into an exclusion.
7. **Maximize posture** (default `Profile.maximize_executable_upside=True`): dollar target / deadline are stretch scoreboard only. Do **not** apply the low_ceiling fit soft-penalty; use a neutral deadline for `score_time_to_first_dollar`. Informational `low_ceiling` flag OK.
8. **RAS** = `fit * (yield_normalized / (1 + risk_composite))`.
9. **effort_yield** = `(yield * capital / 12) / hours`.

## Ranking (`rank_streams`)

- Streams are scored in order; each qualifying stream adds its `correlation_tags` to `selected_tags`, which feed the next stream's `diversification` factor.
- Sort is `(not disqualified, ras)` descending: qualifying streams first, then by RAS.
- Brief `select_options` / commitment `pick_commitment` skip unreachable / prefer stack match. Under maximize they must **not** demote or exclude on `low_ceiling`.

## Rules

- Keep `WEIGHTS` summing to exactly 1.0. Changing one necessitates adjusting others, and you must update any snapshot golden values and run the tests.
- Do not weaken hard disqualifiers: maintenance over budget, exclusion matches, capital below min.
- `score_stream` handles missing data conservatively (`skills_leveraged` empty -> 50; no correlation tags -> 50 for diversification, neutral; empty stack -> modest stack score), so do not special-case None in callers.
- Never invent money numbers; never claim financial advice.

## Verification

- `python -m pytest -q` (venv: `.venv/bin/python -m pytest -q`)
- Run the web suite: hit `http://127.0.0.1:8000/health` after `serve` and validate an analyze request. See README.
- Reference `tests/` files covering schemas, scoring, portfolio, projector, tracker, and `test_abcde_stack_debt.py`.

## Education disclaimer

The tool is an educational planning aid and not financial, legal, or tax advice. Keep that framing in all exported output and UI copy.
