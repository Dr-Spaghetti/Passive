---
name: pia-ai-intake
description: Handle the optional Anthropic-backed natural-language intake and playbooks for the Passive Income Analyzer, including the offline no-key fallback. Use when working with src/pia/ai, .env, ANTHROPIC_API_KEY, or intake/playbook behavior.
---

# PIA AI Intake and Playbooks

Use when reasoning about natural-language intake, customized playbooks, the `ANTHROPIC_API_KEY` flow, or the offline deterministic fallback. Source lives in `src/pia/ai/`.

## How it works

- With a valid `ANTHROPIC_API_KEY` in `.env`, intake and playbook generation can be provider-backed.
- Without a key, the analyzer must fall back to **offline deterministic parsing and playbook data**. This path always works and is the default for hygiene/verification.

## Rules

- `ANTHROPIC_API_KEY` is read from `.env`, which is never committed (`.env.example` is the committed template). Restart the server after adding/removing the key.
- Never hard-code a key, never log it, and never put it in a commit or share link.
- The offline fallback is not "lesser" scheduling simplification: it must produce a valid, deterministic result so the dashboard works with zero external dependencies (README quick start shows a no-key install).
- Any new prompt or playbook template should define a strict structured output schema so parsing does not silently fail; validate against the existing `src/pia/schemas/`.
- Do not let an AI response produce unsupported enum values or numbers outside valid ranges. Clamp and validate before persisting to the tracker/storage.

## Common failure modes and a fix path

1. Call fails because the key is missing: do not change code; check `.env`, restart server.
2. Parsed output does not match `Stream`/`Profile` schemas: fix the prompt/instructions or the schema, then run the schema tests, not ad-hoc coercion.

## Verification

- `python -m pytest -q`
- Start `serve`, hit `http://127.0.0.1:8000/health`; validate a natural-language analyze request with and without a key present (`tests/` cover the no-key playbook fallback).