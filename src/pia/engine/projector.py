from __future__ import annotations
import math
from dataclasses import dataclass


@dataclass
class Scenario:
    label: str
    yield_mult: float = 1.0
    traffic_growth_pct: float = 0.0
    conversion_mult: float = 1.0


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
