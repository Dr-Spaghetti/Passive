from __future__ import annotations
import json
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from pia.schemas.profile import Profile
from pia.catalog.loader import load_catalog
from pia.engine.scorer import rank_streams
from pia.engine.portfolio import build_portfolio
from pia.engine.projector import project_paper

CATALOG_DIR = Path(__file__).parent.parent.parent.parent / "catalog" / "streams"
STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="Passive Income Analyzer")


class AnalyzeRequest(BaseModel):
    profile: dict


class PlaybookRequest(BaseModel):
    profile: dict


@app.get("/", response_class=HTMLResponse)
async def root():
    html_path = STATIC_DIR / "index.html"
    if html_path.exists():
        return HTMLResponse(content=html_path.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>Passive Income Analyzer</h1><p>index.html not found.</p>")


@app.post("/api/analyze")
async def analyze(req: AnalyzeRequest):
    try:
        profile = Profile(**req.profile)
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))

    streams = load_catalog(CATALOG_DIR)
    ranked = rank_streams(profile, streams)
    alloc = build_portfolio(profile, ranked)

    # Build monthly projections
    monthly_proj = {"bear": 0.0, "base": 0.0, "bull": 0.0}
    for item in alloc.allocations:
        match = next((r for r in ranked if r.stream.stream_id == item.stream_id), None)
        if match and match.stream.category == "paper":
            proj = project_paper(item.allocation_usd, match.stream.yield_.base, 0, 12, False)
            for sc in ("bear", "base", "bull"):
                key = f"income_month_12"
                monthly_proj[sc] += proj[sc].get(key, 0)

    # Build 24-month projection series for chart
    projection_series: dict[str, list[float]] = {"bear": [], "base": [], "bull": []}
    total_paper_alloc = sum(
        item.allocation_usd for item in alloc.allocations
        if next((r for r in ranked if r.stream.stream_id == item.stream_id), None)
        and next((r for r in ranked if r.stream.stream_id == item.stream_id)).stream.category == "paper"
    )
    if total_paper_alloc > 0:
        sample_stream = next(
            (r for r in ranked if not r.disqualified and r.stream.category == "paper"), None
        )
        if sample_stream:
            proj24 = project_paper(total_paper_alloc, sample_stream.stream.yield_.base, 0, 24, False)
            for sc in ("bear", "base", "bull"):
                projection_series[sc] = [proj24[sc].get(f"income_month_{m}", 0) for m in range(1, 25)]

    return {
        "profile_id": profile.profile_id,
        "debt_gate_active": alloc.debt_gate_active,
        "debt_gate_message": alloc.debt_gate_message,
        "monthly_projections": monthly_proj,
        "projection_series": projection_series,
        "ranked_streams": [
            {
                "stream_id": r.stream.stream_id,
                "name": r.stream.name,
                "category": r.stream.category,
                "passivity_index": r.stream.passivity_index,
                "passivity_label": r.stream.passivity_label,
                "fit_score": r.fit_score,
                "ras": r.ras,
                "disqualified": r.disqualified,
                "disqualify_reason": r.disqualify_reason,
                "explain": r.explain,
                "capital_suggested_usd": r.capital_suggested_usd,
                "yield_bear": r.stream.yield_.bear,
                "yield_base": r.stream.yield_.base,
                "yield_bull": r.stream.yield_.bull,
                "yield_unit": r.stream.yield_.unit,
                "startup_checklist": r.stream.startup_checklist,
                "kill_criteria": r.stream.kill_criteria,
                "kpis": r.stream.kpis,
                "is_stale": r.stream.is_stale,
            }
            for r in ranked
        ],
        "portfolio": {
            "total_deployed": alloc.total_deployed,
            "phase_summary": alloc.phase_summary,
            "allocations": [
                {
                    "stream_id": item.stream_id,
                    "stream_name": item.stream_name,
                    "tier": item.tier,
                    "phase": item.phase,
                    "allocation_usd": item.allocation_usd,
                    "allocation_pct": item.allocation_pct,
                    "passivity_index": item.passivity_index,
                    "ras": item.ras,
                }
                for item in alloc.allocations
            ],
        },
    }


@app.post("/api/playbook/{stream_id}")
async def playbook(stream_id: str, req: PlaybookRequest):
    try:
        profile = Profile(**req.profile)
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))

    streams = load_catalog(CATALOG_DIR)
    stream = next((s for s in streams if s.stream_id == stream_id), None)
    if not stream:
        raise HTTPException(status_code=404, detail=f"Stream '{stream_id}' not found")

    from pia.ai.playbooks import generate_playbook
    content = generate_playbook(profile, stream)
    return {"stream_id": stream_id, "content": content}


@app.get("/api/streams")
async def list_streams():
    streams = load_catalog(CATALOG_DIR)
    return [{"stream_id": s.stream_id, "name": s.name, "category": s.category} for s in streams]
