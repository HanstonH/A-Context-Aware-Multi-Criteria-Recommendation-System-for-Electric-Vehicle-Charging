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

GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "")

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
