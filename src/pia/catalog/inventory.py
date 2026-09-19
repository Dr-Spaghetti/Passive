"""FACT-only stack inventory: validated JSON is the source of truth.

WORK-lane assets are never treated as personal deployable capital unless
personal_use_ok is confirmed. Markdown parse is an optional migration path only.
Educational tooling — does not invent money, gear, or deploy numbers.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable, Literal

from pydantic import ValidationError

from pia.schemas.profile import Profile, StackAsset, StackInventory

Lane = Literal["work", "product", "personal"]
Status = Literal["fact", "unknown", "weak_fact"]

INVENTORY_RULES_NOTE = (
    "WORK SaaS/gear is not personal capital unless Nick confirms personal_use_ok."
)


def validate_inventory(data: dict | list | StackInventory) -> StackInventory:
    """Validate raw data into StackInventory; raise ValueError with clear detail."""
    try:
        if isinstance(data, StackInventory):
            return data
        if isinstance(data, list):
            return StackInventory(assets=[StackAsset.model_validate(row) for row in data])
        if isinstance(data, dict):
            if "assets" in data:
                return StackInventory.model_validate(data)
            # Single asset envelope is not supported as a full inventory
            raise ValueError("Inventory JSON must be {assets:[...], notes?, source?} or a list of assets")
        raise ValueError(f"Unsupported inventory type: {type(data)!r}")
    except ValidationError as exc:
        raise ValueError(f"Invalid inventory schema: {exc}") from exc


def load_inventory_json(path: Path) -> StackInventory:
    """Load and validate inventory JSON (source of truth)."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    inv = validate_inventory(raw)
    if not inv.source:
        inv = inv.model_copy(update={"source": str(path)})
    return inv


def save_inventory_json(inventory: StackInventory, path: Path, *, indent: int = 2) -> None:
    """Persist validated inventory as JSON (atomic-ish write)."""
    inv = validate_inventory(inventory)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = inv.model_dump()
    if not payload.get("source"):
        payload["source"] = str(path)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=indent) + "\n", encoding="utf-8")
    tmp.replace(path)


def parse_inventory_markdown_text(text: str, *, source: str = "pasted-markdown") -> StackInventory:
    """Optional migration helper: best-effort FACT extractor from pia-ops markdown.

    Prefer curated JSON via load_inventory_json / CLI CRUD. Do not treat this
    heuristic as authoritative for CoS production briefs.
    """
    assets: list[StackAsset] = []
    notes: list[str] = [
        INVENTORY_RULES_NOTE,
        f"Parsed from {source} (migration heuristic — prefer curated JSON).",
    ]

    # (regex, name, lane, personal_use_ok, tags)
    patterns = [
        (r"(?i)insta360", "Insta360 camera", "work", True, ["insta360", "360", "video", "pano"]),
        (r"(?i)panostitch", "panostitch-pro", "product", True, ["panostitch", "pano", "panorama", "video"]),
        (r"(?i)brightlocal", "BrightLocal", "work", False, ["seo", "gbp", "citation", "brightlocal"]),
        (r"(?i)local falcon", "Local Falcon", "work", False, ["seo", "gbp", "local falcon"]),
        (r"(?i)runway", "Runway AI", "work", False, ["ai", "video", "runway"]),
        (r"(?i)higgsfield", "Higgsfield", "work", False, ["ai", "video", "higgsfield"]),
        (
            r"(?i)justify\s*local|director of ai",
            "Justify Local AI/SEO skills",
            "work",
            True,
            ["seo", "gbp", "ai", "citation", "maps"],
        ),
        (r"(?i)vercel", "Vercel / Dr-Spaghetti shipping", "product", True, ["software", "saas", "vercel", "github"]),
        (r"(?i)passive income analyzer|/Passive", "Passive (pia)", "personal", True, ["software", "pia"]),
    ]

    seen: set[str] = set()
    for pattern, name, lane, personal_use_ok, tags in patterns:
        if not re.search(pattern, text):
            continue
        if name in seen:
            continue
        status: Status = "fact"
        if lane == "work" and name.startswith("Insta360"):
            notes.append(
                "Insta360: ownership/payer UNKNOWN in inventory — counted for skill/gear adjacency only; "
                "not as free deployable capital."
            )
        assets.append(
            StackAsset(
                name=name,
                lane=lane,  # type: ignore[arg-type]
                status=status,
                personal_use_ok=personal_use_ok,
                tags=tags,
                notes="from inventory markdown heuristic (migration)",
            )
        )
        seen.add(name)

    return StackInventory(assets=assets, notes=notes, source=source)


def parse_inventory_markdown(path: Path) -> StackInventory:
    """Optional migration: parse pia-ops nick-inventory markdown tables."""
    return parse_inventory_markdown_text(path.read_text(encoding="utf-8"), source=str(path))


def load_inventory(path: Path) -> StackInventory:
    """Load inventory; JSON is preferred. Non-JSON falls back to markdown migration."""
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".json":
        return load_inventory_json(path)
    if suffix in {".md", ".markdown", ".txt"}:
        return parse_inventory_markdown(path)
    # Ambiguous: try JSON first, then markdown text
    try:
        return load_inventory_json(path)
    except (json.JSONDecodeError, ValueError, UnicodeDecodeError):
        return parse_inventory_markdown(path)


def list_assets(
    inventory: StackInventory,
    *,
    lane: Lane | None = None,
    status: Status | None = None,
    deployable_only: bool = False,
) -> list[StackAsset]:
    """List assets with optional filters. deployable_only applies WORK/personal_use_ok rule."""
    out: list[StackAsset] = []
    for asset in inventory.assets:
        if lane is not None and asset.lane != lane:
            continue
        if status is not None and asset.status != status:
            continue
        if deployable_only:
            if asset.lane == "work" and not asset.personal_use_ok:
                continue
            if asset.status == "unknown":
                continue
        out.append(asset)
    return out


def find_asset(inventory: StackInventory, name: str) -> StackAsset | None:
    key = name.strip().lower()
    for asset in inventory.assets:
        if asset.name.lower() == key:
            return asset
    return None


def add_asset(
    inventory: StackInventory,
    *,
    name: str,
    lane: Lane,
    status: Status = "fact",
    personal_use_ok: bool = False,
    tags: Iterable[str] | None = None,
    notes: str = "",
    overwrite: bool = False,
) -> StackInventory:
    """Add a FACT/UNKNOWN asset. Raises ValueError if name exists and overwrite is False."""
    name = name.strip()
    if not name:
        raise ValueError("Asset name is required")
    existing = find_asset(inventory, name)
    if existing is not None and not overwrite:
        raise ValueError(f"Asset already exists: {existing.name!r} (use update or --overwrite)")
    asset = StackAsset(
        name=name,
        lane=lane,
        status=status,
        personal_use_ok=personal_use_ok,
        tags=[t.strip() for t in (tags or []) if t and str(t).strip()],
        notes=notes or "",
    )
    assets = [a for a in inventory.assets if a.name.lower() != name.lower()]
    assets.append(asset)
    return inventory.model_copy(update={"assets": assets})


def update_asset(
    inventory: StackInventory,
    name: str,
    *,
    lane: Lane | None = None,
    status: Status | None = None,
    personal_use_ok: bool | None = None,
    tags: Iterable[str] | None = None,
    notes: str | None = None,
    new_name: str | None = None,
) -> StackInventory:
    """Update fields on an existing asset by name."""
    current = find_asset(inventory, name)
    if current is None:
        raise ValueError(f"Asset not found: {name!r}")
    data = current.model_dump()
    if new_name is not None and new_name.strip():
        data["name"] = new_name.strip()
    if lane is not None:
        data["lane"] = lane
    if status is not None:
        data["status"] = status
    if personal_use_ok is not None:
        data["personal_use_ok"] = personal_use_ok
    if tags is not None:
        data["tags"] = [t.strip() for t in tags if t and str(t).strip()]
    if notes is not None:
        data["notes"] = notes
    updated = StackAsset.model_validate(data)
    # Prevent accidental rename collision
    if updated.name.lower() != current.name.lower() and find_asset(inventory, updated.name):
        raise ValueError(f"Rename target already exists: {updated.name!r}")
    assets = [updated if a.name.lower() == current.name.lower() else a for a in inventory.assets]
    return inventory.model_copy(update={"assets": assets})


def remove_asset(inventory: StackInventory, name: str) -> StackInventory:
    current = find_asset(inventory, name)
    if current is None:
        raise ValueError(f"Asset not found: {name!r}")
    assets = [a for a in inventory.assets if a.name.lower() != current.name.lower()]
    return inventory.model_copy(update={"assets": assets})


def import_markdown_to_json(md_path: Path, json_path: Path, *, overwrite: bool = False) -> StackInventory:
    """Migration: parse markdown heuristic → write validated JSON."""
    json_path = Path(json_path)
    if json_path.exists() and not overwrite:
        raise ValueError(f"Refusing to overwrite existing {json_path} (pass overwrite=True)")
    inv = parse_inventory_markdown(Path(md_path))
    notes = list(inv.notes)
    if "Migrated from markdown heuristic — review FACT rows before CoS use." not in notes:
        notes.append("Migrated from markdown heuristic — review FACT rows before CoS use.")
    inv = inv.model_copy(update={"notes": notes, "source": str(json_path)})
    save_inventory_json(inv, json_path)
    return inv


def work_blocked_assets(inventory: StackInventory) -> list[StackAsset]:
    """WORK assets that must NOT score as personal deployable capital."""
    return [
        a
        for a in inventory.assets
        if a.lane == "work" and not a.personal_use_ok and a.status != "unknown"
    ]


def merge_inventory_into_profile(profile: Profile, inventory: StackInventory) -> Profile:
    """Return a copy of profile with stack inventory merged (does not alter money fields)."""
    inventory = validate_inventory(inventory)
    data = profile.model_dump()
    existing = StackInventory(**data.get("stack") or {})
    # Merge by name; incoming inventory wins on conflict
    by_name = {a.name: a for a in existing.assets}
    for asset in inventory.assets:
        by_name[asset.name] = asset
    notes = list(dict.fromkeys([*existing.notes, *inventory.notes]))
    if INVENTORY_RULES_NOTE not in notes:
        notes.insert(0, INVENTORY_RULES_NOTE)
    blocked = work_blocked_assets(StackInventory(assets=list(by_name.values())))
    if blocked:
        blocked_note = (
            "WORK blocked from deployable capital (personal_use_ok=false): "
            + ", ".join(a.name for a in blocked[:12])
        )
        if blocked_note not in notes:
            notes.append(blocked_note)
    domains = list(profile.skills.domain_expertise or [])
    seed_domains: list[str] = []
    tag_set: set[str] = set()
    # Seed domains only from deployable assets (never unconfirmed WORK)
    for a in by_name.values():
        if a.lane == "work" and not a.personal_use_ok:
            continue
        if a.status == "unknown":
            continue
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
    # Physical gear names (PERSONAL/PRODUCT or personal_use_ok WORK only)
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
