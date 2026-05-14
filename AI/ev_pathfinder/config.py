"""Centralised configuration for the EV-Pathfinder Orchestrator."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# ── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent          # …/AI
DATA_DIR = BASE_DIR / "data"
MODEL_A_DIR = BASE_DIR / "model"                           # availability classifiers
MODEL_B_DIR = BASE_DIR / "model_B"                         # duration regressors
PREPROCESSOR_PATH = BASE_DIR / "preprocessor_pipeline.joblib"
RAW_DATA_PATH = DATA_DIR / "ChargePointData2011-2020-ManullyPreCleaned3.csv"
CLEANED_DATA_PATH = DATA_DIR / "Final_Cleaned_Dataset.csv"

# ── API Keys ─────────────────────────────────────────────────────────────────
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "")

# ── Palo Alto Bounding Box ───────────────────────────────────────────────────
PALO_ALTO_BOUNDS = {
    "lat_min": 37.3685,
    "lat_max": 37.4725,
    "lon_min": -122.1900,
    "lon_max": -122.0950,
}

PALO_ALTO_CENTER = (37.4419, -122.1430)

# ── Feature Schema (matches training pipeline) ──────────────────────────────
FEATURE_COLUMNS = [
    "MAC Address",
    "temp", "precip", "clouds",
    "Minute", "Hour", "DayOfWeek", "Month",
    "IsWeekend", "IsHoliday",
    "Hour_Sin", "Hour_Cos",
    "Month_Sin", "Month_Cos",
    "Plug Type Encoded",
]

NUMERIC_FEATURES = [c for c in FEATURE_COLUMNS if c != "MAC Address"]

PLUG_TYPE_MAP = {"J1772": 0, "NEMA 5-20R": 1}

# ── Radius for "Find Closest" mode (miles → metres) ─────────────────────────
SEARCH_RADIUS_MILES = 5
SEARCH_RADIUS_METRES = SEARCH_RADIUS_MILES * 1609.34

# ── Google Routes API ────────────────────────────────────────────────────────
ROUTES_API_URL = "https://routes.googleapis.com/directions/v2:computeRoutes"

# ── Open-Meteo (weather, no key required) ────────────────────────────────────
WEATHER_API_URL = "https://api.open-meteo.com/v1/forecast"
