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
    for filename, content in artifacts.items():
        (run_dir / filename).write_text(content, encoding="utf-8")
    print(f"Exported {len(artifacts)} artifacts to {run_dir}")
