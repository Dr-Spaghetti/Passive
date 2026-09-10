from __future__ import annotations
from typing import Literal, Optional
from pydantic import BaseModel, Field, model_validator


class Range(BaseModel):
    min: float = Field(0.0, ge=0)
    max: float = Field(0.0, ge=0)
    point: Optional[float] = None

    @model_validator(mode="after")
    def set_point(self) -> Range:
        if self.min > self.max:
            raise ValueError("minimum cannot exceed maximum")
        if self.point is None:
            self.point = (self.min + self.max) / 2
        return self


class Locale(BaseModel):
    country: str = "US"
    state: str = ""
    metro: Optional[str] = None


class Audience(BaseModel):
    email: int = Field(0, ge=0)
    yt: int = Field(0, ge=0)
    social_total: int = Field(0, ge=0)


class ExistingAssets(BaseModel):
    brokerage_usd: float = Field(0.0, ge=0)
    retirement_usd: float = Field(0.0, ge=0)
    rental_properties: int = Field(0, ge=0)
    digital_products_live: int = Field(0, ge=0)
    audience: Audience = Field(default_factory=Audience)
    physical: list[str] = Field(default_factory=list)


class Tax(BaseModel):
    filing_status: str = "single"
    self_employed: bool = False
    notes: str = ""


class Financial(BaseModel):
    liquid_deployable_usd: Range = Field(default_factory=Range)
    monthly_surplus_usd: Range = Field(default_factory=Range)
    emergency_fund_months: float = Field(0.0, ge=0)
    high_interest_debt_usd: float = Field(0.0, ge=0)
    existing_assets: ExistingAssets = Field(default_factory=ExistingAssets)
    target_monthly_passive_usd: float = Field(0.0, ge=0)
    target_deadline_months: int = Field(24, ge=1)
    tax: Tax = Field(default_factory=Tax)


class TimeProfile(BaseModel):
    setup_hours_per_week_90d: float = Field(0.0, ge=0)
    maintenance_hours_per_month_steady: float = Field(0.0, ge=0)
    preferred_cadence: Literal["set_forget", "light_ops", "creative_ops"] = "light_ops"


class Risk(BaseModel):
    score_1_to_10: int = Field(5, ge=1, le=10)
    max_drawdown_tolerance_pct: float = Field(20.0, ge=0, le=100)
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
    max_platforms: int = Field(3, ge=1)
    other: str = ""


class Confidence(BaseModel):
    financial: Literal["high", "med", "low"] = "med"
    time: Literal["high", "med", "low"] = "med"
    skills: Literal["high", "med", "low"] = "med"


class StackAsset(BaseModel):
    """Lane-tagged inventory item. WORK is never personal deployable capital."""

    name: str
    lane: Literal["work", "product", "personal"]
    status: Literal["fact", "unknown", "weak_fact"] = "fact"
    personal_use_ok: bool = False
    tags: list[str] = Field(default_factory=list)
    notes: str = ""


class StackInventory(BaseModel):
    """PERSONAL/PRODUCT may score; WORK only if personal_use_ok is confirmed."""

    assets: list[StackAsset] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    source: str = ""


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
    stack: StackInventory = Field(default_factory=StackInventory)

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
    def monthly_surplus_point(self) -> float:
        return self.financial.monthly_surplus_usd.point or 0.0

    @property
    def monthly_maintenance_budget(self) -> float:
        return self.time.maintenance_hours_per_month_steady

    def deployable_stack_assets(self) -> list[StackAsset]:
        """Assets that may inform PERSONAL Passive scoring (never unconfirmed WORK)."""
        out: list[StackAsset] = []
        for asset in self.stack.assets:
            if asset.lane == "work" and not asset.personal_use_ok:
                continue
            if asset.status == "unknown":
                continue
            out.append(asset)
        return out

    def stack_tags(self) -> set[str]:
        tags: set[str] = set()
        for asset in self.deployable_stack_assets():
            tags.update(t.lower() for t in asset.tags)
            tags.add(asset.name.lower())
        for item in self.financial.existing_assets.physical:
            tags.add(item.lower())
        for domain in self.skills.domain_expertise:
            tags.add(domain.lower())
        return tags
