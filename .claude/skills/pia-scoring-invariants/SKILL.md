---
name: pia-scoring-invariants
description: Apply the canonical scoring engine for the Passive Income Analyzer. Use when tuning, testing, or reasoning about fit score, RAs, effort/yield, disqualification, preferences, or portfolio ranking.
---

# PIA Scoring Invariants

Use whenever a stream's fit score, ranking, or disqualification is in question, or when changing `WEIGHTS` in `src/pia/engine/scorer.py`. The engine is deterministic: same inputs, same outputs. If this skill and the code disagree, the code wins.

## Canonical flow (`score_stream`)

Starting from a `Profile` and a `Stream`:

1. **Disqualification check first.** If `score_maintenance_fit` (hours per month above budget with `return_disqualify=True`) exceeds them, the stream is disqualified outright. Same for a stream that matches any `profile.risk.exclusions` via `exclusions_match`. Disqualified streams never get a fit score.
2. **Eight score factors**, combined with `WEIGHTS` (must sum to 1.0):
   - `capital` 0.18, `maintenance` 0.18, `setup` 0.10, `risk` 0.15, `skill` 0.14, `goal` 0.12, `time_to_dollar` 0.08, `diversification` 0.05
3. **Preference penalties** from `preference_tradeoffs` (public face and customer support) are subtracted from the weighted fit. They lower rank but never turn a stream into an exclusion.
4. **RAS** = `fit * (yield_normalized / (1 + risk_composite))`.
5. **effort_yield** = `(yield * capital / 12) / hours`.

## Ranking (`rank_streams`)

- Streams are scored in order; each qualifying stream adds its `correlation_tags` to `selected_tags`, which feed the next stream's `diversification` factor.
- Sort is `(not disqualified, ras)` descending: qualifying streams first, then by RAS.

## Rules

- Keep `WEIGHTS` summing to exactly 1.0. Changing one necessitates adjusting others, and you must update any snapshot golden values and run the tests.
- Do not change disqualification semantics silently: maintenance over budget and exclusion matches are hard disqualifiers, not soft penalties.
- `score_stream` handles missing data conservatively (`skills_leveraged` empty -> 50; no correlation tags -> 50 for diversification, neutral), so do not special-case None in callers.

## Verification

- `python -m pytest -q` (run with the venv: `.venv/Scripts/python.exe -m pytest -q`)
- Run the web suite: hit `http://127.0.0.1:8000/health` after `serve` and validate an analyze request. See README.
- Reference `tests/` files covering schemas, scoring, portfolio, projector, and tracker.

## Education disclaimer

The tool is an educational planning aid and not financial, legal, or tax advice. Keep that framing in all exported output and UI copy.