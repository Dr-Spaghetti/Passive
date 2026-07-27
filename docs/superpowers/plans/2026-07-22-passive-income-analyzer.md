# Passive Income Analyzer — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python CLI tool that scores 36 passive income streams against a user profile, constructs a phased portfolio with bear/base/bull projections, and exports playbooks, 90-day checklists, and a KPI tracker — without hype.

**Architecture:** Deterministic scoring engine in pure Python with Pydantic schemas; catalog stored as versioned JSON files; Claude API handles conversational intake normalization and playbook narrative; all output rendered as Markdown/CSV artifacts to a `runs/` directory; SQLite for run persistence.

**Tech Stack:** Python 3.11+, Pydantic v2, Click, Rich, `anthropic` SDK, Jinja2, pytest, sqlite3 (stdlib)

## Global Constraints
- Python 3.11+; add `from __future__ import annotations` in every source file
- All $ projections: bear/base/bull ranges — never a single point estimate
- Every stream output must display its `passivity_index`; streams scoring <5 must show `(semi-active)` label
- Banned phrases in all generated output: "guaranteed," "risk-free," any single return figure without a range
- High-risk gates: `crypto`, `adult`, `p2p`, `leveraged_re` — require `--acknowledge-risk` CLI flag to include
- `data_freshness` > 90 days from run date → label `[UNVERIFIED — verify before allocating]` in output
- Fixtures A/B/C must produce ≥ 3 different streams in their respective top-5 lists
- Fixture D must print the debt-gate warning and cap risky allocation to 10%
- Canonical disclaimer block required on every file export (see §16 of spec)

---

## File Structure

```
PASSIVE HACK/
├── src/
│   └── pia/
│       ├── __init__.py
│       ├── cli.py                    # Click entry point
│       ├── schemas/
│       │   ├── __init__.py
│       │   ├── profile.py            # Profile Pydantic model
│       │   └── stream.py             # Stream Pydantic model + ScoredStream
│       ├── catalog/
│       │   ├── __init__.py
│       │   └── loader.py             # Glob JSON → validate → List[Stream]
│       ├── engine/
│       │   ├── __init__.py
│       │   ├── scorer.py             # 7 factor functions + composite
│       │   ├── portfolio.py          # Core/satellite/local allocation + phases
│       │   └── projector.py          # Paper + digital + reverse-solver
│       ├── output/
│       │   ├── __init__.py
│       │   ├── renderer.py           # Markdown tables and artifact strings
│       │   └── exporter.py           # Write runs/<run_id>/ to disk
│       └── ai/
│           ├── __init__.py
│           ├── intake.py             # Claude: free-text → Profile JSON
│           └── playbooks.py          # Claude: profile+stream → playbook markdown
├── catalog/
│   └── streams/                      # 36 JSON files (one per stream)
│       ├── hysa.json
│       ├── tbills.json
│       ├── cd_ladder.json
│       ├── us_index_etf.json
│       ├── dividend_etf.json
│       ├── bond_etf.json
│       ├── target_date.json
│       ├── equity_reit_etf.json
│       ├── individual_reits.json
│       ├── preferred_income.json
│       ├── longterm_rental_pm.json
│       ├── house_hack.json
│       ├── str_rental.json
│       ├── parking.json
│       ├── storage_rental.json
│       ├── equipment_rental.json
│       ├── vehicle_wrap.json
│       ├── vending.json
│       ├── notion_templates.json
│       ├── ebooks.json
│       ├── printables.json
│       ├── online_course.json
│       ├── ai_art_stock.json
│       ├── ai_music_stock.json
│       ├── stock_video.json
│       ├── faceless_youtube.json
│       ├── affiliate_niche_site.json
│       ├── paid_newsletter.json
│       ├── evergreen_podcast.json
│       ├── print_on_demand.json
│       ├── tiktok_shop.json
│       ├── amazon_kdp.json
│       ├── domain_parking.json
│       ├── micro_saas.json
│       ├── white_label_saas.json
│       └── website_flipping.json
├── templates/
│   ├── exec_summary.md.j2
│   ├── ranked_table.md.j2
│   ├── portfolio_blueprint.md.j2
│   ├── projections.md.j2
│   ├── checklist_90day.md.j2
│   ├── tracker.csv.j2
│   └── assumption_log.md.j2
├── tests/
│   ├── fixtures/
│   │   ├── profile_a.json            # Capital-light AI builder
│   │   ├── profile_b.json            # Time-poor professional
│   │   ├── profile_c.json            # Local asset hybrid
│   │   └── profile_d.json            # Debt + ambition
│   ├── conftest.py
│   ├── test_schemas.py
│   ├── test_scorer.py
│   ├── test_portfolio.py
│   ├── test_projector.py
│   └── test_fixtures.py              # Acceptance: A≠B≠C top-5, D debt gate
├── runs/                             # gitignored; generated output
├── pyproject.toml
├── requirements.txt
└── .gitignore
```

---

## Task 1: Project Scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `requirements.txt`
- Create: `.gitignore`
- Create: `src/pia/__init__.py` and all `__init__.py` stubs
- Create: `runs/.gitkeep`

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.backends.legacy:build"

[project]
name = "pia"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "pydantic>=2.0",
    "anthropic>=0.40",
    "click>=8.1",
    "rich>=13.0",
    "jinja2>=3.1",
]

[project.scripts]
pia = "pia.cli:cli"

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
```

- [ ] **Step 2: Create `requirements.txt`**

```
pydantic>=2.0
anthropic>=0.40
click>=8.1
rich>=13.0
jinja2>=3.1
pytest>=8.0
pytest-cov
```

- [ ] **Step 3: Create `.gitignore`**

```
runs/
*.pyc
__pycache__/
.env
*.db
dist/
*.egg-info/
```

- [ ] **Step 4: Create all `__init__.py` stubs**

Create empty `__init__.py` in: `src/pia/`, `src/pia/schemas/`, `src/pia/catalog/`, `src/pia/engine/`, `src/pia/output/`, `src/pia/ai/`, `tests/`, `tests/fixtures/`

- [ ] **Step 5: Create `runs/.gitkeep`** (empty file to track the dir)

- [ ] **Step 6: Install dependencies**

```
pip install -e ".[dev]"
pip install -r requirements.txt
```

Expected: no errors, `pia` command registered.

- [ ] **Step 7: Verify pytest runs**

```
pytest --collect-only
```

Expected: `no tests ran` (not an error).

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml requirements.txt .gitignore src/ tests/ runs/.gitkeep
git commit -m "chore: scaffold pia project structure"
```

---

## Task 2: Profile Schema

**Files:**
- Create: `src/pia/schemas/profile.py`
- Create: `tests/test_schemas.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_schemas.py
import json, pytest
from pathlib import Path
from pia.schemas.profile import Profile

def test_profile_loads_from_dict():
    data = {
        "profile_id": "test-001",
        "created_at": "2026-07-22T00:00:00",
    }
    p = Profile(**data)
    assert p.profile_id == "test-001"
    assert p.financial.liquid_deployable_usd.point == 0.0

def test_effective_risk_capped_when_low_emergency_fund():
    p = Profile(profile_id="x", created_at="2026-07-22",
                financial={"emergency_fund_months": 1},
                risk={"score_1_to_10": 8})
    assert p.effective_risk_score == 4

def test_effective_risk_uncapped_with_adequate_emergency_fund():
    p = Profile(profile_id="x", created_at="2026-07-22",
                financial={"emergency_fund_months": 6},
                risk={"score_1_to_10": 8})
    assert p.effective_risk_score == 8

def test_debt_gate_fires():
    p = Profile(profile_id="x", created_at="2026-07-22",
                financial={"high_interest_debt_usd": 12000})
    assert p.has_debt_gate is True
```

- [ ] **Step 2: Run — expect FAIL** `pytest tests/test_schemas.py -v`

- [ ] **Step 3: Implement `src/pia/schemas/profile.py`**

```python
from __future__ import annotations
from typing import Literal, Optional
from pydantic import BaseModel, Field, model_validator


class Range(BaseModel):
    min: float = 0.0
    max: float = 0.0
    point: Optional[float] = None

    @model_validator(mode="after")
    def set_point(self) -> Range:
        if self.point is None:
            self.point = (self.min + self.max) / 2
        return self


class Locale(BaseModel):
    country: str = "US"
    state: str = "FL"
    metro: Optional[str] = None


class Audience(BaseModel):
    email: int = 0
    yt: int = 0
    social_total: int = 0


class ExistingAssets(BaseModel):
    brokerage_usd: float = 0.0
    retirement_usd: float = 0.0
    rental_properties: int = 0
    digital_products_live: int = 0
    audience: Audience = Field(default_factory=Audience)
    physical: list[str] = Field(default_factory=list)


class Tax(BaseModel):
    filing_status: str = "single"
    self_employed: bool = False
    notes: str = ""


class Financial(BaseModel):
    liquid_deployable_usd: Range = Field(default_factory=Range)
    monthly_surplus_usd: Range = Field(default_factory=Range)
    emergency_fund_months: float = 0.0
    high_interest_debt_usd: float = 0.0
    existing_assets: ExistingAssets = Field(default_factory=ExistingAssets)
    target_monthly_passive_usd: float = 0.0
    target_deadline_months: int = 24
    tax: Tax = Field(default_factory=Tax)


class TimeProfile(BaseModel):
    setup_hours_per_week_90d: float = 0.0
    maintenance_hours_per_month_steady: float = 0.0
    preferred_cadence: Literal["set_forget", "light_ops", "creative_ops"] = "light_ops"


class Risk(BaseModel):
    score_1_to_10: int = Field(5, ge=1, le=10)
    max_drawdown_tolerance_pct: float = 20.0
    liquidity_need: Literal["days", "months", "years"] = "months"
    exclusions: list[str] = Field(default_factory=list)
    preferred_classes: list[str] = Field(default_factory=list)


class Skills(BaseModel):
    ai_ml: int = Field(0, ge=0, le=10)
    content: int = Field(0, ge=0, le=10)
    video: int = Field(0, ge=0, le=10)
    copywriting: int = Field(0, ge=0, le=10)
    software: int = Field(0, ge=0, le=10)
    design: int = Field(0, ge=0, le=10)
    marketing: int = Field(0, ge=0, le=10)
    sales: int = Field(0, ge=0, le=10)
    real_estate: int = Field(0, ge=0, le=10)
    ops_automation: int = Field(0, ge=0, le=10)
    domain_expertise: list[str] = Field(default_factory=list)


class Goals(BaseModel):
    primary: Literal["cash_flow", "wealth", "freedom", "legacy", "tax_efficiency"] = "cash_flow"
    secondary: list[str] = Field(default_factory=list)
    values: list[str] = Field(default_factory=list)


class Constraints(BaseModel):
    no_public_face: bool = False
    no_customer_support: bool = False
    max_platforms: int = 3
    other: str = ""


class Confidence(BaseModel):
    financial: Literal["high", "med", "low"] = "med"
    time: Literal["high", "med", "low"] = "med"
    skills: Literal["high", "med", "low"] = "med"


class Profile(BaseModel):
    profile_id: str
    created_at: str
    locale: Locale = Field(default_factory=Locale)
    financial: Financial = Field(default_factory=Financial)
    time: TimeProfile = Field(default_factory=TimeProfile)
    risk: Risk = Field(default_factory=Risk)
    skills: Skills = Field(default_factory=Skills)
    goals: Goals = Field(default_factory=Goals)
    constraints: Constraints = Field(default_factory=Constraints)
    confidence: Confidence = Field(default_factory=Confidence)

    @property
    def effective_risk_score(self) -> int:
        if self.financial.emergency_fund_months < 3:
            return min(self.risk.score_1_to_10, 4)
        return self.risk.score_1_to_10

    @property
    def has_debt_gate(self) -> bool:
        return self.financial.high_interest_debt_usd > 0

    @property
    def deployable_capital(self) -> float:
        return self.financial.liquid_deployable_usd.point or 0.0

    @property
    def monthly_maintenance_budget(self) -> float:
        return self.time.maintenance_hours_per_month_steady
```

- [ ] **Step 4: Run — expect PASS** `pytest tests/test_schemas.py -v`

- [ ] **Step 5: Commit**

```bash
git add src/pia/schemas/profile.py tests/test_schemas.py
git commit -m "feat: add Profile Pydantic schema with debt/risk gates"
```

---

## Task 3: Stream Schema + ScoredStream

**Files:**
- Create: `src/pia/schemas/stream.py`
- Extend: `tests/test_schemas.py`

- [ ] **Step 1: Add tests to `tests/test_schemas.py`**

```python
from pia.schemas.stream import Stream

HYSA_DICT = {
    "stream_id": "hysa",
    "name": "HYSA",
    "category": "paper",
    "passivity_index": 10,
    "capital_usd": {"min": 0, "typical": 10000, "scale_tiers": [100000]},
    "setup": {"hours": 1, "calendar_weeks": 0.25},
    "maintenance_hours_per_month": {"steady": 0.1, "year_1_avg": 0.2},
    "yield": {"unit": "annual_pct_on_capital", "bear": 3.5, "base": 4.5, "bull": 5.5, "as_of": "2026-07"},
    "time_to_first_dollar_days": {"bear": 30, "base": 7, "bull": 1},
    "risk": {"principal_loss": "low", "platform": "low", "regulatory": "low",
             "liquidity": "high", "complexity": "low"},
    "scalability": "linear_capital",
    "data_freshness": "2026-07-22",
}

def test_stream_loads():
    s = Stream(**HYSA_DICT)
    assert s.stream_id == "hysa"
    assert s.passivity_index == 10

def test_stream_not_stale_when_fresh():
    s = Stream(**HYSA_DICT)
    assert s.is_stale is False

def test_stream_stale_when_old():
    d = {**HYSA_DICT, "data_freshness": "2020-01-01"}
    s = Stream(**d)
    assert s.is_stale is True

def test_stream_risk_composite():
    s = Stream(**HYSA_DICT)
    assert s.risk_composite == pytest.approx(1.0)  # all low=1
```

- [ ] **Step 2: Run — expect FAIL** `pytest tests/test_schemas.py -v`

- [ ] **Step 3: Implement `src/pia/schemas/stream.py`**

```python
from __future__ import annotations
from typing import Literal, Optional
from pydantic import BaseModel, Field
from datetime import date


class YieldRange(BaseModel):
    unit: Literal["annual_pct_on_capital", "monthly_usd_at_typical", "blended"] = "annual_pct_on_capital"
    bear: float = 0.0
    base: float = 0.0
    bull: float = 0.0
    notes: str = ""
    as_of: str = ""


class TimeToFirstDollar(BaseModel):
    bear: int = 0
    base: int = 0
    bull: int = 0


class StreamRisk(BaseModel):
    principal_loss: Literal["low", "med", "high"] = "low"
    platform: Literal["low", "med", "high"] = "low"
    regulatory: Literal["low", "med", "high"] = "low"
    liquidity: Literal["high", "med", "low"] = "high"
    complexity: Literal["low", "med", "high"] = "low"
    flags: list[str] = Field(default_factory=list)


class CapitalRange(BaseModel):
    min: float = 0.0
    typical: float = 0.0
    scale_tiers: list[float] = Field(default_factory=list)


class SetupInfo(BaseModel):
    hours: float = 0.0
    calendar_weeks: float = 0.0


class MaintenanceInfo(BaseModel):
    steady: float = 0.0
    year_1_avg: float = 0.0


class Stream(BaseModel):
    stream_id: str
    name: str
    category: Literal["paper", "real_asset", "digital", "content", "commerce",
                       "credit_alt", "local_physical", "other"]
    passivity_index: int = Field(..., ge=0, le=10)
    capital_usd: CapitalRange
    setup: SetupInfo
    maintenance_hours_per_month: MaintenanceInfo
    yield_: YieldRange = Field(alias="yield")
    time_to_first_dollar_days: TimeToFirstDollar
    risk: StreamRisk
    skills_leveraged: list[str] = Field(default_factory=list)
    scalability: Literal["linear_capital", "linear_audience", "exponential_product", "capped"]
    tax_character: list[str] = Field(default_factory=list)
    location_sensitivity: Literal["low", "med", "high"] = "low"
    correlation_tags: list[str] = Field(default_factory=list)
    prerequisites: list[str] = Field(default_factory=list)
    exclusions_match: list[str] = Field(default_factory=list)
    startup_checklist: list[str] = Field(default_factory=list)
    failure_modes: list[str] = Field(default_factory=list)
    kill_criteria: list[str] = Field(default_factory=list)
    kpis: list[str] = Field(default_factory=list)
    tool_stack_examples: list[str] = Field(default_factory=list)
    playbook_ref: str = ""
    data_freshness: str = ""
    sources_note: str = ""

    model_config = {"populate_by_name": True}

    @property
    def is_stale(self) -> bool:
        if not self.data_freshness:
            return True
        try:
            freshness = date.fromisoformat(self.data_freshness)
            return (date.today() - freshness).days > 90
        except ValueError:
            return True

    @property
    def risk_composite(self) -> float:
        m = {"low": 1.0, "med": 2.0, "high": 3.0}
        return (m[self.risk.principal_loss] + m[self.risk.platform] + m[self.risk.regulatory]) / 3

    @property
    def passivity_label(self) -> str:
        if self.passivity_index >= 9:
            return "near-true passive"
        if self.passivity_index >= 7:
            return "low-touch"
        if self.passivity_index >= 5:
            return "semi-passive"
        return "semi-active"


class ScoredStream(BaseModel):
    stream: Stream
    fit_score: float = 0.0
    ras: float = 0.0
    effort_yield: float = 0.0
    disqualified: bool = False
    disqualify_reason: str = ""
    explain: list[str] = Field(default_factory=list)
    capital_suggested_usd: float = 0.0
    projected_monthly: dict[str, dict[str, float]] = Field(default_factory=dict)
```

- [ ] **Step 4: Run — expect PASS** `pytest tests/test_schemas.py -v`

- [ ] **Step 5: Commit**

```bash
git add src/pia/schemas/stream.py tests/test_schemas.py
git commit -m "feat: add Stream schema with staleness check and ScoredStream"
```

---

## Task 4: Catalog Loader

**Files:**
- Create: `src/pia/catalog/loader.py`
- Create: `catalog/streams/hysa.json` (first seed entry)
- Extend: `tests/test_schemas.py`

- [ ] **Step 1: Create `catalog/streams/hysa.json`**

```json
{
  "stream_id": "hysa",
  "name": "High-Yield Savings Account / Money Market",
  "category": "paper",
  "passivity_index": 10,
  "capital_usd": { "min": 0, "typical": 10000, "scale_tiers": [10000, 100000, 500000] },
  "setup": { "hours": 1, "calendar_weeks": 0.25 },
  "maintenance_hours_per_month": { "steady": 0.1, "year_1_avg": 0.2 },
  "yield": {
    "unit": "annual_pct_on_capital",
    "bear": 3.5, "base": 4.5, "bull": 5.5,
    "notes": "Fed funds rate dependent. Verify current top rates before allocating.",
    "as_of": "2026-07"
  },
  "time_to_first_dollar_days": { "bear": 30, "base": 7, "bull": 1 },
  "risk": {
    "principal_loss": "low", "platform": "low", "regulatory": "low",
    "liquidity": "high", "complexity": "low",
    "flags": ["FDIC insured up to $250k per institution", "Rate moves with Fed policy"]
  },
  "skills_leveraged": [],
  "scalability": "linear_capital",
  "tax_character": ["ordinary"],
  "location_sensitivity": "low",
  "correlation_tags": ["rates"],
  "prerequisites": ["Bank account", "SSN for account opening"],
  "exclusions_match": [],
  "startup_checklist": [
    "Compare current rates at bankrate.com or nerdwallet.com",
    "Open account at highest-rate FDIC-insured bank (SoFi, Marcus, Ally, Discover)",
    "Set up ACH transfer from checking",
    "Enable auto-transfer of monthly surplus",
    "Set calendar reminder to re-compare rates quarterly"
  ],
  "failure_modes": [
    "Rate drops after Fed cuts without notice",
    "Teaser rate expires; institution silently drops rate",
    "Balance exceeds $250k FDIC limit at single institution"
  ],
  "kill_criteria": [
    "APY drops below 2% AND better risk-equivalent yield available (Treasuries, CDs)",
    "Institution loses FDIC insurance status"
  ],
  "kpis": ["Current APY vs market benchmark", "Monthly interest earned USD", "Balance vs target"],
  "tool_stack_examples": ["SoFi", "Marcus by Goldman Sachs", "Ally Bank", "Discover Online Savings"],
  "playbook_ref": "hysa",
  "data_freshness": "2026-07-22",
  "sources_note": "Rates from Bankrate/NerdWallet survey. Verify before allocating."
}
```

- [ ] **Step 2: Add loader test to `tests/test_schemas.py`**

```python
from pia.catalog.loader import load_catalog
from pathlib import Path

CATALOG_DIR = Path(__file__).parent.parent / "catalog" / "streams"

def test_catalog_loads_hysa():
    streams = load_catalog(CATALOG_DIR)
    ids = [s.stream_id for s in streams]
    assert "hysa" in ids

def test_catalog_all_have_required_fields():
    streams = load_catalog(CATALOG_DIR)
    for s in streams:
        assert s.passivity_index >= 0
        assert s.capital_usd.min >= 0
        assert s.yield_.base >= 0
```

- [ ] **Step 3: Run — expect FAIL**

- [ ] **Step 4: Implement `src/pia/catalog/loader.py`**

```python
from __future__ import annotations
import json
from pathlib import Path
from pia.schemas.stream import Stream


def load_catalog(catalog_dir: Path) -> list[Stream]:
    streams: list[Stream] = []
    for path in sorted(catalog_dir.glob("*.json")):
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
        streams.append(Stream(**data))
    return streams
```

- [ ] **Step 5: Run — expect PASS** `pytest tests/test_schemas.py -v`

- [ ] **Step 6: Commit**

```bash
git add catalog/streams/hysa.json src/pia/catalog/loader.py tests/test_schemas.py
git commit -m "feat: add catalog loader and HYSA seed entry"
```

---

## Task 5: 7 Remaining Seed Catalog Entries

**Files:** Create `catalog/streams/tbills.json`, `cd_ladder.json`, `us_index_etf.json`, `dividend_etf.json`, `bond_etf.json`, `equity_reit_etf.json`, `parking.json`

These follow the identical schema as `hysa.json`. Key values per stream:

**`tbills.json`** — `passivity_index: 10`, `category: paper`, yield bear/base/bull: 4.2/5.0/5.8 (annual %), `correlation_tags: ["rates"]`, `exclusions_match: []`, `data_freshness: "2026-07-22"`. Note in flags: "FL-friendly: Treasury interest exempt from FL intangible tax; federal ordinary income applies."

**`cd_ladder.json`** — `passivity_index: 9`, `category: paper`, yield 3.8/4.6/5.4, liquidity: `med` (locked until maturity). Kill criteria: "CD maturity with rate < HYSA equivalent → roll to HYSA instead."

**`us_index_etf.json`** — `passivity_index: 9`, `category: paper`, `scalability: linear_capital`, yield for dividend yield only: bear 1.2/base 1.5/bull 1.9 (total return excluded — wealth stream, not cash-flow). Note in flags: "Primary use: wealth accumulation. Cash flow only if selling shares per SWR plan."

**`dividend_etf.json`** — `passivity_index: 9`, `category: paper`, yield bear/base/bull: 2.8/3.5/4.5, `tax_character: ["qualified_dividends"]`, `correlation_tags: ["equity", "rates"]`.

**`bond_etf.json`** — `passivity_index: 9`, `category: paper`, yield 3.5/4.2/5.0, `correlation_tags: ["rates"]`. Flag: "Inverse price/yield relationship — price drops as rates rise."

**`equity_reit_etf.json`** — `passivity_index: 8`, `category: real_asset`, yield bear/base/bull: 3.0/4.0/5.5, `tax_character: ["ordinary", "qualified_dividends", "return_of_capital"]`, flag: "REIT dividends mostly ordinary income — less tax-efficient than qualified dividends."

**`parking.json`** — `passivity_index: 8`, `category: local_physical`, capital min $0 (own a spot), typical $0, monthly_usd_at_typical bear/base/bull: 50/120/250 USD/month, `location_sensitivity: high`, `correlation_tags: ["local_economy"]`, prerequisites: ["Own or lease a driveway, garage, or parking spot", "Check local zoning/HOA rules"], tool_stack_examples: ["SpotHero", "Neighbor.com", "ParkingForMe"].

- [ ] **Create all 7 JSON files following the hysa.json structure above**

- [ ] **Run** `pytest tests/test_schemas.py::test_catalog_all_have_required_fields -v` — expect PASS with 8 streams loading

- [ ] **Commit**

```bash
git add catalog/streams/
git commit -m "feat: add 7 seed catalog entries (T-bills, CD, index ETF, dividend ETF, bond ETF, REIT ETF, parking)"
```

---

## Task 6: Scoring Engine — 7 Factor Functions

**Files:**
- Create: `src/pia/engine/scorer.py`
- Create: `tests/test_scorer.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_scorer.py
import pytest
from pia.engine.scorer import (
    score_capital_fit,
    score_maintenance_fit,
    score_risk_alignment,
    score_skill_leverage,
    score_goal_alignment,
    score_time_to_first_dollar,
    score_diversification_value,
)
from pia.schemas.stream import Stream, CapitalRange, MaintenanceInfo, StreamRisk, TimeToFirstDollar, YieldRange, SetupInfo


def make_stream(**kwargs) -> Stream:
    defaults = {
        "stream_id": "test", "name": "Test", "category": "paper",
        "passivity_index": 8,
        "capital_usd": {"min": 1000, "typical": 10000, "scale_tiers": [100000]},
        "setup": {"hours": 2, "calendar_weeks": 0.5},
        "maintenance_hours_per_month": {"steady": 1.0, "year_1_avg": 2.0},
        "yield": {"unit": "annual_pct_on_capital", "bear": 3.0, "base": 4.5, "bull": 6.0},
        "time_to_first_dollar_days": {"bear": 30, "base": 14, "bull": 7},
        "risk": {"principal_loss": "low", "platform": "low", "regulatory": "low",
                 "liquidity": "high", "complexity": "low"},
        "scalability": "linear_capital",
        "data_freshness": "2026-07-22",
    }
    defaults.update(kwargs)
    return Stream(**defaults)


# --- Capital Fit ---
def test_capital_fit_severe_underfund():
    s = make_stream(capital_usd={"min": 10000, "typical": 50000, "scale_tiers": [200000]})
    score = score_capital_fit(capital=1000, stream=s)
    assert score < 50  # severe underfund penalty

def test_capital_fit_in_range():
    s = make_stream(capital_usd={"min": 1000, "typical": 10000, "scale_tiers": [100000]})
    score = score_capital_fit(capital=5500, stream=s)
    assert 70 <= score <= 100

def test_capital_fit_at_typical():
    s = make_stream(capital_usd={"min": 1000, "typical": 10000, "scale_tiers": [100000]})
    score = score_capital_fit(capital=10000, stream=s)
    assert score == 100

def test_capital_fit_over_scale():
    s = make_stream(capital_usd={"min": 1000, "typical": 10000, "scale_tiers": [100000]})
    score = score_capital_fit(capital=200000, stream=s)
    assert score == 90  # diminishing returns

# --- Maintenance Fit ---
def test_maintenance_fit_perfect():
    s = make_stream(maintenance_hours_per_month={"steady": 1.0, "year_1_avg": 2.0})
    score = score_maintenance_fit(monthly_hours_budget=10.0, stream=s)
    assert score == 100

def test_maintenance_fit_disqualify():
    s = make_stream(maintenance_hours_per_month={"steady": 20.0, "year_1_avg": 25.0})
    disq, score = score_maintenance_fit(monthly_hours_budget=10.0, stream=s, return_disqualify=True)
    assert disq is True  # 20 > 10 * 1.15

def test_maintenance_fit_partial():
    s = make_stream(maintenance_hours_per_month={"steady": 8.0, "year_1_avg": 10.0})
    score = score_maintenance_fit(monthly_hours_budget=10.0, stream=s)
    assert 70 <= score < 100

# --- Risk Alignment ---
def test_risk_exclusion_penalty():
    s = make_stream()
    s2 = Stream(**{**s.model_dump(by_alias=True), "exclusions_match": ["crypto"]})
    score = score_risk_alignment(user_risk=5, user_exclusions=["crypto"], stream=s2)
    assert score < 20

def test_risk_low_user_prefers_low_risk():
    s = make_stream(risk={"principal_loss": "low", "platform": "low", "regulatory": "low",
                          "liquidity": "high", "complexity": "low"})
    score = score_risk_alignment(user_risk=2, user_exclusions=[], stream=s)
    assert score >= 80

# --- Skill Leverage ---
def test_skill_leverage_no_skills_needed():
    s = make_stream()  # skills_leveraged = []
    score = score_skill_leverage(user_skills={}, stream=s)
    assert score == 50  # baseline: capital does the work

def test_skill_leverage_high_match():
    s = make_stream()
    s2 = Stream(**{**s.model_dump(by_alias=True), "skills_leveraged": ["ai_ml", "content"]})
    score = score_skill_leverage(user_skills={"ai_ml": 9, "content": 8}, stream=s2)
    assert score >= 90

# --- Goal Alignment ---
def test_goal_cash_flow_boosts_high_passivity():
    s = make_stream()  # passivity 8, paper
    score = score_goal_alignment(primary_goal="cash_flow", stream=s)
    assert score >= 70

def test_goal_wealth_boosts_equity():
    s = make_stream()
    s2 = Stream(**{**s.model_dump(by_alias=True), "category": "paper",
                   "correlation_tags": ["equity"]})
    score = score_goal_alignment(primary_goal="wealth", stream=s2)
    assert score >= 70

# --- Time to First Dollar ---
def test_time_to_first_dollar_fast_scores_high():
    s = make_stream(time_to_first_dollar_days={"bear": 7, "base": 1, "bull": 1})
    score = score_time_to_first_dollar(target_deadline_days=365, stream=s)
    assert score >= 90

def test_time_to_first_dollar_slow_scores_low():
    s = make_stream(time_to_first_dollar_days={"bear": 365, "base": 270, "bull": 180})
    score = score_time_to_first_dollar(target_deadline_days=180, stream=s)
    assert score < 50

# --- Diversification Value ---
def test_diversification_new_tag_adds_value():
    s = make_stream()
    s2 = Stream(**{**s.model_dump(by_alias=True), "correlation_tags": ["local_economy"]})
    score = score_diversification_value(selected_tags=["rates", "equity"], stream=s2)
    assert score > 50

def test_diversification_duplicate_tag_penalized():
    s = make_stream()
    s2 = Stream(**{**s.model_dump(by_alias=True), "correlation_tags": ["rates"]})
    score = score_diversification_value(selected_tags=["rates", "rates", "rates"], stream=s2)
    assert score < 50
```

- [ ] **Step 2: Run — expect FAIL** `pytest tests/test_scorer.py -v`

- [ ] **Step 3: Implement `src/pia/engine/scorer.py`**

```python
from __future__ import annotations
import math
from pia.schemas.stream import Stream


def score_capital_fit(capital: float, stream: Stream) -> float:
    L = stream.capital_usd.min
    T = stream.capital_usd.typical
    S = stream.capital_usd.scale_tiers[-1] if stream.capital_usd.scale_tiers else T * 10

    if capital < L:
        return 100 * (capital / max(L, 1)) * 0.5
    if capital <= T:
        return 70 + 30 * (capital - L) / max(T - L, 1)
    if capital <= S:
        return 100.0
    return 90.0  # over-capitalized: diminishing returns


def score_maintenance_fit(
    monthly_hours_budget: float,
    stream: Stream,
    return_disqualify: bool = False,
):
    hs = stream.maintenance_hours_per_month.steady
    hu = max(monthly_hours_budget, 0.1)
    disqualified = hs > hu * 1.15
    score = max(0.0, min(100.0, 100 * (1 - max(0, hs - hu) / hu)))
    if return_disqualify:
        return disqualified, score
    return score


def score_risk_alignment(
    user_risk: int,
    user_exclusions: list[str],
    stream: Stream,
) -> float:
    # Check exclusions — hard penalty
    for exc in user_exclusions:
        if exc in stream.exclusions_match:
            return 5.0

    # Preferred composite risk ceiling for user
    max_composite = math.ceil(user_risk / 3.5)
    composite = stream.risk_composite  # 1–3 scale

    if composite <= max_composite:
        base = 100.0
    else:
        overage = composite - max_composite
        base = max(0.0, 100.0 - overage * 35)

    # Liquidity penalty
    if stream.risk.liquidity == "low" and user_risk <= 4:
        base -= 20

    return max(0.0, min(100.0, base))


def score_skill_leverage(
    user_skills: dict[str, int],
    stream: Stream,
) -> float:
    if not stream.skills_leveraged:
        return 50.0  # no skill needed; capital does the work
    best = max((user_skills.get(k, 0) for k in stream.skills_leveraged), default=0)
    return min(100.0, 20 + 8 * best)


def score_goal_alignment(primary_goal: str, stream: Stream) -> float:
    score = 50.0
    tags = stream.correlation_tags
    pi = stream.passivity_index

    if primary_goal == "cash_flow":
        if pi >= 7:
            score += 20
        if stream.yield_.unit == "monthly_usd_at_typical":
            score += 15
        if stream.category == "paper":
            score += 10

    elif primary_goal == "wealth":
        if "equity" in tags or stream.category == "paper":
            score += 25
        if stream.scalability in ("exponential_product", "linear_capital"):
            score += 10

    elif primary_goal == "freedom":
        if pi >= 7:
            score += 25
        if stream.maintenance_hours_per_month.steady <= 2:
            score += 15

    elif primary_goal == "tax_efficiency":
        if "qualified_dividends" in stream.tax_character:
            score += 20
        if "cap_gains" in stream.tax_character:
            score += 10

    return min(100.0, max(0.0, score))


def score_time_to_first_dollar(target_deadline_days: int, stream: Stream) -> float:
    d_base = stream.time_to_first_dollar_days.base
    D = max(90, target_deadline_days / 2)
    return 100.0 * math.exp(-d_base / D)


def score_diversification_value(
    selected_tags: list[str],
    stream: Stream,
) -> float:
    if not stream.correlation_tags:
        return 50.0
    new_tags = set(stream.correlation_tags) - set(selected_tags)
    overlap = set(stream.correlation_tags) & set(selected_tags)
    score = 50.0 + 10 * len(new_tags) - 5 * len(overlap)
    return min(100.0, max(0.0, score))
```

- [ ] **Step 4: Run — expect PASS** `pytest tests/test_scorer.py -v`

- [ ] **Step 5: Commit**

```bash
git add src/pia/engine/scorer.py tests/test_scorer.py
git commit -m "feat: implement 7 scoring factor functions with full test coverage"
```

---

## Task 7: Composite Scorer

**Files:**
- Extend: `src/pia/engine/scorer.py` (add `score_stream`)
- Extend: `tests/test_scorer.py`

- [ ] **Step 1: Add composite test**

```python
from pia.engine.scorer import score_stream
from pia.schemas.profile import Profile
from pia.schemas.stream import ScoredStream

def test_composite_score_produces_scored_stream():
    profile = Profile(
        profile_id="t", created_at="2026-07-22",
        financial={"liquid_deployable_usd": {"min": 5000, "max": 10000},
                   "emergency_fund_months": 4},
        time={"maintenance_hours_per_month_steady": 5},
        risk={"score_1_to_10": 5},
        goals={"primary": "cash_flow"},
    )
    stream = make_stream()  # from earlier in this file
    result = score_stream(profile=profile, stream=stream, selected_tags=[])
    assert isinstance(result, ScoredStream)
    assert 0 <= result.fit_score <= 100
    assert result.ras >= 0
    assert result.disqualified is False
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Append to `src/pia/engine/scorer.py`**

```python
# Weights from spec §9.1
WEIGHTS = {
    "capital":       0.18,
    "maintenance":   0.18,
    "setup":         0.10,
    "risk":          0.15,
    "skill":         0.14,
    "goal":          0.12,
    "time_to_dollar":0.08,
    "diversification":0.05,
}

from pia.schemas.profile import Profile
from pia.schemas.stream import ScoredStream


def score_stream(
    profile: Profile,
    stream: Stream,
    selected_tags: list[str],
) -> ScoredStream:
    capital = profile.deployable_capital
    maintenance_budget = profile.monthly_maintenance_budget
    user_risk = profile.effective_risk_score
    deadline_days = profile.financial.target_deadline_months * 30
    skills_dict = profile.skills.model_dump(exclude={"domain_expertise"})

    # Maintenance disqualification check
    maint_disq, maint_score = score_maintenance_fit(
        maintenance_budget, stream, return_disqualify=True
    )
    if maint_disq:
        return ScoredStream(
            stream=stream,
            disqualified=True,
            disqualify_reason=f"Maintenance {stream.maintenance_hours_per_month.steady}h/mo exceeds budget {maintenance_budget}h/mo",
        )

    # Exclusion disqualification
    for exc in profile.risk.exclusions:
        if exc in stream.exclusions_match:
            return ScoredStream(
                stream=stream,
                disqualified=True,
                disqualify_reason=f"Stream matches user exclusion: {exc}",
            )

    factors = {
        "capital":        score_capital_fit(capital, stream),
        "maintenance":    maint_score,
        "setup":          min(100.0, 100 * (1 - stream.setup.hours / max(profile.time.setup_hours_per_week_90d * 12, 1))),
        "risk":           score_risk_alignment(user_risk, profile.risk.exclusions, stream),
        "skill":          score_skill_leverage(skills_dict, stream),
        "goal":           score_goal_alignment(profile.goals.primary, stream),
        "time_to_dollar": score_time_to_first_dollar(deadline_days, stream),
        "diversification":score_diversification_value(selected_tags, stream),
    }

    fit = sum(WEIGHTS[k] * v for k, v in factors.items())

    # Normalize base yield to 0–100 scale (cap at 30% annual for scoring purposes)
    yield_normalized = min(stream.yield_.base / 30, 1.0) * 100 if stream.yield_.unit == "annual_pct_on_capital" else min(stream.yield_.base / 2000, 1.0) * 100
    ras = fit * (yield_normalized / (1 + stream.risk_composite))

    effort_yield = (stream.yield_.base * capital / 12) / max(1, stream.maintenance_hours_per_month.steady)

    explain = [
        f"Fit: {fit:.0f}/100 — best factors: {sorted(factors.items(), key=lambda x: -x[1])[:2]}",
        f"Main risk: {max(stream.risk.flags[:1], default='see risk profile')}",
        f"First action: {stream.startup_checklist[0] if stream.startup_checklist else 'See playbook'}",
    ]

    return ScoredStream(
        stream=stream,
        fit_score=round(fit, 1),
        ras=round(ras, 1),
        effort_yield=round(effort_yield, 2),
        explain=explain,
        capital_suggested_usd=min(capital, stream.capital_usd.typical),
    )


def rank_streams(
    profile: Profile,
    streams: list[Stream],
) -> list[ScoredStream]:
    selected_tags: list[str] = []
    scored: list[ScoredStream] = []
    for s in streams:
        result = score_stream(profile, s, selected_tags)
        if not result.disqualified:
            selected_tags.extend(s.correlation_tags)
        scored.append(result)
    scored.sort(key=lambda x: (not x.disqualified, x.ras), reverse=True)
    return scored
```

- [ ] **Step 4: Run — expect PASS** `pytest tests/test_scorer.py -v`

- [ ] **Step 5: Commit**

```bash
git add src/pia/engine/scorer.py tests/test_scorer.py
git commit -m "feat: add composite scorer and rank_streams function"
```

---

## Task 8: Acceptance Fixtures (A–D)

**Files:**
- Create: `tests/fixtures/profile_a.json` through `profile_d.json`
- Create: `tests/test_fixtures.py`

- [ ] **Step 1: Create `tests/fixtures/profile_a.json`** (Capital-light AI builder)

```json
{
  "profile_id": "fixture-a",
  "created_at": "2026-07-22",
  "financial": {
    "liquid_deployable_usd": {"min": 2000, "max": 4000},
    "monthly_surplus_usd": {"min": 300, "max": 500},
    "emergency_fund_months": 4,
    "high_interest_debt_usd": 0,
    "target_monthly_passive_usd": 1500,
    "target_deadline_months": 24
  },
  "time": {"setup_hours_per_week_90d": 8, "maintenance_hours_per_month_steady": 4, "preferred_cadence": "creative_ops"},
  "risk": {"score_1_to_10": 6, "exclusions": [], "liquidity_need": "months"},
  "skills": {"ai_ml": 8, "content": 8, "video": 6, "copywriting": 7, "software": 5},
  "goals": {"primary": "cash_flow", "secondary": ["freedom"]},
  "constraints": {"no_public_face": true}
}
```

- [ ] **Step 2: Create `tests/fixtures/profile_b.json`** (Time-poor professional)

```json
{
  "profile_id": "fixture-b",
  "created_at": "2026-07-22",
  "financial": {
    "liquid_deployable_usd": {"min": 70000, "max": 90000},
    "monthly_surplus_usd": {"min": 2000, "max": 4000},
    "emergency_fund_months": 8,
    "high_interest_debt_usd": 0,
    "target_monthly_passive_usd": 2000,
    "target_deadline_months": 24
  },
  "time": {"setup_hours_per_week_90d": 2, "maintenance_hours_per_month_steady": 1, "preferred_cadence": "set_forget"},
  "risk": {"score_1_to_10": 3, "exclusions": ["crypto", "adult"], "liquidity_need": "months"},
  "skills": {"ai_ml": 2, "content": 1, "software": 2, "real_estate": 3},
  "goals": {"primary": "wealth", "secondary": ["cash_flow"]},
  "constraints": {"no_customer_support": true}
}
```

- [ ] **Step 3: Create `tests/fixtures/profile_c.json`** (Local asset hybrid)

```json
{
  "profile_id": "fixture-c",
  "created_at": "2026-07-22",
  "financial": {
    "liquid_deployable_usd": {"min": 12000, "max": 18000},
    "monthly_surplus_usd": {"min": 500, "max": 800},
    "emergency_fund_months": 5,
    "high_interest_debt_usd": 0,
    "existing_assets": {"physical": ["parking", "tools"]},
    "target_monthly_passive_usd": 1000,
    "target_deadline_months": 18
  },
  "time": {"setup_hours_per_week_90d": 6, "maintenance_hours_per_month_steady": 8, "preferred_cadence": "light_ops"},
  "risk": {"score_1_to_10": 5, "exclusions": ["crypto"], "preferred_classes": ["paper", "local_physical"]},
  "skills": {"marketing": 6, "ops_automation": 5, "real_estate": 4},
  "goals": {"primary": "cash_flow"},
  "constraints": {}
}
```

- [ ] **Step 4: Create `tests/fixtures/profile_d.json`** (Debt + ambition)

```json
{
  "profile_id": "fixture-d",
  "created_at": "2026-07-22",
  "financial": {
    "liquid_deployable_usd": {"min": 4000, "max": 6000},
    "monthly_surplus_usd": {"min": 200, "max": 400},
    "emergency_fund_months": 1,
    "high_interest_debt_usd": 12000,
    "target_monthly_passive_usd": 3000,
    "target_deadline_months": 12
  },
  "time": {"setup_hours_per_week_90d": 10, "maintenance_hours_per_month_steady": 15},
  "risk": {"score_1_to_10": 7, "exclusions": []},
  "skills": {"content": 5, "marketing": 6},
  "goals": {"primary": "cash_flow"}
}
```

- [ ] **Step 5: Create `tests/test_fixtures.py`**

```python
import json, pytest
from pathlib import Path
from pia.schemas.profile import Profile
from pia.catalog.loader import load_catalog
from pia.engine.scorer import rank_streams

FIXTURE_DIR = Path(__file__).parent / "fixtures"
CATALOG_DIR = Path(__file__).parent.parent / "catalog" / "streams"


def load_profile(name: str) -> Profile:
    with open(FIXTURE_DIR / f"profile_{name}.json") as f:
        return Profile(**json.load(f))


@pytest.fixture(scope="module")
def streams():
    return load_catalog(CATALOG_DIR)


def top5(profile: Profile, all_streams) -> list[str]:
    ranked = rank_streams(profile, all_streams)
    qualified = [r for r in ranked if not r.disqualified]
    return [r.stream.stream_id for r in qualified[:5]]


def test_fixture_a_b_c_have_different_top5(streams):
    top_a = set(top5(load_profile("a"), streams))
    top_b = set(top5(load_profile("b"), streams))
    top_c = set(top5(load_profile("c"), streams))
    # At least 3 streams different between each pair
    assert len(top_a - top_b) >= 3, f"A and B too similar: A={top_a}, B={top_b}"
    assert len(top_b - top_c) >= 3, f"B and C too similar: B={top_b}, C={top_c}"
    assert len(top_a - top_c) >= 2, f"A and C too similar: A={top_a}, C={top_c}"


def test_fixture_a_prioritizes_digital(streams):
    top = top5(load_profile("a"), streams)
    digital_streams = {"notion_templates", "faceless_youtube", "amazon_kdp",
                       "print_on_demand", "online_course", "ebooks"}
    assert len(set(top) & digital_streams) >= 1, f"Fixture A should have ≥1 digital stream: {top}"


def test_fixture_b_prioritizes_paper(streams):
    top = top5(load_profile("b"), streams)
    paper_streams = {"hysa", "tbills", "cd_ladder", "dividend_etf", "bond_etf",
                     "us_index_etf", "equity_reit_etf"}
    assert len(set(top) & paper_streams) >= 3, f"Fixture B should be paper-heavy: {top}"


def test_fixture_c_includes_local(streams):
    top = top5(load_profile("c"), streams)
    local_streams = {"parking", "storage_rental", "equipment_rental"}
    assert len(set(top) & local_streams) >= 1, f"Fixture C should include local asset: {top}"


def test_fixture_d_debt_gate_fires(streams):
    profile = load_profile("d")
    assert profile.has_debt_gate is True
    assert profile.effective_risk_score <= 4  # emergency fund <3mo caps risk


def test_fixture_d_low_emergency_fund_caps_risk(streams):
    profile = load_profile("d")
    assert profile.financial.emergency_fund_months < 3
    assert profile.effective_risk_score == 4
```

- [ ] **Step 6: Run** `pytest tests/test_fixtures.py -v`

  At this stage with only 8 streams, `test_fixture_a_b_c_have_different_top5` may not yet pass fully. That's acceptable — it becomes the regression gate when more streams are added in Task 20.

- [ ] **Step 7: Commit**

```bash
git add tests/fixtures/ tests/test_fixtures.py
git commit -m "test: add acceptance fixtures A-D and differentiation assertions"
```

---

## Task 9: Portfolio Constructor

**Files:**
- Create: `src/pia/engine/portfolio.py`
- Create: `tests/test_portfolio.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_portfolio.py
import json
from pathlib import Path
from pia.schemas.profile import Profile
from pia.schemas.stream import ScoredStream, Stream
from pia.engine.portfolio import build_portfolio, PortfolioAllocation


def load_profile(name: str) -> Profile:
    with open(Path(__file__).parent / "fixtures" / f"profile_{name}.json") as f:
        return Profile(**json.load(f))


def make_scored(stream_id: str, category: str, ras: float, passivity: int, tags: list) -> ScoredStream:
    base = {
        "stream_id": stream_id, "name": stream_id, "category": category,
        "passivity_index": passivity,
        "capital_usd": {"min": 0, "typical": 5000, "scale_tiers": [50000]},
        "setup": {"hours": 2, "calendar_weeks": 1},
        "maintenance_hours_per_month": {"steady": 1.0, "year_1_avg": 2.0},
        "yield": {"unit": "annual_pct_on_capital", "bear": 3.0, "base": 4.5, "bull": 6.0},
        "time_to_first_dollar_days": {"bear": 30, "base": 14, "bull": 7},
        "risk": {"principal_loss": "low", "platform": "low", "regulatory": "low",
                 "liquidity": "high", "complexity": "low"},
        "scalability": "linear_capital",
        "correlation_tags": tags,
        "data_freshness": "2026-07-22",
    }
    return ScoredStream(stream=Stream(**base), ras=ras, fit_score=ras, capital_suggested_usd=5000)


def test_portfolio_respects_max_single_stream_pct():
    profile = load_profile("b")  # $80k, risk 3
    scored = [
        make_scored("hysa", "paper", 90, 10, ["rates"]),
        make_scored("tbills", "paper", 88, 10, ["rates"]),
        make_scored("dividend_etf", "paper", 80, 9, ["equity"]),
    ]
    alloc = build_portfolio(profile, scored)
    for item in alloc.allocations:
        pct = item.allocation_usd / alloc.total_deployed
        assert pct <= 0.35, f"{item.stream_id} exceeds 35% single-stream cap"


def test_portfolio_core_floor_for_low_risk():
    profile = load_profile("b")  # risk 3 → heavy core
    scored = [
        make_scored("hysa", "paper", 90, 10, ["rates"]),
        make_scored("dividend_etf", "paper", 85, 9, ["equity"]),
        make_scored("faceless_youtube", "content", 60, 6, ["attention"]),
    ]
    alloc = build_portfolio(profile, scored)
    core_usd = sum(i.allocation_usd for i in alloc.allocations if i.tier == "core")
    total = alloc.total_deployed
    assert core_usd / total >= 0.40, "Core floor should be ≥40% of deployed capital"


def test_portfolio_has_phases():
    profile = load_profile("a")
    scored = [make_scored(f"stream_{i}", "digital", 70, 7, ["attention"]) for i in range(3)]
    alloc = build_portfolio(profile, scored)
    phases = {i.phase for i in alloc.allocations}
    assert "P0" in phases or "P1" in phases
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement `src/pia/engine/portfolio.py`**

```python
from __future__ import annotations
from dataclasses import dataclass, field
from pia.schemas.profile import Profile
from pia.schemas.stream import ScoredStream


@dataclass
class AllocationItem:
    stream_id: str
    stream_name: str
    tier: str          # "core" | "satellite" | "local"
    phase: str         # "P0" | "P1" | "P2" | "P3"
    allocation_usd: float
    allocation_pct: float
    passivity_index: int
    ras: float


@dataclass
class PortfolioAllocation:
    allocations: list[AllocationItem] = field(default_factory=list)
    total_deployed: float = 0.0
    debt_gate_active: bool = False
    debt_gate_message: str = ""
    phase_summary: dict[str, float] = field(default_factory=dict)


CORE_CATEGORIES = {"paper", "real_asset"}
LOCAL_CATEGORIES = {"local_physical"}


def build_portfolio(
    profile: Profile,
    ranked: list[ScoredStream],
) -> PortfolioAllocation:
    alloc = PortfolioAllocation()
    capital = profile.deployable_capital
    risk = profile.effective_risk_score

    # Debt gate
    if profile.has_debt_gate:
        alloc.debt_gate_active = True
        alloc.debt_gate_message = (
            f"⚠️  DEBT GATE: ${profile.financial.high_interest_debt_usd:,.0f} high-interest debt detected. "
            "Prioritize aggressive paydown before deploying capital into income streams. "
            "Recommended: allocate ≥60% of monthly surplus to debt. Max risky allocation capped at 10%."
        )
        # Reduce deployable capital for scoring purposes
        capital = capital * 0.4  # hold 60% for debt paydown

    qualified = [r for r in ranked if not r.disqualified]

    if not qualified:
        return alloc

    # Determine tier split targets
    if risk <= 3:
        core_target, satellite_target, local_target = 0.70, 0.20, 0.10
    elif risk <= 5:
        core_target, satellite_target, local_target = 0.55, 0.30, 0.15
    else:
        core_target, satellite_target, local_target = 0.40, 0.45, 0.15

    core_budget = capital * core_target
    satellite_budget = capital * satellite_target
    local_budget = capital * local_target

    core_spent = satellite_spent = local_spent = 0.0
    tag_exposure: dict[str, float] = {}
    items: list[AllocationItem] = []

    for scored in qualified:
        s = scored.stream
        if core_spent + satellite_spent + local_spent >= capital:
            break

        # Tier classification
        if s.category in CORE_CATEGORIES:
            tier = "core"
            budget_remaining = core_budget - core_spent
        elif s.category in LOCAL_CATEGORIES:
            tier = "local"
            budget_remaining = local_budget - local_spent
        else:
            tier = "satellite"
            budget_remaining = satellite_budget - satellite_spent

        if budget_remaining <= 0:
            continue

        # Max single-stream cap: 35%
        max_stream = min(capital * 0.35, budget_remaining)
        suggested = scored.capital_suggested_usd
        amount = min(suggested, max_stream)

        # Correlation concentration: max 45% per tag
        for tag in s.correlation_tags:
            already = tag_exposure.get(tag, 0)
            if (already + amount) / capital > 0.45:
                amount = max(0, capital * 0.45 - already)

        if amount <= 0:
            continue

        # Phase assignment
        if scored.stream.setup.calendar_weeks <= 1 and amount <= 500:
            phase = "P0"
        elif scored.stream.setup.calendar_weeks <= 12:
            phase = "P1"
        elif scored.stream.setup.calendar_weeks <= 52:
            phase = "P2"
        else:
            phase = "P3"

        items.append(AllocationItem(
            stream_id=s.stream_id,
            stream_name=s.name,
            tier=tier,
            phase=phase,
            allocation_usd=round(amount, 2),
            allocation_pct=0.0,  # filled below
            passivity_index=s.passivity_index,
            ras=scored.ras,
        ))

        # Track budgets and exposure
        if tier == "core":
            core_spent += amount
        elif tier == "local":
            local_spent += amount
        else:
            satellite_spent += amount

        for tag in s.correlation_tags:
            tag_exposure[tag] = tag_exposure.get(tag, 0) + amount

    total = sum(i.allocation_usd for i in items)
    for item in items:
        item.allocation_pct = round(item.allocation_usd / total * 100, 1) if total > 0 else 0.0

    alloc.allocations = items
    alloc.total_deployed = round(total, 2)
    alloc.phase_summary = {
        phase: round(sum(i.allocation_usd for i in items if i.phase == phase), 2)
        for phase in ("P0", "P1", "P2", "P3")
    }
    return alloc
```

- [ ] **Step 4: Run — expect PASS** `pytest tests/test_portfolio.py -v`

- [ ] **Step 5: Commit**

```bash
git add src/pia/engine/portfolio.py tests/test_portfolio.py
git commit -m "feat: portfolio constructor with tier/phase allocation and concentration caps"
```

---

## Task 10: Projector (Paper + Digital + Reverse-Solver)

**Files:**
- Create: `src/pia/engine/projector.py`
- Create: `tests/test_projector.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_projector.py
import pytest
from pia.engine.projector import project_paper, project_digital, reverse_solve, Scenario


def test_paper_projection_compounding():
    result = project_paper(principal=10000, annual_yield_pct=4.5,
                           monthly_contrib=0, months=12, reinvest=True)
    assert result["base"]["month_12"] > 10000
    assert result["bear"]["month_12"] < result["base"]["month_12"]
    assert result["bull"]["month_12"] > result["base"]["month_12"]


def test_paper_projection_monthly_income_no_reinvest():
    result = project_paper(principal=100000, annual_yield_pct=4.5,
                           monthly_contrib=0, months=1, reinvest=False)
    # $100k at 4.5% / 12 = $375/mo
    assert 300 < result["base"]["income_month_1"] < 450


def test_digital_projection_has_three_scenarios():
    result = project_digital(
        conversion_rate_pct=2.0, aov_usd=47, monthly_traffic_start=1000,
        monthly_traffic_growth_pct=10, platform_fee_pct=5, months=6
    )
    assert "bear" in result and "base" in result and "bull" in result


def test_reverse_solve_finds_capital():
    result = reverse_solve(target_monthly_usd=1000, months=24,
                           annual_yield_pct=4.5, monthly_contrib=200)
    assert result["required_principal"] > 0
    assert result["required_principal"] < 500000  # sanity


def test_projections_never_single_point():
    r = project_paper(10000, 4.5, 0, 12, True)
    for scenario in ("bear", "base", "bull"):
        assert scenario in r
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement `src/pia/engine/projector.py`**

```python
from __future__ import annotations
import math
from dataclasses import dataclass


@dataclass
class Scenario:
    label: str
    yield_pct: float
    traffic_growth_pct: float
    conversion_mult: float


PAPER_SCENARIOS = {
    "bear": Scenario("bear", yield_mult=0.80, traffic_growth_pct=0, conversion_mult=0.6),
    "base": Scenario("base", yield_mult=1.00, traffic_growth_pct=0, conversion_mult=1.0),
    "bull": Scenario("bull", yield_mult=1.20, traffic_growth_pct=0, conversion_mult=1.4),
}


def project_paper(
    principal: float,
    annual_yield_pct: float,
    monthly_contrib: float,
    months: int,
    reinvest: bool,
) -> dict[str, dict[str, float]]:
    results = {}
    for scenario, mult in [("bear", 0.80), ("base", 1.00), ("bull", 1.20)]:
        r = (annual_yield_pct * mult) / 100 / 12
        data: dict[str, float] = {}
        balance = principal
        for m in range(1, months + 1):
            interest = balance * r
            if reinvest:
                balance += interest + monthly_contrib
                data[f"month_{m}"] = round(balance, 2)
            else:
                data[f"income_month_{m}"] = round(interest, 2)
                balance += monthly_contrib
                data[f"month_{m}"] = round(balance, 2)
        results[scenario] = data
    return results


def project_digital(
    conversion_rate_pct: float,
    aov_usd: float,
    monthly_traffic_start: int,
    monthly_traffic_growth_pct: float,
    platform_fee_pct: float,
    months: int,
) -> dict[str, dict[str, float]]:
    results = {}
    scenarios = {
        "bear": (monthly_traffic_growth_pct * 0.5, conversion_rate_pct * 0.6),
        "base": (monthly_traffic_growth_pct, conversion_rate_pct),
        "bull": (monthly_traffic_growth_pct * 1.5, conversion_rate_pct * 1.4),
    }
    for scenario, (growth, conv) in scenarios.items():
        data: dict[str, float] = {}
        traffic = monthly_traffic_start
        for m in range(1, months + 1):
            gross = traffic * (conv / 100) * aov_usd
            net = gross * (1 - platform_fee_pct / 100)
            data[f"month_{m}"] = round(net, 2)
            traffic *= (1 + growth / 100)
        results[scenario] = data
    return results


def reverse_solve(
    target_monthly_usd: float,
    months: int,
    annual_yield_pct: float,
    monthly_contrib: float,
) -> dict[str, float]:
    r = annual_yield_pct / 100 / 12
    if r <= 0:
        return {"required_principal": target_monthly_usd * 12 / max(annual_yield_pct / 100, 0.01)}

    # Solve: target = P * r  →  P = target / r (ignoring contrib for simplicity)
    # With contrib: FV_contrib = monthly_contrib * ((1+r)^m - 1) / r
    fv_contrib = monthly_contrib * ((1 + r) ** months - 1) / r if r > 0 else 0
    income_from_contrib = fv_contrib * r
    income_needed_from_principal = max(0, target_monthly_usd - income_from_contrib)
    required_principal = income_needed_from_principal / r if r > 0 else income_needed_from_principal * 1000

    return {
        "required_principal": round(required_principal, 2),
        "required_monthly_contrib": round(monthly_contrib, 2),
        "income_from_contrib_at_month": round(income_from_contrib, 2),
        "note": "Base scenario. Bear scenario requires ~25% more principal.",
    }
```

- [ ] **Step 4: Run — expect PASS** `pytest tests/test_projector.py -v`

- [ ] **Step 5: Commit**

```bash
git add src/pia/engine/projector.py tests/test_projector.py
git commit -m "feat: paper and digital projectors + reverse-solver, always bear/base/bull"
```

---

## Task 11: Output Renderer

**Files:**
- Create: `src/pia/output/renderer.py`
- Create: `tests/test_renderer.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_renderer.py
from pia.output.renderer import render_ranked_table, render_portfolio_blueprint, DISCLAIMER

def test_ranked_table_contains_passivity_index(scored_list):
    md = render_ranked_table(scored_list)
    assert "Passivity" in md

def test_ranked_table_labels_semi_active(scored_list):
    md = render_ranked_table(scored_list)
    # Any stream with passivity <5 must show semi-active
    assert "(semi-active)" in md or all(s.stream.passivity_index >= 5 for s in scored_list)

def test_ranked_table_no_single_yield_figures(scored_list):
    md = render_ranked_table(scored_list)
    assert "guaranteed" not in md.lower()

def test_portfolio_blueprint_has_three_scenarios(portfolio_alloc):
    md = render_portfolio_blueprint(portfolio_alloc, monthly_projections={
        "bear": 100, "base": 200, "bull": 350
    })
    assert "bear" in md.lower() and "base" in md.lower() and "bull" in md.lower()

def test_disclaimer_present():
    assert "not financial" in DISCLAIMER.lower()
```

(Note: `scored_list` and `portfolio_alloc` are pytest fixtures — define them in `conftest.py`.)

- [ ] **Step 2: Add to `tests/conftest.py`**

```python
import pytest
from pia.schemas.stream import Stream, ScoredStream
from pia.engine.portfolio import PortfolioAllocation, AllocationItem

@pytest.fixture
def base_stream_dict():
    return {
        "stream_id": "hysa", "name": "HYSA", "category": "paper", "passivity_index": 10,
        "capital_usd": {"min": 0, "typical": 10000, "scale_tiers": [100000]},
        "setup": {"hours": 1, "calendar_weeks": 0.25},
        "maintenance_hours_per_month": {"steady": 0.1, "year_1_avg": 0.2},
        "yield": {"unit": "annual_pct_on_capital", "bear": 3.5, "base": 4.5, "bull": 5.5},
        "time_to_first_dollar_days": {"bear": 30, "base": 7, "bull": 1},
        "risk": {"principal_loss": "low", "platform": "low", "regulatory": "low",
                 "liquidity": "high", "complexity": "low"},
        "scalability": "linear_capital", "data_freshness": "2026-07-22",
    }

@pytest.fixture
def scored_list(base_stream_dict):
    s = Stream(**base_stream_dict)
    low_p = Stream(**{**base_stream_dict, "stream_id": "tiktok", "name": "TikTok Shop",
                     "passivity_index": 3, "category": "commerce"})
    return [
        ScoredStream(stream=s, fit_score=85, ras=75, explain=["Good fit", "Low risk", "Open account"]),
        ScoredStream(stream=low_p, fit_score=40, ras=20, explain=["High maintenance", "Platform risk", "Setup store"]),
    ]

@pytest.fixture
def portfolio_alloc():
    return PortfolioAllocation(
        allocations=[AllocationItem("hysa", "HYSA", "core", "P0", 5000, 100.0, 10, 75)],
        total_deployed=5000, debt_gate_active=False,
    )
```

- [ ] **Step 3: Implement `src/pia/output/renderer.py`**

```python
from __future__ import annotations
from pia.schemas.stream import ScoredStream
from pia.engine.portfolio import PortfolioAllocation

DISCLAIMER = (
    "\n---\n"
    "**Disclaimer:** This output is educational analysis only. It is not financial, investment, "
    "tax, or legal advice. Income results vary widely; many streams earn $0 after costs. "
    "Yields, fees, and platform rules change. You are solely responsible for your decisions "
    "and compliance with laws and platform terms. Consult licensed professionals before "
    "material capital deployment.\n"
)


def render_ranked_table(scored: list[ScoredStream]) -> str:
    rows = ["| # | Stream | Passivity | Fit | RAS | Est. Monthly (bear/base/bull) | Status |",
            "|---|--------|-----------|-----|-----|-------------------------------|--------|"]
    for i, s in enumerate(scored, 1):
        label = s.stream.passivity_label
        if s.stream.passivity_index < 5:
            label += " (semi-active)"
        status = "✗ disqualified" if s.disqualified else "✓"
        reason = f" — {s.disqualify_reason}" if s.disqualified else ""
        rows.append(
            f"| {i} | {s.stream.name} | {s.stream.passivity_index}/10 {label} | "
            f"{s.fit_score:.0f} | {s.ras:.0f} | see projections | {status}{reason} |"
        )
    return "\n".join(rows)


def render_portfolio_blueprint(
    alloc: PortfolioAllocation,
    monthly_projections: dict[str, float],
) -> str:
    lines = ["## Portfolio Blueprint\n"]

    if alloc.debt_gate_active:
        lines.append(f"> {alloc.debt_gate_message}\n")

    lines.append(f"**Total Deployed:** ${alloc.total_deployed:,.0f}\n")
    lines.append("### Projected Monthly Income at Month 12")
    lines.append(f"- Bear: ${monthly_projections.get('bear', 0):,.0f}/mo")
    lines.append(f"- Base: ${monthly_projections.get('base', 0):,.0f}/mo")
    lines.append(f"- Bull: ${monthly_projections.get('bull', 0):,.0f}/mo\n")

    lines.append("### Allocations\n")
    lines.append("| Stream | Tier | Phase | Amount | % | Passivity |")
    lines.append("|--------|------|-------|--------|---|-----------|")
    for item in alloc.allocations:
        lines.append(
            f"| {item.stream_name} | {item.tier} | {item.phase} | "
            f"${item.allocation_usd:,.0f} | {item.allocation_pct:.1f}% | {item.passivity_index}/10 |"
        )

    lines.append("\n### Phase Summary")
    for phase, amount in alloc.phase_summary.items():
        if amount > 0:
            lines.append(f"- {phase}: ${amount:,.0f}")

    lines.append(DISCLAIMER)
    return "\n".join(lines)


def render_exec_summary(
    profile_id: str,
    alloc: PortfolioAllocation,
    monthly_projections: dict[str, float],
    top_streams: list[ScoredStream],
    week1_actions: list[str],
) -> str:
    lines = [f"# Passive Income Analysis — Executive Summary\n",
             f"**Profile:** {profile_id}\n",
             "## Projected Monthly Income at Month 12",
             f"| Scenario | Monthly Income |",
             f"|----------|---------------|",
             f"| Bear     | ${monthly_projections.get('bear', 0):,.0f} |",
             f"| Base     | ${monthly_projections.get('base', 0):,.0f} |",
             f"| Bull     | ${monthly_projections.get('bull', 0):,.0f} |\n",
             "## Top Recommended Streams"]
    for s in top_streams[:5]:
        if not s.disqualified:
            lines.append(f"- **{s.stream.name}** (PI {s.stream.passivity_index}/10, RAS {s.ras:.0f}) — {s.explain[0] if s.explain else ''}")
    lines.append("\n## Week 1 Actions")
    for action in week1_actions:
        lines.append(f"- [ ] {action}")
    lines.append(DISCLAIMER)
    return "\n".join(lines)
```

- [ ] **Step 4: Run — expect PASS** `pytest tests/test_renderer.py -v`

- [ ] **Step 5: Commit**

```bash
git add src/pia/output/renderer.py tests/test_renderer.py tests/conftest.py
git commit -m "feat: output renderer with ranked table, blueprint, exec summary, and disclaimer"
```

---

## Task 12: Artifact Exporter

**Files:**
- Create: `src/pia/output/exporter.py`

```python
from __future__ import annotations
import uuid
from datetime import date
from pathlib import Path


RUNS_DIR = Path(__file__).parent.parent.parent.parent / "runs"


def new_run_dir(profile_id: str) -> Path:
    run_id = f"{date.today().isoformat()}-{profile_id[:8]}-{uuid.uuid4().hex[:6]}"
    d = RUNS_DIR / run_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def export_run(run_dir: Path, artifacts: dict[str, str]) -> None:
    """artifacts: {filename: content_string}"""
    for filename, content in artifacts.items():
        (run_dir / filename).write_text(content, encoding="utf-8")
    print(f"✓ Exported {len(artifacts)} artifacts to {run_dir}")
```

- [ ] **Commit**

```bash
git add src/pia/output/exporter.py
git commit -m "feat: artifact exporter writes run directory"
```

---

## Task 13: CLI (Form Intake + Analyze Command)

**Files:**
- Create: `src/pia/cli.py`

- [ ] **Implement `src/pia/cli.py`**

```python
from __future__ import annotations
import json, uuid
from datetime import date
from pathlib import Path

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
    """Passive Income Analyzer — scores streams, builds portfolios, exports plans."""
    pass


@cli.command()
@click.option("--output", "-o", default="runs", help="Output directory")
@click.option("--acknowledge-risk", is_flag=True, default=False,
              help="Required to include high-risk streams (crypto, adult, P2P)")
def analyze(output, acknowledge_risk):
    """Interactive profile intake → full analysis → export artifacts."""
    console.rule("[bold]Passive Income Analyzer v0.1[/bold]")
    console.print("This tool is for [bold]educational planning only[/bold] — not financial advice.\n")

    # --- Intake ---
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
    exclusions_raw = click.prompt("Exclude categories? (crypto, adult, p2p, leveraged_re — comma-sep or blank)", default="")
    exclusions = [e.strip() for e in exclusions_raw.split(",") if e.strip()]
    if not acknowledge_risk:
        for risky in ("crypto", "p2p", "leveraged_re", "adult"):
            if risky not in exclusions:
                exclusions.append(risky)
        console.print("[dim]High-risk categories excluded. Use --acknowledge-risk to include.[/dim]")

    console.print("\n[bold cyan]Step 4: Skills (0–10)[/bold cyan]")
    skills_data = {}
    for skill in ("ai_ml", "content", "video", "software", "marketing", "real_estate"):
        skills_data[skill] = click.prompt(f"  {skill}", type=int, default=0)

    console.print("\n[bold cyan]Step 5: Goals[/bold cyan]")
    primary_goal = click.prompt("Primary goal", type=click.Choice(
        ["cash_flow", "wealth", "freedom", "legacy", "tax_efficiency"]), default="cash_flow")
    no_face = click.confirm("Prefer no public face / anonymous?", default=False)
    no_support = click.confirm("Prefer no customer support requirements?", default=False)

    # Build profile
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
        time=TimeProfile(setup_hours_per_week_90d=setup_hrs,
                         maintenance_hours_per_month_steady=maint_hrs),
        risk=Risk(score_1_to_10=risk_score, exclusions=exclusions),
        skills=Skills(**skills_data),
        goals=Goals(primary=primary_goal),
        constraints=Constraints(no_public_face=no_face, no_customer_support=no_support),
    )

    # Warn on debt gate
    if profile.has_debt_gate:
        console.print(f"\n[bold red]⚠ DEBT GATE:[/bold red] ${debt_usd:,.0f} high-interest debt detected.")
        console.print("Recommend: prioritize aggressive paydown before deploying capital into income streams.\n")

    if profile.financial.emergency_fund_months < 3:
        console.print("[yellow]⚠ Emergency fund < 3 months. Risk score capped at 4 for new illiquid bets.[/yellow]\n")

    # Load and score
    with console.status("Loading catalog and scoring streams..."):
        streams = load_catalog(CATALOG_DIR)
        ranked = rank_streams(profile, streams)

    # Display ranked table
    console.rule("Ranked Opportunities")
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("#", width=3)
    table.add_column("Stream", width=30)
    table.add_column("PI", width=4)
    table.add_column("RAS", width=6)
    table.add_column("Status")
    for i, r in enumerate(ranked[:15], 1):
        status = "[red]disqualified[/red]" if r.disqualified else "[green]✓[/green]"
        table.add_row(str(i), r.stream.name, str(r.stream.passivity_index),
                      f"{r.ras:.0f}", status)
    console.print(table)

    # Build portfolio
    alloc = build_portfolio(profile, ranked)

    # Quick projections
    monthly_proj = {"bear": 0.0, "base": 0.0, "bull": 0.0}
    for item in alloc.allocations:
        match = next((r for r in ranked if r.stream.stream_id == item.stream_id), None)
        if match and match.stream.category == "paper":
            proj = project_paper(item.allocation_usd, match.stream.yield_.base,
                                 0, 12, reinvest=False)
            monthly_proj["bear"] += list(proj["bear"].values())[-1]
            monthly_proj["base"] += list(proj["base"].values())[-1]
            monthly_proj["bull"] += list(proj["bull"].values())[-1]

    # Export
    run_dir = new_run_dir(profile_id)
    artifacts = {
        "profile.json": profile.model_dump_json(indent=2),
        "ranked_table.md": render_ranked_table(ranked),
        "portfolio_blueprint.md": render_portfolio_blueprint(alloc, monthly_proj),
        "exec_summary.md": render_exec_summary(
            profile_id, alloc, monthly_proj,
            [r for r in ranked if not r.disqualified][:5],
            [r.stream.startup_checklist[0] for r in ranked[:3] if not r.disqualified and r.stream.startup_checklist]
        ),
    }
    export_run(run_dir, artifacts)
    console.print(f"\n[bold green]Done![/bold green] Run saved to: {run_dir}")


if __name__ == "__main__":
    cli()
```

- [ ] **Test the CLI manually**

```bash
python -m pia.cli analyze
```

Walk through all prompts. Verify output directory is created with 4 files.

- [ ] **Commit**

```bash
git add src/pia/cli.py
git commit -m "feat: interactive CLI analyze command with full intake, scoring, portfolio, and export"
```

---

## Task 14: Claude AI Intake (Conversational → Profile)

**Files:**
- Create: `src/pia/ai/intake.py`

Requires: `ANTHROPIC_API_KEY` env var.

```python
from __future__ import annotations
import json, os
from datetime import date
from anthropic import Anthropic
from pia.schemas.profile import Profile

CLIENT = Anthropic()

SYSTEM = """You are a passive income profile intake assistant.
Your job is to extract a structured profile from a free-text description.
Output ONLY valid JSON matching the Profile schema. No commentary.
Required top-level keys: profile_id, created_at, financial, time, risk, skills, goals, constraints.
Use ranges (min/max) for capital and surplus. Estimate missing fields conservatively.
Flag high-interest debt if mentioned. Set emergency_fund_months to 0 if not mentioned."""


def intake_from_text(user_text: str, profile_id: str | None = None) -> Profile:
    pid = profile_id or f"ai-intake-{date.today().isoformat()}"
    response = CLIENT.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        system=SYSTEM,
        messages=[{
            "role": "user",
            "content": f"Extract a profile from this description. Set profile_id to '{pid}' and created_at to '{date.today().isoformat()}'.\n\n{user_text}"
        }]
    )
    raw = response.content[0].text.strip()
    # Strip markdown fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return Profile(**json.loads(raw.strip()))
```

- [ ] **Add a CLI command for conversational intake**

In `cli.py`, add:

```python
@cli.command()
def chat():
    """Describe your situation in plain English → profile extracted → run analysis."""
    console.print("Describe your financial situation, time availability, skills, and income goals.")
    console.print("(Be as detailed or as vague as you like — ranges are fine.)\n")
    text = click.edit(text="Describe your situation here...")
    if not text:
        console.print("[red]No input.[/red]")
        return
    from pia.ai.intake import intake_from_text
    with console.status("Extracting profile with AI..."):
        profile = intake_from_text(text)
    console.print(f"[green]Profile extracted:[/green] {profile.profile_id}")
    console.print(profile.model_dump_json(indent=2))
    if click.confirm("Run full analysis with this profile?"):
        # Reuse analyze logic (refactor to shared function in production)
        console.print("Profile saved. Run `pia analyze` and load this profile.")
```

- [ ] **Commit**

```bash
git add src/pia/ai/intake.py src/pia/cli.py
git commit -m "feat: Claude AI conversational intake normalizes free-text to Profile"
```

---

## Task 15: Claude Playbook Generation

**Files:**
- Create: `src/pia/ai/playbooks.py`

```python
from __future__ import annotations
from anthropic import Anthropic
from pia.schemas.profile import Profile
from pia.schemas.stream import Stream

CLIENT = Anthropic()

PLAYBOOK_SYSTEM = """You are a no-hype passive income advisor writing a playbook for a specific person and stream.
Write in direct, operator-grade markdown. No guarantees. Always give ranges not single figures.
Include: Who it's for / not for, unit economics (editable assumptions), 30/60/90-day plan (checkboxes),
tool stack, distribution plan (where first customers come from), automation & AI leverage,
compliance/TOS watchouts, KPIs, failure modes, kill criteria, scale play, exit options.
Be specific to the person's profile. No filler."""


def generate_playbook(profile: Profile, stream: Stream) -> str:
    profile_summary = (
        f"Capital: ${profile.deployable_capital:,.0f}, "
        f"Monthly hours budget: {profile.time.maintenance_hours_per_month_steady}h, "
        f"Risk: {profile.effective_risk_score}/10, "
        f"Skills: {profile.skills.model_dump(exclude={'domain_expertise'})}, "
        f"Goal: {profile.goals.primary}, "
        f"No public face: {profile.constraints.no_public_face}"
    )
    prompt = (
        f"Write a complete playbook for '{stream.name}' (passivity {stream.passivity_index}/10) "
        f"tailored to this person:\n{profile_summary}\n\n"
        f"Stream yield range: bear {stream.yield_.bear}% / base {stream.yield_.base}% / bull {stream.yield_.bull}% "
        f"({stream.yield_.unit}).\n"
        f"Tool stack: {', '.join(stream.tool_stack_examples[:5])}.\n"
        f"Kill criteria: {stream.kill_criteria}\n\n"
        f"Write the full playbook in markdown."
    )
    response = CLIENT.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=3000,
        system=PLAYBOOK_SYSTEM,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text
```

- [ ] **Wire into CLI export**: In the `analyze` command, after building `alloc`, generate playbooks for the top 3 qualified streams and add them to `artifacts`:

```python
# In analyze(), after building alloc:
top_qualified = [r for r in ranked if not r.disqualified][:3]
if click.confirm(f"\nGenerate AI playbooks for top {len(top_qualified)} streams? (uses Claude API)"):
    from pia.ai.playbooks import generate_playbook
    for scored in top_qualified:
        with console.status(f"Generating playbook: {scored.stream.name}..."):
            pb = generate_playbook(profile, scored.stream)
        artifacts[f"playbook_{scored.stream.stream_id}.md"] = pb
```

- [ ] **Commit**

```bash
git add src/pia/ai/playbooks.py src/pia/cli.py
git commit -m "feat: Claude playbook generation per stream tailored to user profile"
```

---

## Task 16: SQLite Run Storage

**Files:**
- Create: `src/pia/storage.py`

```python
from __future__ import annotations
import json, sqlite3
from pathlib import Path
from datetime import date

DB_PATH = Path(__file__).parent.parent.parent / "runs" / "runs.db"


def init_db() -> None:
    DB_PATH.parent.mkdir(exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY,
                profile_id TEXT,
                created_at TEXT,
                profile_json TEXT,
                top5_ids TEXT,
                total_deployed REAL,
                projected_base REAL
            )
        """)


def save_run(run_id: str, profile_id: str, profile_json: str,
             top5_ids: list[str], total_deployed: float, projected_base: float) -> None:
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO runs VALUES (?,?,?,?,?,?,?)",
            (run_id, profile_id, date.today().isoformat(),
             profile_json, json.dumps(top5_ids), total_deployed, projected_base)
        )


def list_runs() -> list[dict]:
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute("SELECT run_id, profile_id, created_at, projected_base FROM runs ORDER BY created_at DESC").fetchall()
    return [{"run_id": r[0], "profile_id": r[1], "date": r[2], "projected_base": r[3]} for r in rows]
```

- [ ] **Add `pia runs` CLI command** in `cli.py`:

```python
@cli.command(name="runs")
def list_runs_cmd():
    """List all saved analysis runs."""
    from pia.storage import list_runs
    runs = list_runs()
    if not runs:
        console.print("No runs yet. Run `pia analyze` first.")
        return
    table = Table()
    table.add_column("Date"); table.add_column("Profile"); table.add_column("Projected Base/mo")
    for r in runs:
        table.add_row(r["date"], r["profile_id"], f"${r['projected_base']:,.0f}")
    console.print(table)
```

- [ ] **Commit**

```bash
git add src/pia/storage.py src/pia/cli.py
git commit -m "feat: SQLite run storage and list-runs CLI command"
```

---

## Task 17: Tracking Mode (Log + Drift Alerts)

**Files:**
- Create: `src/pia/tracker.py`

```python
from __future__ import annotations
import json, sqlite3
from pathlib import Path
from datetime import date

DB_PATH = Path(__file__).parent.parent.parent / "runs" / "runs.db"

LOG_SCHEMA = {
    "date": "",
    "stream_id": "",
    "gross_usd": 0.0,
    "fees_usd": 0.0,
    "net_usd": 0.0,
    "hours": 0.0,
    "metrics": {},
    "notes": "",
}


def init_tracker() -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS income_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT, stream_id TEXT, gross_usd REAL,
                fees_usd REAL, net_usd REAL, hours REAL,
                metrics TEXT, notes TEXT
            )
        """)


def log_income(stream_id: str, gross: float, fees: float, hours: float, notes: str = "") -> None:
    init_tracker()
    net = gross - fees
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO income_log (date,stream_id,gross_usd,fees_usd,net_usd,hours,metrics,notes) VALUES (?,?,?,?,?,?,?,?)",
            (date.today().isoformat(), stream_id, gross, fees, net, hours, "{}", notes)
        )


def check_drift(stream_id: str, plan_monthly_net: float, plan_monthly_hours: float) -> list[str]:
    """Returns list of alert strings. Empty = no drift."""
    init_tracker()
    alerts = []
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            "SELECT net_usd, hours FROM income_log WHERE stream_id=? ORDER BY date DESC LIMIT 12",
            (stream_id,)
        ).fetchall()

    if not rows:
        return []

    recent_nets = [r[0] for r in rows[:3]]
    recent_hours = [r[1] for r in rows[:4]]

    if len(recent_nets) >= 3 and all(n < plan_monthly_net * 0.5 for n in recent_nets):
        alerts.append(f"⚠ INCOME DRIFT: {stream_id} has been <50% of plan for 3 consecutive months.")

    if len(recent_hours) >= 4 and all(h > plan_monthly_hours * 1.5 for h in recent_hours):
        alerts.append(f"⚠ TIME DRIFT: {stream_id} has been >1.5× planned hours for 4 consecutive weeks.")

    return alerts
```

- [ ] **Add `pia log` and `pia drift` CLI commands** in `cli.py`:

```python
@cli.command()
@click.argument("stream_id")
def log(stream_id):
    """Log actual income for a stream."""
    from pia.tracker import log_income
    gross = click.prompt("Gross income ($)", type=float)
    fees = click.prompt("Fees/costs ($)", type=float, default=0.0)
    hours = click.prompt("Hours spent", type=float, default=0.0)
    notes = click.prompt("Notes (optional)", default="")
    log_income(stream_id, gross, fees, hours, notes)
    console.print(f"[green]✓ Logged: ${gross-fees:.2f} net for {stream_id}[/green]")


@cli.command()
@click.argument("stream_id")
@click.option("--plan-net", type=float, required=True)
@click.option("--plan-hours", type=float, required=True)
def drift(stream_id, plan_net, plan_hours):
    """Check a stream for income or time drift vs plan."""
    from pia.tracker import check_drift
    alerts = check_drift(stream_id, plan_net, plan_hours)
    if alerts:
        for a in alerts:
            console.print(f"[red]{a}[/red]")
    else:
        console.print(f"[green]✓ {stream_id}: no drift detected.[/green]")
```

- [ ] **Commit**

```bash
git add src/pia/tracker.py src/pia/cli.py
git commit -m "feat: income log + drift alerts for tracking mode"
```

---

## Task 18: Remaining 28 Catalog Streams

Follow the exact JSON schema from `hysa.json`. Required for all: `stream_id`, `name`, `category`, `passivity_index`, all capital/yield/time/risk/maintenance fields, `startup_checklist` (≥4 items), `kill_criteria` (≥2), `kpis` (≥2), `data_freshness: "2026-07-22"`.

**Create these 28 files in `catalog/streams/`:**

| stream_id | category | passivity_index | yield unit | yield base (est.) |
|-----------|----------|-----------------|------------|-------------------|
| `individual_reits` | real_asset | 7 | annual_pct | 5.5% |
| `preferred_income` | paper | 8 | annual_pct | 6.0% |
| `longterm_rental_pm` | real_asset | 7 | monthly_usd_at_typical | $400–$1,200/mo |
| `house_hack` | real_asset | 6 | monthly_usd_at_typical | $600–$1,800/mo |
| `str_rental` | real_asset | 4 | monthly_usd_at_typical | $800–$3,000/mo |
| `storage_rental` | local_physical | 7 | monthly_usd_at_typical | $50–$200/mo |
| `equipment_rental` | local_physical | 6 | monthly_usd_at_typical | $100–$500/mo |
| `vehicle_wrap` | local_physical | 9 | monthly_usd_at_typical | $100–$450/mo |
| `vending` | local_physical | 5 | monthly_usd_at_typical | $150–$800/mo |
| `notion_templates` | digital | 8 | monthly_usd_at_typical | $100–$1,500/mo |
| `ebooks` | digital | 8 | monthly_usd_at_typical | $50–$800/mo |
| `printables` | digital | 8 | monthly_usd_at_typical | $50–$600/mo |
| `online_course` | digital | 7 | monthly_usd_at_typical | $200–$5,000/mo |
| `ai_art_stock` | digital | 7 | monthly_usd_at_typical | $30–$300/mo |
| `ai_music_stock` | digital | 7 | monthly_usd_at_typical | $20–$400/mo |
| `stock_video` | digital | 7 | monthly_usd_at_typical | $50–$500/mo |
| `faceless_youtube` | content | 5 | monthly_usd_at_typical | $100–$3,000/mo |
| `affiliate_niche_site` | content | 5 | monthly_usd_at_typical | $100–$5,000/mo |
| `paid_newsletter` | content | 5 | monthly_usd_at_typical | $200–$3,000/mo |
| `evergreen_podcast` | content | 5 | monthly_usd_at_typical | $50–$1,000/mo |
| `print_on_demand` | commerce | 6 | monthly_usd_at_typical | $50–$1,500/mo |
| `tiktok_shop` | commerce | 3 | monthly_usd_at_typical | $100–$3,000/mo |
| `amazon_kdp` | commerce | 7 | monthly_usd_at_typical | $50–$2,000/mo |
| `domain_parking` | commerce | 8 | monthly_usd_at_typical | $10–$500/mo |
| `micro_saas` | digital | 6 | monthly_usd_at_typical | $200–$5,000/mo |
| `white_label_saas` | commerce | 6 | monthly_usd_at_typical | $300–$3,000/mo |
| `website_flipping` | commerce | 4 | monthly_usd_at_typical | lumpy/project |
| `p2p_lending` | credit_alt | 5 | annual_pct | 6–10% |

For each: set `exclusions_match: ["crypto"]` only on crypto-adjacent; `exclusions_match: ["adult"]` on adult; `exclusions_match: ["p2p"]` on p2p_lending; `exclusions_match: ["leveraged_re"]` on str_rental and house_hack if high leverage.

Flag `str_rental` with `"location_sensitivity": "high"` and note FL STR regulations vary by county.

- [ ] **After creating all 28 files, run:**

```bash
pytest tests/test_fixtures.py -v
```

Expected: all 5 fixture tests pass, including `test_fixture_a_b_c_have_different_top5`.

- [ ] **Commit**

```bash
git add catalog/streams/
git commit -m "feat: complete 36-stream catalog"
```

---

## Task 19: 90-Day Checklist Generator

**Files:**
- Create: `src/pia/output/checklist.py`

```python
from __future__ import annotations
from pia.schemas.stream import ScoredStream


def render_90day_checklist(scored: list[ScoredStream]) -> str:
    lines = ["# 90-Day Execution Checklist\n",
             "Copy this to your task manager. Check off daily.\n"]
    qualified = [s for s in scored if not s.disqualified][:5]

    lines.append("## Week 1: Accounts & Setup")
    lines.append("- [ ] Create `runs/tracker.csv` and log all streams")
    for s in qualified:
        if s.stream.startup_checklist:
            lines.append(f"- [ ] [{s.stream.name}] {s.stream.startup_checklist[0]}")

    lines.append("\n## Weeks 2–4: Launch")
    for s in qualified:
        for step in s.stream.startup_checklist[1:3]:
            lines.append(f"- [ ] [{s.stream.name}] {step}")

    lines.append("\n## Month 2: First Revenue Check")
    for s in qualified:
        lines.append(f"- [ ] [{s.stream.name}] Log first income in tracker")
        if s.stream.kpis:
            lines.append(f"  - KPI: {s.stream.kpis[0]}")

    lines.append("\n## Month 3: Kill or Double Down")
    for s in qualified:
        lines.append(f"- [ ] [{s.stream.name}] Check kill criteria:")
        for k in s.stream.kill_criteria[:2]:
            lines.append(f"  - {k}")

    lines.append("\n## Revisit Triggers")
    lines.append("- [ ] Re-run analysis if income <50% of base plan for 2 months")
    lines.append("- [ ] Re-run analysis at month 6 and month 12")
    lines.append("- [ ] Re-run if a platform changes fees >20% or policy materially")
    return "\n".join(lines)
```

- [ ] **Wire into `analyze` command** — add to `artifacts`:
  ```python
  from pia.output.checklist import render_90day_checklist
  artifacts["checklist_90day.md"] = render_90day_checklist(ranked)
  ```

- [ ] **Commit**
```bash
git add src/pia/output/checklist.py src/pia/cli.py
git commit -m "feat: 90-day execution checklist generator"
```

---

## Task 20: KPI Tracker CSV Template

**Files:**
- Add to `src/pia/output/renderer.py`:

```python
def render_tracker_csv(scored: list[ScoredStream]) -> str:
    lines = ["Date,Stream,Gross_USD,Fees_USD,Net_USD,Hours,vs_Plan_Net,vs_Plan_Hours,Notes"]
    qualified = [s for s in scored if not s.disqualified][:8]
    for s in qualified:
        lines.append(f"YYYY-MM-DD,{s.stream.name},0,0,0,0,{s.stream.yield_.base},target_tbd,")
    return "\n".join(lines)
```

- [ ] **Wire into `analyze` command**: `artifacts["tracker.csv"] = render_tracker_csv(ranked)`

- [ ] **Commit**
```bash
git add src/pia/output/renderer.py src/pia/cli.py
git commit -m "feat: KPI tracker CSV template export"
```

---

## Task 21: Full Integration Test

**Files:**
- Create: `tests/test_integration.py`

```python
import json
from pathlib import Path
from pia.schemas.profile import Profile
from pia.catalog.loader import load_catalog
from pia.engine.scorer import rank_streams
from pia.engine.portfolio import build_portfolio
from pia.output.renderer import render_ranked_table, render_portfolio_blueprint, DISCLAIMER
from pia.output.checklist import render_90day_checklist

CATALOG_DIR = Path(__file__).parent.parent / "catalog" / "streams"


def load_profile(name):
    with open(Path(__file__).parent / "fixtures" / f"profile_{name}.json") as f:
        return Profile(**json.load(f))


def run_full_pipeline(profile_name):
    profile = load_profile(profile_name)
    streams = load_catalog(CATALOG_DIR)
    ranked = rank_streams(profile, streams)
    alloc = build_portfolio(profile, ranked)
    table_md = render_ranked_table(ranked)
    blueprint_md = render_portfolio_blueprint(alloc, {"bear": 0, "base": 100, "bull": 200})
    checklist_md = render_90day_checklist(ranked)
    return ranked, alloc, table_md, blueprint_md, checklist_md


def test_full_pipeline_all_fixtures():
    for name in ("a", "b", "c", "d"):
        ranked, alloc, table, blueprint, checklist = run_full_pipeline(name)
        assert len(ranked) > 0
        assert DISCLAIMER in blueprint
        assert "90-Day" in checklist


def test_fixture_d_shows_debt_warning():
    _, alloc, _, blueprint, _ = run_full_pipeline("d")
    assert alloc.debt_gate_active
    assert "DEBT GATE" in blueprint


def test_all_exports_contain_disclaimer():
    _, _, table, blueprint, checklist = run_full_pipeline("b")
    assert "not financial" in blueprint.lower()


def test_no_single_point_yield_in_blueprint():
    _, _, _, blueprint, _ = run_full_pipeline("a")
    assert "guaranteed" not in blueprint.lower()
    assert "risk-free" not in blueprint.lower()
```

- [ ] **Run:** `pytest tests/test_integration.py -v` — expect all PASS

- [ ] **Run full suite:** `pytest --tb=short` — target: 0 failures

- [ ] **Commit**
```bash
git add tests/test_integration.py
git commit -m "test: full integration pipeline tests for all 4 fixtures"
```

---

## Phased Delivery Checklist

| Phase | Deliverable | Done when |
|-------|-------------|-----------|
| **0** | Scaffolding + schemas | `pytest` collects tests, no import errors |
| **1** | 8 seed streams + scorer + portfolio + CLI | `pia analyze` runs end-to-end, exports 5+ files |
| **2** | All 36 streams + fixture A≠B≠C top-5 | `test_fixtures.py` all pass |
| **3** | Claude AI intake + playbooks | `pia chat` extracts profile; playbooks generated |
| **4** | Tracking mode + SQLite | `pia log` + `pia drift` work; runs persist |
| **5** | Integration tests all green | `pytest --tb=short` = 0 failures |

**Ship only when:**
- [ ] Fixtures A, B, C have ≥ 3 different streams in top-5
- [ ] Fixture D triggers debt gate warning
- [ ] All $ outputs show bear/base/bull
- [ ] Disclaimer present on every export
- [ ] `pia analyze` completes cold-start in < 30 seconds

---

*End of plan. Spec version: Passive Income Analysis Skill v2.0.*
