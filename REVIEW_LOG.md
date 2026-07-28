# Review Log

## 2026-07-27 - Restored full dashboard surface

### Reference and design decision

The user supplied the latest dashboard screenshot as the visual target. The source showed a dark desktop dashboard with six top-level destinations: Dashboard, New Analysis, Streams, Income Tracker, Past Runs, and Reverse Solver. The implementation restored that information architecture while preserving the existing results, portfolio, and playbook experience behind New Analysis.

### Changes

- Restored a responsive dark dashboard, action-card overview, metric strip, six-destination top navigation, stream browser, income tracker, past-run list, and reverse solver.
- Added web APIs for enriched catalog data, saved runs, tracked income, and reverse-solver results.
- Persisted web analyses into the saved-run store and added `PIA_DB_PATH` support for isolated test deployments.
- Added coverage for the richer stream payload, reverse-solver validation, run persistence, tracker history, and unknown-stream rejection.

### Independent evidence

- `python -m pytest -q --basetemp .test-tmp` completed with **74 passed**.
- In-browser verification at 1720 x 960 confirmed the dashboard, catalog, tracker surface, and reverse-solver result with no final-console errors.
- [design-qa.md](design-qa.md) contains the normalized screenshot comparison and records `final result: passed`.

### Deferred provider check

Live Anthropic intake and provider-generated playbooks remain ready but cannot be truthfully exercised until the user places `ANTHROPIC_API_KEY` in the local `.env` file. The offline parser and static-playbook path remain verified.

## 2026-07-27 - Completion-audit follow-up

### Stack decision

The existing Python/FastAPI dashboard remains the right fit. The requested Agents SDK and AI Elements guidance was assessed, but a React/AI-SDK migration would add an incompatible stack without improving this server-rendered local tool. The implemented local parser preserves useful natural-language intake without an external credential.

### Changes

- Replaced generic +/-20% paper-asset projection multipliers with each catalog stream's evidence-backed bear/base/bull yields in both the web flow and CLI analysis.
- Added a transparent, conservative offline natural-language parser for explicitly stated capital, time, target, deadline, risk, skills, and constraints.
- Exposed the intake source to the UI, corrected the no-key guidance, and added keyboard-operable roles to sidebar and intake mode navigation.

### Adversarial findings and disposition

- **High, resolved:** Scenario projections ignored catalog-specific bear/base/bull yields and could understate or overstate the spread. Explicit scenario yields are now passed per allocation, with projector and endpoint regression coverage.
- **High, resolved:** Natural-language intake was unusable without `ANTHROPIC_API_KEY`, despite the rest of the dashboard being locally functional. The safe offline parser now powers that full flow and is clearly labeled as local parsing.
- **Medium, resolved:** Navigation controls were clickable but not keyboard-semantic. They now expose button roles, focusability, and Enter/Space activation.
- **Deferred by missing credential:** Provider-backed Anthropic extraction and customized provider playbooks still require `ANTHROPIC_API_KEY`; the complete safe offline alternative was exercised instead. No remote provider claim is made without a credential.

### Independent evidence

- `python -m pytest -q --basetemp .test-tmp` completed with **70 passed**.
- `python -m compileall -q src tests` and `git diff --check` completed successfully (only repository line-ending notices).
- Live `/health` returned `{"status":"ok","catalog_streams":36}`.
- In-app browser verification loaded Smart Intake, parsed a realistic description locally into the intended capital, emergency fund, time, target, skills, and constraints; submitted analysis; opened the portfolio with bear/base/bull month-12 values; and opened an offline playbook. Browser console errors were empty.

### Lesson

When an optional LLM capability is unavailable, replace a hard failure with a transparent deterministic path for explicit facts, rather than disguising a degraded mode as AI output.

## 2026-07-27 - Runtime repair and end-to-end verification

### Stack decision

Local Python execution and the in-app browser were selected because this work needed real runtime and UI evidence. Live AI requests were deliberately not attempted without a user-supplied API credential.

### Changes

- Rebuilt the broken local virtual environment and documented the supported install, CLI, server, test, and health-check workflows.
- Added development test dependencies, a `pia serve` command, and a lightweight `/health` endpoint.
- Added validation for invalid financial ranges and negative profile inputs.
- Corrected portfolio projections so every paper allocation uses its own stream yield rather than the first paper stream's yield.
- Added regression and endpoint coverage for analysis, validation, static playbooks, intake validation, the health endpoint, and the weighted projection calculation.

### Adversarial findings and disposition

- **Critical, resolved:** Paper-asset projections applied the first selected paper stream's annual yield to every allocation. The corrected projection sums each allocation's own monthly scenario result; a regression test locks this behavior down.
- **High, resolved:** The checked-in virtual environment referenced a missing Python runtime, preventing tests and local serving. It was rebuilt with the available Python 3.14 runtime and dependencies were reinstalled.
- **High, resolved:** Inverted ranges and negative financial/time values could reach analysis and produce nonsensical inputs. Schema constraints now reject them with a clear validation error.
- **Medium, deferred by missing credential:** Live Anthropic-powered intake and custom playbook generation need `ANTHROPIC_API_KEY`. The safe no-key fallback was tested, but live provider responses cannot be truthfully verified without that credential.
- **Low, accepted framework warning:** The test client emits an upstream FastAPI/HTTPX deprecation warning while all product tests pass. It does not affect application behavior.

### Independent evidence

- `python -m pytest -q --basetemp .test-tmp` completed with **68 passed**.
- `python -m compileall -q src tests` and `git diff --check` completed successfully.
- A real local server returned `/health` as `{"status":"ok","catalog_streams":36}`.
- In the in-app browser, submitting the profile produced **34 qualified** and **2 disqualified** streams; the Portfolio page showed allocation details and a 24-month projection; the Playbooks page showed the expected no-key fallback. Browser console errors were empty.

### Lesson

Portfolio calculations must be tested with allocations that have different yields; otherwise a representative-stream implementation can appear correct while producing materially wrong recommendations.

## 2026-07-27 - Credential configuration and provider-resilience verification

### Changes

- Added the user-supplied Anthropic credential to the git-ignored local `.env`; its value was never logged or displayed.
- Made both AI intake and AI playbooks return the conservative built-in experience if the provider is unavailable, rather than failing a user workflow.
- Added regression tests for provider quota/outage fallbacks and a UI notice that identifies a locally parsed fallback profile.

### Independent evidence

- `python -m pytest -q --basetemp .pytest-tmp-live-20260727-2` completed with **76 passed** (one upstream FastAPI/HTTPX deprecation warning).
- `python -m compileall -q src` and `git diff --check` completed successfully.
- Live Anthropic calls reached the service. The provider reported that the account has insufficient API credit; the app then returned HTTP 200 for both generic test intake and playbook calls, with `intake_source=offline_fallback` and the built-in playbook active.

### Remaining external condition

Provider-generated output cannot be verified until the Anthropic account has API credits. The local application now remains fully usable while that account-level condition persists.

## 2026-07-27 - Closed remaining profile validation gaps

### Changes

- Found that the earlier negative-value validation pass covered `Financial`, `TimeProfile`, and `Range`, but left `ExistingAssets` (brokerage/retirement/rental/digital-product counts), `Audience` counts, `Risk.max_drawdown_tolerance_pct`, and `Constraints.max_platforms` accepting negative or out-of-range values.
- Added `ge=0` (and `le=100` for drawdown tolerance, `ge=1` for max platforms) constraints to those fields so the whole `Profile` schema now rejects nonsensical user input consistently.
- Added four regression tests covering negative existing-asset values, negative audience counts, out-of-range drawdown tolerance, and a zero max-platforms constraint.

### Independent evidence

- `.venv/Scripts/python.exe -m pytest -q --basetemp .test-tmp-resume2` completed with **83 passed** (up from 79; the 4 new tests target the newly-validated fields).
- `.venv/Scripts/python.exe -m compileall -q src tests` and `git diff --check` on the changed files completed with no errors.

## 2026-07-28 - Fixed live Anthropic intake, invalidated by three separate bugs

### Stack decision

The user confirmed the Anthropic account now has usable credits, so the previously-deferred live provider path was exercised directly instead of assumed. It had never actually worked — three independent bugs were masking each other behind the safe offline fallback.

### Adversarial findings and disposition

- **Critical, resolved:** Both `intake.py` and `playbooks.py` called a nonexistent model id (`claude-sonnet-4-6`), which failed every request and was silently swallowed by the safety fallback. Corrected to `claude-sonnet-5`.
- **Critical, resolved:** `response.content[0].text` assumed the first content block was always text, but Claude sometimes emits a `ThinkingBlock` first, raising `AttributeError` and triggering the same silent fallback. Fixed by selecting the block with `type == "text"` in both files.
- **Critical, resolved:** The intake system prompt described the `Profile` schema in prose instead of providing it, so the model invented plausible-but-wrong field names (`"capital"` instead of `liquid_deployable_usd`, `"target_monthly_income"` instead of `financial.target_monthly_passive_usd`, `skills` as a string array instead of a rated object). Pydantic silently dropped the unrecognized keys, so `intake_source` reported `"provider"` while the extracted profile was actually empty defaults. Replaced free-text JSON prompting with a forced tool call whose `input_schema` is `Profile.model_json_schema()` directly, eliminating field-name drift by construction.
- **Medium, resolved:** Even with the tool-use fix, the model occasionally still emits a wrong-type value for a field with nothing to report (e.g. `skills: []`) or an out-of-enum string for a `Literal` field. Added `_coerce_provider_json` to normalize these back to schema defaults instead of failing the whole extraction, plus explicit enum-token instructions in the prompt.

### Independent evidence

- Direct calls to `_provider_intake` (bypassing the app's fallback) reproduced each bug in isolation before the corresponding fix, confirming root cause rather than assuming it.
- After all fixes: 8/8 repeated calls with an ambiguous prompt succeeded; 6/6 across three varied real-world phrasings succeeded; 4/4 direct `_provider_playbook` calls succeeded.
- A full HTTP round trip through the live `pia serve` process (`/api/intake` → `/api/analyze`) correctly extracted capital, monthly target, deadline, and skills from free text and produced a ranked portfolio.
- `.venv/Scripts/python.exe -m pytest -q` completed with **89 passed** (6 new regression tests in `tests/test_intake.py` covering the coercion helper).
- `.venv/Scripts/python.exe -m compileall -q src tests` and `git diff --check` on the changed files completed with no errors.
- `runs/runs.db` was cleared of verification-run rows after testing so the demo starts from an empty run history.
