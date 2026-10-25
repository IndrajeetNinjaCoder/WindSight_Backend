from datetime import date, datetime, timezone

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from app.schemas import AnalysisResponse, Metrics
from app.services.analytics import build_analysis
from app.services.elexon import ElexonAPIError, fetch_actuals, fetch_forecasts

app = FastAPI(
    title="WindSight API",
    description="Wind generation forecast accuracy analytics using Elexon data.",
    version="1.0.0",
)

# For local development. Set FRONTEND_ORIGIN to your deployed frontend URL later.
import os

frontend_origin = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[frontend_origin, "http://127.0.0.1:5173"],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "WindSight API"}


@app.get("/api/analysis", response_model=AnalysisResponse)
async def get_analysis(
    delivery_date: date = Query(
        ..., description="Delivery date in January 2026, YYYY-MM-DD"
    ),
    decision_cutoff: datetime = Query(
        ...,
        description="Decision timestamp with timezone, e.g. 2026-01-14T12:00:00Z",
    ),
):
    if delivery_date.year != 2026 or delivery_date.month != 1:
        raise HTTPException(
            status_code=400,
            detail="This assignment is restricted to delivery dates in January 2026.",
        )

    if decision_cutoff.tzinfo is None:
        raise HTTPException(
            status_code=400,
            detail="decision_cutoff must include a timezone, e.g. Z for UTC.",
        )

    if decision_cutoff > datetime.now(timezone.utc):
        raise HTTPException(
            status_code=400,
            detail="decision_cutoff cannot be in the future.",
        )

    try:
        actuals = await fetch_actuals(delivery_date)
        forecasts = await fetch_forecasts(delivery_date, decision_cutoff)

        metrics, points = build_analysis(
            actuals,
            forecasts,
            decision_cutoff,
            delivery_date,
        )

        return AnalysisResponse(
            delivery_date=delivery_date,
            decision_cutoff=decision_cutoff,
            metrics=Metrics(**metrics),
            points=points,
        )

    except ElexonAPIError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        # Keep detailed exceptions in server logs, not the public response.
        print(f"Unexpected analysis error: {exc}")
        raise HTTPException(
            status_code=500,
            detail="Unexpected error while building the analysis.",
        ) from exc