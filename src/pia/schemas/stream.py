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
    bear: int = Field(1, ge=1)
    base: int = Field(1, ge=1)
    bull: int = Field(1, ge=1)


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
    public_face_requirement: Literal["none", "optional", "required"]
    customer_support_requirement: Literal["none", "light", "ongoing"]
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
