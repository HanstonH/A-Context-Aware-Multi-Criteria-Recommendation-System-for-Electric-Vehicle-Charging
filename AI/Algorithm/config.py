"""Configuration used by the recommendation algorithm."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ALGORITHM_DIR = Path(__file__).resolve().parent
AI_DIR = ALGORITHM_DIR.parent
DATA_DIR = AI_DIR / "data"

MODEL_A_DIR = ALGORITHM_DIR / "model"
MODEL_B_DIR = ALGORITHM_DIR / "model_B"
PREPROCESSOR_PATH = ALGORITHM_DIR / "preprocessor_pipeline.joblib"

RAW_DATA_PATH = DATA_DIR / "ChargePointData2011-2020-ManullyPreCleaned3.csv"
CLEANED_DATA_PATH = DATA_DIR / "Final_Cleaned_Dataset.csv"
UNIT_PRICE_PATH = DATA_DIR / "unit_price_by_station_palo_alto.csv"

GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "")

PALO_ALTO_BOUNDS = {
    "lat_min": 37.3685,
    "lat_max": 37.4725,
    "lon_min": -122.1900,
    "lon_max": -122.0950,
}
PALO_ALTO_CENTER = (37.4419, -122.1430)

FEATURE_COLUMNS = [
    "MAC Address",
    "temp", "precip", "clouds",
    "Minute", "Hour", "DayOfWeek", "Month",
    "IsWeekend", "IsHoliday",
    "Hour_Sin", "Hour_Cos",
    "Month_Sin", "Month_Cos",
    "Days_Until_Next_Holiday", "Days_Since_Last_Holiday",
    "Thermal_Deviation_Index",
    "Is_Freezing_Penalty",
    "Extreme_Heat_Throttle_Risk",
    "Solar_Irradiance_Proxy",
    "Parasitic_Load_Probability_Index",
    "Plug Type Encoded",
    "fee",
]

NUMERIC_FEATURES = [c for c in FEATURE_COLUMNS if c != "MAC Address"]
PLUG_TYPE_MAP = {"J1772": 0, "NEMA 5-20R": 1}

AVAILABILITY_THRESHOLD = 0.5

# SUMO EV_Car defaults (see Simulation/paloalto.rou.xml) — used for range before scoring
DEFAULT_MAX_BATTERY_WH = 60_000.0
DEFAULT_STOPPING_THRESHOLD_WH = 0.1  # SUMO stops the vehicle at or below this (Wh)
DEFAULT_INITIAL_CHARGE_WH = 5_000.0
# Calibrated order-of-magnitude from SUMO MMPEVEM at ~40 km/h; override via live telemetry
DEFAULT_WH_PER_KM = 180.0
RANGE_SAFETY_FACTOR = 0.85  # fraction of theoretical max range to keep as buffer
