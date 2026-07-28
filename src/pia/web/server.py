from __future__ import annotations
import json
import uuid
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

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


class IntakeRequest(BaseModel):
    text: str


class IncomeLogRequest(BaseModel):
    stream_id: str
    gross_usd: float = Field(ge=0)
    fees_usd: float = Field(0, ge=0)
    hours: float = Field(0, ge=0)
    notes: str = Field("", max_length=2_000)


class ReverseSolveRequest(BaseModel):
    target_monthly_usd: float = Field(gt=0)
    months: int = Field(gt=0, le=600)
    annual_yield_pct: float = Field(ge=0, le=100)
    monthly_contrib: float = Field(0, ge=0)


def build_paper_projections(allocations, ranked, months: int = 24) -> dict[str, list[float]]:
    """Return total monthly paper-asset income using each allocation's own yield."""
    series: dict[str, list[float]] = {"bear": [0.0] * months, "base": [0.0] * months, "bull": [0.0] * months}
    by_stream_id = {item.stream.stream_id: item.stream for item in ranked}

    for allocation in allocations:
        stream = by_stream_id.get(allocation.stream_id)
        if not stream or stream.category != "paper" or stream.yield_.unit != "annual_pct_on_capital":
            continue
        projection = project_paper(
            allocation.allocation_usd,
            stream.yield_.base,
            0,
            months,
            reinvest=False,
            scenario_yields={
                "bear": stream.yield_.bear,
                "base": stream.yield_.base,
                "bull": stream.yield_.bull,
            },
        )
        for scenario in series:
            series[scenario] = [
                round(total + projection[scenario][f"income_month_{month}"], 2)
                for month, total in enumerate(series[scenario], start=1)
            ]
    return series


@app.get("/health")
async def health():
    """Readiness endpoint for local use and deployment checks."""
    return {"status": "ok", "catalog_streams": len(load_catalog(CATALOG_DIR))}


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

    projection_series = build_paper_projections(alloc.allocations, ranked)
    monthly_proj = {scenario: values[11] for scenario, values in projection_series.items()}
    qualified_top5 = [item.stream.stream_id for item in ranked if not item.disqualified][:5]
    from pia.storage import save_run
    save_run(
        run_id=f"web-{profile.profile_id}-{uuid.uuid4().hex[:8]}",
        profile_id=profile.profile_id,
        profile_json=profile.model_dump_json(),
        top5_ids=qualified_top5,
        total_deployed=alloc.total_deployed,
        projected_base=monthly_proj["base"],
    )

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
                "public_face_requirement": r.stream.public_face_requirement,
                "customer_support_requirement": r.stream.customer_support_requirement,
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
                "yield_as_of": r.stream.yield_.as_of,
                "data_freshness": r.stream.data_freshness,
                "sources_note": r.stream.sources_note,
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


@app.post("/api/intake")
async def intake(req: IntakeRequest):
    if not req.text.strip():
        raise HTTPException(status_code=422, detail="Description text is required.")

    from pia.ai.intake import intake_from_text_with_source
    try:
        profile, intake_source = intake_from_text_with_source(req.text)
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Could not extract a profile from that description: {e}")

    payload = profile.model_dump(mode="json")
    payload["intake_source"] = intake_source
    return payload


@app.get("/api/streams")
async def list_streams():
    streams = load_catalog(CATALOG_DIR)
    return [
        {
            "stream_id": s.stream_id,
            "name": s.name,
            "category": s.category,
            "passivity_index": s.passivity_index,
            "public_face_requirement": s.public_face_requirement,
            "customer_support_requirement": s.customer_support_requirement,
            "yield_bear": s.yield_.bear,
            "yield_base": s.yield_.base,
            "yield_bull": s.yield_.bull,
            "yield_unit": s.yield_.unit,
            "yield_as_of": s.yield_.as_of,
            "data_freshness": s.data_freshness,
            "sources_note": s.sources_note,
            "maintenance_hours_per_month": s.maintenance_hours_per_month.steady,
            "is_stale": s.is_stale,
        }
        for s in streams
    ]


@app.get("/api/runs")
async def runs():
    from pia.storage import list_runs

    return {"runs": list_runs()}


@app.get("/api/tracker")
async def tracker_history():
    from pia.tracker import list_income_logs

    entries = list_income_logs()
    return {
        "entries": entries,
        "total_net_usd": round(sum(entry["net_usd"] for entry in entries), 2),
        "total_hours": round(sum(entry["hours"] for entry in entries), 2),
    }


@app.post("/api/tracker")
async def tracker_log(req: IncomeLogRequest):
    from pia.tracker import log_income

    stream_ids = {stream.stream_id for stream in load_catalog(CATALOG_DIR)}
    if req.stream_id not in stream_ids:
        raise HTTPException(status_code=404, detail=f"Stream '{req.stream_id}' not found")
    log_income(req.stream_id, req.gross_usd, req.fees_usd, req.hours, req.notes)
    return await tracker_history()


@app.post("/api/reverse-solve")
async def reverse_solver(req: ReverseSolveRequest):
    from pia.engine.projector import reverse_solve

    return reverse_solve(
        req.target_monthly_usd,
        req.months,
        req.annual_yield_pct,
        req.monthly_contrib,
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
