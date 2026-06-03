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

# ── Availability Threshold ────────────────────────────────────────────────────
# Label convention in the ChargePoint training set:
#     0 = Available   (station is idle / no active session)
#     1 = Occupied    (station has an active charging session)
#
# For **classifiers** (XGBoost, RF, DT, LR):
#     model.predict()  returns 0 or 1 directly.
#     model.predict_proba() returns [P(class 0), P(class 1)].
#     Station is Available when P(class 0) > AVAILABILITY_THRESHOLD.
#
# For the **LSTM** (sigmoid output in [0, 1]):
#     output < AVAILABILITY_THRESHOLD  =>  Available
#     output >= AVAILABILITY_THRESHOLD =>  Occupied
#
# A threshold of 0.5 gives equal weight to false positives and false
# negatives.  Raise it (e.g. 0.6) to be more conservative — the system
# will report "Occupied" more often, reducing the chance of sending a
# user to a station that turns out to be busy.
AVAILABILITY_THRESHOLD = 0.5

# ── User battery search defaults (match Algorithm/config.py) ─────────────────
DEFAULT_MAX_BATTERY_WH = 60_000.0
DEFAULT_STOPPING_THRESHOLD_WH = 0.1
DEFAULT_WH_PER_KM = 180.0
RANGE_SAFETY_FACTOR = 0.85

# ── LSTM Sequence Parameters ─────────────────────────────────────────────────
LSTM_TIME_STEPS = 12
LSTM_A_FEATURES = 15       # TargetEncoder pipeline -> Model A LSTM
LSTM_B_FEATURES = 21       # BinaryEncoder pipeline -> Model B LSTM

# ── Radius for "Find Closest" mode (miles -> metres) ─────────────────────────
SEARCH_RADIUS_MILES = 5
SEARCH_RADIUS_METRES = SEARCH_RADIUS_MILES * 1609.34

# ── Google Routes API ────────────────────────────────────────────────────────
ROUTES_API_URL = "https://routes.googleapis.com/directions/v2:computeRoutes"

# ── Open-Meteo (weather, no key required) ────────────────────────────────────
WEATHER_API_URL = "https://api.open-meteo.com/v1/forecast"
