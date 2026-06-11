"""Shared feature construction for ev_pathfinder inference."""

from __future__ import annotations

from datetime import datetime
from functools import lru_cache
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd
from pandas.tseries.holiday import USFederalHolidayCalendar

from .config import FEATURE_COLUMNS, UNIT_PRICE_PATH

_HOLIDAY_CAL = USFederalHolidayCalendar()
_CLOUD_FRACTION_SCALE = 100.0
_LIGHT_PRECIP_MM = 2.5
_COMFORT_TEMP_C = 22.5


@lru_cache(maxsize=1)
def _fee_lookup() -> tuple[Dict[str, float], float]:
    price_df = pd.read_csv(UNIT_PRICE_PATH)
    price_df["Station Name"] = price_df["Station Name"].astype(str).str.strip()
    costs = pd.to_numeric(price_df["median_unit_price_per_kwh"], errors="coerce")
    mapping = price_df.set_index("Station Name")["median_unit_price_per_kwh"].to_dict()
    default = float(costs.median()) if costs.notna().any() else 0.0
    return mapping, default


def station_fee(station_name: str) -> float:
    mapping, default = _fee_lookup()
    return float(mapping.get(str(station_name).strip(), default))


def holiday_proximity(dt: datetime) -> tuple[int, int]:
    session_day = np.datetime64(pd.Timestamp(dt.date()), "D")
    start = pd.Timestamp(dt.date()) - pd.Timedelta(days=400)
    end = pd.Timestamp(dt.date()) + pd.Timedelta(days=400)
    holidays = (
        pd.DatetimeIndex(_HOLIDAY_CAL.holidays(start=start, end=end))
        .normalize()
        .unique()
        .values
        .astype("datetime64[D]")
    )

    next_idx = np.searchsorted(holidays, session_day, side="right")
    prev_idx = next_idx - 1

    days_until = int((holidays[next_idx] - session_day).astype(int)) if next_idx < len(holidays) else 0
    days_since = int((session_day - holidays[prev_idx]).astype(int)) if prev_idx >= 0 else 0
    return days_until, days_since


def parasitic_load_probability(temp: float, precip: float) -> int:
    if temp <= 0 and precip > 0:
        return 3
    if temp < 5 or temp > 30:
        return 2
    if (5 <= temp < 15) or (0 < precip <= _LIGHT_PRECIP_MM):
        return 1
    if 15 <= temp <= 25 and precip <= 0:
        return 0
    return 1


def add_time_features(row: Dict[str, Any], dt: datetime) -> None:
    hour = dt.hour
    month = dt.month
    dow = dt.weekday()
    holidays = _HOLIDAY_CAL.holidays(start=str(dt.year), end=str(dt.year))
    row.setdefault("Minute", dt.minute)
    row.setdefault("Hour", hour)
    row.setdefault("DayOfWeek", dow)
    row.setdefault("Month", month)
    row.setdefault("IsWeekend", int(dow >= 5))
    row.setdefault("IsHoliday", int(pd.Timestamp(dt.date()) in holidays))
    row.setdefault("Hour_Sin", np.sin(2 * np.pi * hour / 24))
    row.setdefault("Hour_Cos", np.cos(2 * np.pi * hour / 24))
    row.setdefault("Month_Sin", np.sin(2 * np.pi * month / 12))
    row.setdefault("Month_Cos", np.cos(2 * np.pi * month / 12))


def add_engineered_features(row: Dict[str, Any], dt: datetime) -> None:
    days_until, days_since = holiday_proximity(dt)
    row.setdefault("Days_Until_Next_Holiday", days_until)
    row.setdefault("Days_Since_Last_Holiday", days_since)

    temp = float(row.get("temp", _COMFORT_TEMP_C) or _COMFORT_TEMP_C)
    precip = float(row.get("precip", 0.0) or 0.0)
    clouds = float(row.get("clouds", 0.0) or 0.0)
    clouds_frac = clouds / _CLOUD_FRACTION_SCALE if clouds > 1.0 else clouds

    row.setdefault("Thermal_Deviation_Index", abs(temp - _COMFORT_TEMP_C))
    row.setdefault("Is_Freezing_Penalty", int(temp <= 0))
    row.setdefault("Extreme_Heat_Throttle_Risk", int(temp >= 35))
    row.setdefault("Solar_Irradiance_Proxy", int(temp > 30 and clouds_frac < 0.2))
    row.setdefault("Parasitic_Load_Probability_Index", parasitic_load_probability(temp, precip))


def complete_model_row(
    row: Dict[str, Any],
    *,
    dt: Optional[datetime] = None,
    station_name: Optional[str] = None,
    fee: Optional[float] = None,
) -> pd.DataFrame:
    """Fill the full training schema expected by the inference preprocessors."""
    row = dict(row)
    dt = dt or datetime.now()

    add_time_features(row, dt)

    if fee is None and station_name is not None:
        fee = station_fee(station_name)
    row.setdefault("fee", fee if fee is not None else 0.0)

    add_engineered_features(row, dt)

    missing = [column for column in FEATURE_COLUMNS if column not in row]
    if missing:
        raise ValueError(f"Missing required feature columns: {missing}")

    return pd.DataFrame([{column: row[column] for column in FEATURE_COLUMNS}], columns=FEATURE_COLUMNS)
