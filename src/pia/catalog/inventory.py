"""Merge FACT-only stack inventory into a Profile for stack-aware scoring.

WORK-lane assets are never treated as personal capital unless personal_use_ok.
Educational tooling only — does not invent money numbers.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from pia.schemas.profile import Profile, StackAsset, StackInventory


def load_inventory_json(path: Path) -> StackInventory:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and "assets" in data:
        return StackInventory(**data)
    if isinstance(data, list):
        return StackInventory(assets=[StackAsset(**row) for row in data], source=str(path))
    raise ValueError(f"Unsupported inventory JSON shape in {path}")


def parse_inventory_markdown_text(text: str, *, source: str = "pasted-markdown") -> StackInventory:
    """Best-effort FACT extractor for pia-ops inventory markdown (string form)."""
    assets: list[StackAsset] = []
    notes: list[str] = [
        "WORK SaaS/gear is not personal capital unless Nick confirms personal_use_ok.",
        f"Parsed from {source} (FACT/UNKNOWN only — no invented gear).",
    ]

    # Heuristic rows: look for known items mentioned as FACT
    patterns = [
        # (regex, name, lane, personal_use_ok, tags)
        (r"(?i)insta360", "Insta360 camera", "work", True, ["insta360", "360", "video", "pano"]),
        (r"(?i)panostitch", "panostitch-pro", "product", True, ["panostitch", "pano", "panorama", "video"]),
        (r"(?i)brightlocal", "BrightLocal", "work", False, ["seo", "gbp", "citation", "brightlocal"]),
        (r"(?i)local falcon", "Local Falcon", "work", False, ["seo", "gbp", "local falcon"]),
        (r"(?i)runway", "Runway AI", "work", False, ["ai", "video", "runway"]),
        (r"(?i)higgsfield", "Higgsfield", "work", False, ["ai", "video", "higgsfield"]),
        (r"(?i)justify\s*local|director of ai", "Justify Local AI/SEO skills", "work", True, ["seo", "gbp", "ai", "citation", "maps"]),
        (r"(?i)vercel", "Vercel / Dr-Spaghetti shipping", "product", True, ["software", "saas", "vercel", "github"]),
        (r"(?i)passive income analyzer|/Passive", "Passive (pia)", "personal", True, ["software", "pia"]),
    ]

    seen: set[str] = set()
    for pattern, name, lane, personal_use_ok, tags in patterns:
        if not re.search(pattern, text):
            continue
        if name in seen:
            continue
        # Prefer FACT mentions near the keyword
        status = "fact"
        if lane == "work" and name.startswith("Insta360"):
            # Inventory marks lane UNKNOWN / payer UNKNOWN — personal_use_ok provisional for skill transfer only
            notes.append(
                "Insta360: ownership/payer UNKNOWN in inventory — counted for skill/gear adjacency only; "
                "not as free deployable capital."
            )
        assets.append(
            StackAsset(
                name=name,
                lane=lane,  # type: ignore[arg-type]
                status=status,  # type: ignore[arg-type]
                personal_use_ok=personal_use_ok,
                tags=tags,
                notes="from inventory markdown heuristic",
            )
        )
        seen.add(name)

    return StackInventory(assets=assets, notes=notes, source=source)


def parse_inventory_markdown(path: Path) -> StackInventory:
    """Best-effort FACT extractor for pia-ops nick-inventory markdown tables."""
    return parse_inventory_markdown_text(path.read_text(encoding="utf-8"), source=str(path))


def load_inventory(path: Path) -> StackInventory:
    if path.suffix.lower() == ".json":
        inv = load_inventory_json(path)
        if not inv.source:
            inv.source = str(path)
        return inv
    return parse_inventory_markdown(path)


def merge_inventory_into_profile(profile: Profile, inventory: StackInventory) -> Profile:
    """Return a copy of profile with stack inventory merged (does not alter money fields)."""
    data = profile.model_dump()
    existing = StackInventory(**data.get("stack") or {})
    # Merge by name; incoming inventory wins on conflict
    by_name = {a.name: a for a in existing.assets}
    for asset in inventory.assets:
        by_name[asset.name] = asset
    notes = list(dict.fromkeys([*existing.notes, *inventory.notes]))
    domains = list(profile.skills.domain_expertise or [])
    # Seed domain_expertise from tags if empty / extend carefully
    seed_domains = []
    tag_set = set()
    for a in by_name.values():
        tag_set.update(a.tags)
    for candidate in ("seo", "gbp", "ai", "video", "panorama", "local seo", "software"):
        if candidate in {t.lower() for t in tag_set} or any(candidate in t.lower() for t in tag_set):
            seed_domains.append(candidate)
    merged_domains = list(dict.fromkeys([*domains, *seed_domains]))
    data["stack"] = StackInventory(
        assets=list(by_name.values()),
        notes=notes,
        source=inventory.source or existing.source,
    ).model_dump()
    data["skills"]["domain_expertise"] = merged_domains
    # Physical gear names (PERSONAL or personal_use_ok only) into existing_assets.physical for scorer tags
    physical = list(profile.financial.existing_assets.physical or [])
    for a in by_name.values():
        if a.lane == "work" and not a.personal_use_ok:
            continue
        if a.status == "unknown":
            continue
        if a.name not in physical and any(
            k in " ".join(a.tags).lower() for k in ("insta360", "camera", "pano", "drone")
        ):
            physical.append(a.name)
    data["financial"]["existing_assets"]["physical"] = physical
    return Profile(**data)
