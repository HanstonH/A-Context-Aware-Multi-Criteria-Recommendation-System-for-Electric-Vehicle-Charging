"""FastAPI wrapper around Calculation_Model so Node.js can call /recommend."""
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")  # explicit path, launch-dir independent

import os
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from API import TDXClient, TDX_CITIES
from logic import Calculation_Model

app = FastAPI(title="EV Charging Recommender")

# One shared TDX client for the process — reuses its cached OAuth token
# across all requests instead of re-authenticating per call.
_CLIENT_ID = os.getenv("TDX_CLIENT_ID")
_CLIENT_SECRET = os.getenv("TDX_CLIENT_SECRET")
if not _CLIENT_ID or not _CLIENT_SECRET:
    raise RuntimeError("TDX_CLIENT_ID / TDX_CLIENT_SECRET not set in environment")

tdx_client = TDXClient(_CLIENT_ID, _CLIENT_SECRET)


class RecommendRequest(BaseModel):
    lat: float
    lng: float
    battery_percent: float = Field(ge=0, le=100)
    city: str = "Taipei"
    is_available_now: bool = False
    full_range_km: float = 300.0
    range_safety_factor: float = 0.8
    max_candidates: int = 10


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/recommend")
def recommend(req: RecommendRequest):
    if req.city not in TDX_CITIES:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown city '{req.city}'. Valid: {', '.join(TDX_CITIES)}",
        )
    try:
        model = Calculation_Model(
            user_location=(req.lat, req.lng),
            battery_percent=req.battery_percent,
            is_available_now=req.is_available_now,
            city=req.city,
            full_range_km=req.full_range_km,
            range_safety_factor=req.range_safety_factor,
            max_candidates=req.max_candidates,
            tdx_client=tdx_client,  # shared, token-cached client
        )
        df = model.recommend()
        return {"recommendations": df.to_dict(orient="records")}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
