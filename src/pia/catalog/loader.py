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
