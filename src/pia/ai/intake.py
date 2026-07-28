from __future__ import annotations
import os
import re
from datetime import date


_AMOUNT = r"\$?\s*([0-9][0-9,]*(?:\.[0-9]+)?)\s*(k|thousand|m|million)?"


def intake_uses_provider() -> bool:
    """Whether free-text intake will use the optional remote provider."""
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def _amount(value: str, suffix: str | None) -> float:
    multiplier = {"k": 1_000, "thousand": 1_000, "m": 1_000_000, "million": 1_000_000}.get(
        (suffix or "").lower(), 1
    )
    return float(value.replace(",", "")) * multiplier


def _first_amount(text: str, patterns: list[str]) -> float | None:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return _amount(match.group(1), match.group(2))
    return None


def _first_number(text: str, patterns: list[str]) -> float | None:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return float(match.group(1))
    return None


def _offline_intake(user_text: str, profile_id: str | None = None) -> "Profile":
    """Create a conservative profile locally when no API key is available.

    The rules only extract explicit facts and leave everything else at safe
    schema defaults, keeping natural-language intake useful without presenting
    the result as model-backed advice.
    """
    from pia.schemas.profile import Constraints, Financial, Goals, Profile, Range, Risk, Skills, TimeProfile

    text = " ".join(user_text.lower().split())
    pid = profile_id or f"offline-intake-{date.today().isoformat()}"

    capital = _first_amount(text, [
        rf"{_AMOUNT}[^.?!]{{0,36}}\b(?:to invest|investable|deployable|capital|savings)\b",
        rf"\b(?:to invest|investable|deployable|capital|savings)\b[^.?!]{{0,36}}{_AMOUNT}",
    ])
    debt = _first_amount(text, [
        rf"{_AMOUNT}[^.?!]{{0,28}}\b(?:high[- ]interest )?debt\b",
        rf"\b(?:high[- ]interest )?debt\b[^.?!]{{0,28}}{_AMOUNT}",
    ])
    target = _first_amount(text, [
        rf"{_AMOUNT}\s*(?:/|per )month",
        rf"\b(?:income|target|goal)\b[^.?!]{{0,30}}{_AMOUNT}\s*(?:/|per )?month",
    ])
    emergency = _first_number(text, [r"(\d+(?:\.\d+)?)\s+months?[^.?!]{0,24}\b(?:emergency|emergency fund)\b", r"\b(?:emergency|emergency fund)[^.?!]{0,24}(\d+(?:\.\d+)?)\s+months?"])
    setup_hours = _first_number(text, [r"(\d+(?:\.\d+)?)\s+hours?\s*(?:a|per)?\s*week", r"(\d+(?:\.\d+)?)\s*hrs?\s*(?:a|per)?\s*week"])
    maintenance_hours = _first_number(text, [r"(\d+(?:\.\d+)?)\s+hours?\s*(?:a|per)?\s*month", r"(\d+(?:\.\d+)?)\s*hrs?\s*(?:a|per)?\s*month"])
    deadline = _first_number(text, [r"(?:within|in)\s+(\d+)\s+months?", r"(\d+)\s+month[^.?!]{0,16}\b(?:deadline|goal|target)\b"])
    stated_risk = _first_number(text, [r"\brisk(?: tolerance)?\s*(?:is|:)?\s*(\d+)\b"])

    risk_score = int(stated_risk) if stated_risk is not None else 5
    if stated_risk is None:
        if any(word in text for word in ("very conservative", "risk averse", "risk-averse")):
            risk_score = 2
        elif "conservative" in text:
            risk_score = 4
        elif any(word in text for word in ("aggressive", "high risk")):
            risk_score = 8
    risk_score = min(10, max(1, risk_score))

    skill_terms = {
        "ai_ml": (" ai ", "machine learning", "ai/", "artificial intelligence"),
        "content": ("content", "writing", "writer"),
        "video": ("video", "youtube", "filming"),
        "software": ("software", "programming", "developer", "coding", "engineer"),
        "marketing": ("marketing", "seo", "growth"),
        "real_estate": ("real estate", "rental property", "landlord"),
        "copywriting": ("copywriting", "copywriter"),
        "design": ("design", "designer"),
        "sales": ("sales", "selling"),
        "ops_automation": ("automation", "operations", "ops"),
    }
    padded_text = f" {text} "
    skills = {name: 6 if any(term in padded_text for term in terms) else 0 for name, terms in skill_terms.items()}
    exclusions = [name for name in ("crypto", "p2p", "adult", "leveraged_re") if f"no {name}" in text or f"avoid {name}" in text]
    primary = "cash_flow"
    for goal, terms in {
        "wealth": ("wealth", "grow net worth"),
        "freedom": ("freedom", "replace my job", "retire early"),
        "legacy": ("legacy", "inheritance"),
        "tax_efficiency": ("tax efficient", "tax-efficien"),
    }.items():
        if any(term in text for term in terms):
            primary = goal
            break

    return Profile(
        profile_id=pid,
        created_at=date.today().isoformat(),
        financial=Financial(
            liquid_deployable_usd=Range(min=capital or 0.0, max=capital or 0.0),
            emergency_fund_months=emergency or 0.0,
            high_interest_debt_usd=debt or 0.0,
            target_monthly_passive_usd=target or 0.0,
            target_deadline_months=max(1, int(deadline or 24)),
        ),
        time=TimeProfile(
            setup_hours_per_week_90d=setup_hours or 0.0,
            maintenance_hours_per_month_steady=maintenance_hours or 0.0,
        ),
        risk=Risk(score_1_to_10=risk_score, exclusions=exclusions),
        skills=Skills(**skills),
        goals=Goals(primary=primary),
        constraints=Constraints(
            no_public_face=any(phrase in text for phrase in ("no public face", "anonymous", "stay private")),
            no_customer_support=any(phrase in text for phrase in ("no customer support", "avoid customer support", "or customer support")),
        ),
    )


def _provider_intake(user_text: str, profile_id: str | None = None) -> "Profile":
    """Extract a profile with Anthropic when the optional provider is available."""
    from pia.schemas.profile import Profile
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("Anthropic API key is not configured.")

    from anthropic import Anthropic
    client = Anthropic(api_key=api_key)
    pid = profile_id or f"ai-intake-{date.today().isoformat()}"

    # Force the exact Profile field names via a tool call rather than asking the
    # model to freehand JSON matching a schema it was only told about in prose —
    # that let it invent plausible-but-wrong keys (e.g. "capital" instead of
    # "liquid_deployable_usd") that pydantic silently ignored as unknown fields.
    tool = {
        "name": "record_profile",
        "description": (
            "Record the structured passive-income profile extracted from the user's "
            "free-text description. Only fill fields you have explicit evidence for; "
            "leave everything else at its schema default rather than guessing."
        ),
        "input_schema": Profile.model_json_schema(),
    }

    response = client.messages.create(
        model="claude-sonnet-5",
        max_tokens=2000,
        tools=[tool],
        tool_choice={"type": "tool", "name": "record_profile"},
        messages=[{
            "role": "user",
            "content": (
                f"Extract a profile from this description. "
                f"Set profile_id to '{pid}' and created_at to '{date.today().isoformat()}'. "
                f"Flag high-interest debt if mentioned; set emergency_fund_months to 0 if not "
                f"mentioned.\n\n{user_text}"
            ),
        }],
    )
    tool_use = next(block for block in response.content if block.type == "tool_use")
    return Profile(**_coerce_provider_json(tool_use.input))


_OBJECT_SECTIONS = ("financial", "time", "risk", "skills", "goals", "constraints", "confidence", "locale")

_ENUM_FIELDS = {
    ("time", "preferred_cadence"): ({"set_forget", "light_ops", "creative_ops"}, "light_ops"),
    ("risk", "liquidity_need"): ({"days", "months", "years"}, "months"),
    ("goals", "primary"): ({"cash_flow", "wealth", "freedom", "legacy", "tax_efficiency"}, "cash_flow"),
    ("confidence", "financial"): ({"high", "med", "low"}, "med"),
    ("confidence", "time"): ({"high", "med", "low"}, "med"),
    ("confidence", "skills"): ({"high", "med", "low"}, "med"),
}


def _coerce_provider_json(data: dict) -> dict:
    """Repair occasional wrong-type or out-of-enum fields the model emits.

    Models occasionally send a plain string for a section that must be an
    object, `[]` for a field that must be an object or string, or descriptive
    text for a field constrained to a fixed set of tokens. Rather than fail
    the whole extraction over one malformed field, drop or normalize it back
    to the schema's own conservative default so validation succeeds.
    """
    if isinstance(data.get("skills"), list):
        data["skills"] = {}

    for section in _OBJECT_SECTIONS:
        if section in data and not isinstance(data[section], dict):
            del data[section]

    constraints = data.get("constraints")
    if isinstance(constraints, dict) and isinstance(constraints.get("other"), list):
        constraints["other"] = ""

    for (section, field), (valid_values, default) in _ENUM_FIELDS.items():
        section_data = data.get(section)
        if isinstance(section_data, dict) and section_data.get(field) not in valid_values:
            section_data[field] = default

    return data


def intake_from_text_with_source(user_text: str, profile_id: str | None = None) -> tuple["Profile", str]:
    """Return a valid profile without making provider availability a form failure."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return _offline_intake(user_text, profile_id), "offline"
    try:
        return _provider_intake(user_text, profile_id), "provider"
    except Exception:
        # Local extraction is deliberately conservative and keeps intake useful
        # during network, quota, or provider-response failures.
        return _offline_intake(user_text, profile_id), "offline_fallback"


def intake_from_text(user_text: str, profile_id: str | None = None) -> "Profile":
    """Compatibility wrapper that returns only the extracted profile."""
    return intake_from_text_with_source(user_text, profile_id)[0]
