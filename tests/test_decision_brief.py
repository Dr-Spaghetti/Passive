from __future__ import annotations

import json
from pathlib import Path

from pia.catalog.loader import load_catalog
from pia.output.decision_brief import build_decision_brief, catalog_freshness_report
from pia.schemas.profile import Profile

FIXTURE_DIR = Path(__file__).parent / "fixtures"
CATALOG_DIR = Path(__file__).parent.parent / "catalog" / "streams"


def test_decision_brief_for_fixture_a():
    profile = Profile(**json.loads((FIXTURE_DIR / "profile_a.json").read_text(encoding="utf-8")))
    streams = load_catalog(CATALOG_DIR)
    brief = build_decision_brief(profile, streams)

    assert brief["options"], "expected non-empty options"
    ids = [o["stream_id"] for o in brief["options"]]
    assert len(ids) == len(set(ids)), f"option stream ids must be distinct: {ids}"
    assert len(ids) >= 2

    md = brief["markdown"]
    assert "Educational" in md
    assert "decision brief" in md.lower()
    for o in brief["options"]:
        assert o["stream_id"] in md
        assert isinstance(o["explain"], list)


def test_catalog_freshness_report_includes_as_of():
    streams = load_catalog(CATALOG_DIR)
    report = catalog_freshness_report(streams)
    assert report["total"] == len(streams)
    assert "stale_count" in report
    assert report["streams"]
    assert "as_of" in report["streams"][0]
    assert "stale" in report["streams"][0]
