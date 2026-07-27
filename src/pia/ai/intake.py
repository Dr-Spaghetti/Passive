from __future__ import annotations
import json
import os
from datetime import date

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def intake_from_text(user_text: str, profile_id: str | None = None) -> "Profile":
    from pia.schemas.profile import Profile
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY not set. Add it to a .env file:\n"
            '  echo "ANTHROPIC_API_KEY=sk-ant-..." >> .env'
        )

    from anthropic import Anthropic
    client = Anthropic(api_key=api_key)
    pid = profile_id or f"ai-intake-{date.today().isoformat()}"

    system = (
        "You are a passive income profile intake assistant. "
        "Extract a structured profile from a free-text description. "
        "Output ONLY valid JSON matching the Profile schema. No commentary. "
        "Required top-level keys: profile_id, created_at, financial, time, risk, skills, goals, constraints. "
        "Use ranges (min/max) for capital and surplus. Estimate missing fields conservatively. "
        "Flag high-interest debt if mentioned. Set emergency_fund_months to 0 if not mentioned."
    )

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        system=system,
        messages=[{
            "role": "user",
            "content": (
                f"Extract a profile from this description. "
                f"Set profile_id to '{pid}' and created_at to '{date.today().isoformat()}'.\n\n{user_text}"
            ),
        }],
    )
    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return Profile(**json.loads(raw.strip()))
