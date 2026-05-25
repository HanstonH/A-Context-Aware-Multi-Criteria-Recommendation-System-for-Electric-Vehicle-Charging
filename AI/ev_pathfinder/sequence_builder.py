"""Data Context Engine -- retrieves and windows historical session data
for LSTM sequence inference.

Bridges the user's UI selection (station + timestamp) with the 12-step
temporal window required by the LSTM models.

Operational flow
----------------
1. At startup, build a per-station time-indexed history from the raw
   ChargePoint 2011-2020 CSV (feature-engineered, weather-merged).
2. At inference time, retrieve the 12 most recent sessions before the
   user-selected timestamp for a given station.
3. Apply the correct preprocessing pipeline (TargetEncoder for Model A
   LSTM, BinaryEncoder for Model B LSTM).
4. If fewer than 12 records exist, pad with the station's historical
   mean so the input shape remains (1, 12, features).
"""

from __future__ import annotations

import pickle
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Tuple

import joblib
import numpy as np
import pandas as pd
from pandas.tseries.holiday import USFederalHolidayCalendar

from .config import (
    BASE_DIR,
    DATA_DIR,
    FEATURE_COLUMNS,
    PREPROCESSOR_PATH,
    RAW_DATA_PATH,
    LSTM_TIME_STEPS,
    AVAILABILITY_THRESHOLD,
)

_CACHE_PATH = DATA_DIR / "sequence_history_cache.pkl"
_HOLIDAY_CAL = USFederalHolidayCalendar()

# Weather archive endpoint (same as used in training)
_WEATHER_URL = "https://archive-api.open-meteo.com/v1/archive"


class SequenceBuilder:
    """Builds (1, time_steps, n_features) arrays for LSTM inference."""

    def __init__(self):
        self._history: Optional[pd.DataFrame] = None
        self._pipeline_b_lstm = None     # BinaryEncoder pipeline for Model B LSTM
        self._pipeline_a_lstm = None     # TargetEncoder pipeline for Model A LSTM
        self._load_history()

    # ------------------------------------------------------------------
    # History construction
    # ------------------------------------------------------------------

    def _load_history(self) -> None:
        if _CACHE_PATH.exists():
            try:
                self._history = pd.read_pickle(str(_CACHE_PATH))
                print(f"[SequenceBuilder] Loaded cached history: "
                      f"{len(self._history)} rows, "
                      f"{self._history['MAC Address'].nunique()} stations.")
                return
            except Exception as exc:
                print(f"[SequenceBuilder] Cache load failed ({exc}), rebuilding...")

        self._history = self._build_history()
        try:
            self._history.to_pickle(str(_CACHE_PATH))
            print(f"[SequenceBuilder] History cached to {_CACHE_PATH}")
        except Exception as exc:
            print(f"[SequenceBuilder] Could not cache history: {exc}")

    def _build_history(self) -> pd.DataFrame:
        print("[SequenceBuilder] Building station history from raw data...")
        cols = [
            "MAC Address", "Start Date", "End Date",
            "Total Duration (hh:mm:ss)", "Plug Type",
        ]
        raw = pd.read_csv(str(RAW_DATA_PATH), usecols=cols, low_memory=False)
        raw["Start Date"] = pd.to_datetime(raw["Start Date"])
        raw["End Date"] = pd.to_datetime(raw["End Date"])
        raw = raw.sort_values(["MAC Address", "Start Date"]).reset_index(drop=True)

        raw["Total_Duration_Secs"] = self._duration_to_secs(
            raw["Total Duration (hh:mm:ss)"]
        )

        raw = self._engineer_time_features(raw)

        raw["Plug Type Encoded"] = (
            raw["Plug Type"]
            .map({"J1772": 0, "NEMA 5-20R": 1})
            .fillna(0)
            .astype(int)
        )

        print("[SequenceBuilder] Fetching historical Palo Alto weather...")
        raw = self._merge_weather(raw)

        keep = ["Start Date", "MAC Address", "Total_Duration_Secs",
                "temp", "precip", "clouds",
                "Minute", "Hour", "DayOfWeek", "Month",
                "IsWeekend", "IsHoliday",
                "Hour_Sin", "Hour_Cos", "Month_Sin", "Month_Cos",
                "Plug Type Encoded"]
        df = raw[keep].copy()
        df = df.sort_values(["MAC Address", "Start Date"]).reset_index(drop=True)
        print(f"[SequenceBuilder] Built history: {len(df)} rows, "
              f"{df['MAC Address'].nunique()} stations.")
        return df

    # ------------------------------------------------------------------
    # Sequence retrieval
    # ------------------------------------------------------------------

    def get_sequence(
        self,
        station_mac: str,
        target_time: Optional[datetime] = None,
        model_type: str = "duration",
    ) -> Tuple[np.ndarray, Dict]:
        """Return a preprocessed (1, time_steps, n_features) array.

        Parameters
        ----------
        station_mac : str
            MAC address of the target station.
        target_time : datetime or None
            The user-selected moment.  If ``None``, all historical
            records for the station are used (i.e. "most recent").
        model_type : str
            ``"availability"`` -> TargetEncoder pipeline (15 features)
            ``"duration"``     -> BinaryEncoder pipeline (21 features)

        Returns
        -------
        sequence : ndarray of shape (1, time_steps, n_features)
        context  : dict with metadata for the response
        """
        if self._history is None:
            raise RuntimeError("Station history not loaded.")

        station_df = self._history[
            self._history["MAC Address"] == station_mac
        ].copy()

        if target_time is not None:
            station_df = station_df[station_df["Start Date"] < target_time]

        station_df = station_df.sort_values("Start Date")
        n_available = len(station_df)
        padded = False

        feature_cols = [c for c in FEATURE_COLUMNS]  # excludes Start Date
        window = station_df[feature_cols].tail(LSTM_TIME_STEPS)

        if len(window) == 0:
            raise ValueError(
                f"No historical records for station {station_mac} "
                f"before {target_time}."
            )

        if len(window) < LSTM_TIME_STEPS:
            padded = True
            mean_row = window.mean(numeric_only=True)
            mac_val = window["MAC Address"].iloc[0]
            pad_rows = []
            for _ in range(LSTM_TIME_STEPS - len(window)):
                pad = mean_row.to_dict()
                pad["MAC Address"] = mac_val
                pad_rows.append(pad)
            pad_df = pd.DataFrame(pad_rows, columns=feature_cols)
            window = pd.concat([pad_df, window], ignore_index=True)

        preprocessed = self._preprocess_window(window, model_type)
        sequence = preprocessed.astype("float32")
        sequence = sequence.reshape(1, LSTM_TIME_STEPS, -1)

        earliest = station_df["Start Date"].iloc[-LSTM_TIME_STEPS] if n_available >= LSTM_TIME_STEPS else station_df["Start Date"].iloc[0]
        latest = station_df["Start Date"].iloc[-1] if n_available > 0 else None

        context = {
            "records_available": n_available,
            "records_used": min(n_available, LSTM_TIME_STEPS),
            "padded": padded,
            "pad_count": max(0, LSTM_TIME_STEPS - n_available),
            "window_start": str(earliest) if earliest is not None else None,
            "window_end": str(latest) if latest is not None else None,
            "confidence_note": self._build_confidence_note(
                n_available, padded, LSTM_TIME_STEPS - min(n_available, LSTM_TIME_STEPS),
            ),
        }
        return sequence, context

    # ------------------------------------------------------------------
    # Preprocessing helpers
    # ------------------------------------------------------------------

    def _preprocess_window(
        self, window_df: pd.DataFrame, model_type: str
    ) -> np.ndarray:
        if model_type == "duration":
            return self._preprocess_binary_encoder(window_df)
        else:
            return self._preprocess_target_encoder(window_df)

    def _preprocess_binary_encoder(self, df: pd.DataFrame) -> np.ndarray:
        """Apply the saved BinaryEncoder + StandardScaler pipeline (21 features)."""
        if self._pipeline_b_lstm is None:
            if PREPROCESSOR_PATH.exists():
                self._pipeline_b_lstm = joblib.load(str(PREPROCESSOR_PATH))
            else:
                raise FileNotFoundError(
                    f"BinaryEncoder pipeline not found at {PREPROCESSOR_PATH}"
                )
        transformed = self._pipeline_b_lstm.transform(df)
        return np.asarray(transformed)

    def set_preprocessor(self, preprocessor) -> None:
        """Share an existing InferencePreprocessor to avoid refitting."""
        self._pipeline_a_lstm = preprocessor

    def _preprocess_target_encoder(self, df: pd.DataFrame) -> np.ndarray:
        """TargetEncoder + StandardScaler pipeline (15 features)."""
        if self._pipeline_a_lstm is None:
            from .preprocessing import InferencePreprocessor
            self._pipeline_a_lstm = InferencePreprocessor()
        transformed = self._pipeline_a_lstm.transform(df, model_type="availability")
        return np.asarray(transformed)

    # ------------------------------------------------------------------
    # Feature engineering (replicates training logic)
    # ------------------------------------------------------------------

    @staticmethod
    def _duration_to_secs(series: pd.Series) -> pd.Series:
        parts = series.str.split(":", expand=True).astype(float)
        return (parts[0] * 3600) + (parts[1] * 60) + parts[2]

    @staticmethod
    def _engineer_time_features(df: pd.DataFrame) -> pd.DataFrame:
        dt = df["Start Date"]
        df["Minute"] = dt.dt.minute
        df["Hour"] = dt.dt.hour
        df["DayOfWeek"] = dt.dt.dayofweek
        df["Month"] = dt.dt.month
        df["IsWeekend"] = (df["DayOfWeek"] >= 5).astype(int)

        holidays = _HOLIDAY_CAL.holidays(
            start=dt.min(), end=dt.max()
        )
        df["IsHoliday"] = dt.dt.normalize().isin(holidays).astype(int)

        df["Hour_Sin"] = np.sin(2 * np.pi * df["Hour"] / 24)
        df["Hour_Cos"] = np.cos(2 * np.pi * df["Hour"] / 24)
        df["Month_Sin"] = np.sin(2 * np.pi * df["Month"] / 12)
        df["Month_Cos"] = np.cos(2 * np.pi * df["Month"] / 12)
        return df

    @staticmethod
    def _merge_weather(df: pd.DataFrame) -> pd.DataFrame:
        import requests

        start = df["Start Date"].min()
        end = df["Start Date"].max()

        try:
            resp = requests.get(_WEATHER_URL, params={
                "latitude": 37.4419,
                "longitude": -122.1430,
                "start_date": start.strftime("%Y-%m-%d"),
                "end_date": end.strftime("%Y-%m-%d"),
                "hourly": "temperature_2m,precipitation,cloudcover",
                "timezone": "America/Los_Angeles",
            }, timeout=30)
            data = resp.json()
            weather = pd.DataFrame({
                "weather_time": pd.to_datetime(data["hourly"]["time"]),
                "temp": data["hourly"]["temperature_2m"],
                "precip": data["hourly"]["precipitation"],
                "clouds": data["hourly"]["cloudcover"],
            })
            df["merge_hour"] = df["Start Date"].dt.floor("h")
            df = df.merge(weather, left_on="merge_hour",
                          right_on="weather_time", how="left")
            df.drop(columns=["merge_hour", "weather_time"], inplace=True)
        except Exception as exc:
            print(f"[SequenceBuilder] Weather fetch failed: {exc}. "
                   "Using defaults.")
            df["temp"] = 18.0
            df["precip"] = 0.0
            df["clouds"] = 50.0

        df["temp"] = df["temp"].fillna(18.0)
        df["precip"] = df["precip"].fillna(0.0)
        df["clouds"] = df["clouds"].fillna(50.0)
        return df

    # ------------------------------------------------------------------
    # Confidence narrative
    # ------------------------------------------------------------------

    @staticmethod
    def _build_confidence_note(
        n_records: int, padded: bool, pad_count: int
    ) -> str:
        if n_records == 0:
            return "No historical data. Prediction is unreliable."
        if padded:
            return (
                f"Only {n_records} session(s) found (need {LSTM_TIME_STEPS}). "
                f"{pad_count} step(s) were padded with the station mean. "
                f"Treat this estimate with caution."
            )
        if n_records < 50:
            return (
                f"Based on the last {LSTM_TIME_STEPS} of {n_records} total "
                f"sessions. Limited history may reduce accuracy."
            )
        return (
            f"Based on the last {LSTM_TIME_STEPS} sessions at this station "
            f"({n_records} total on record). High-confidence context."
        )
