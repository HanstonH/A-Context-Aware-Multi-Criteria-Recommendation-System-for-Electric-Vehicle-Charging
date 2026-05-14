"""Feature engineering for real-time inference.

Replicates the training pipeline's feature construction so that a single
(station, datetime, weather) tuple can be turned into a model-ready vector.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

import joblib
import numpy as np
import pandas as pd
from pandas.tseries.holiday import USFederalHolidayCalendar
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler, TargetEncoder

from .config import (
    CLEANED_DATA_PATH,
    FEATURE_COLUMNS,
    NUMERIC_FEATURES,
)
from .stations import Station
from .weather import WeatherSnapshot


_HOLIDAY_CAL = USFederalHolidayCalendar()


def build_raw_feature_row(
    station: Station,
    weather: WeatherSnapshot,
    dt: Optional[datetime] = None,
) -> pd.DataFrame:
    """Build a single-row DataFrame with the same schema as the training set."""
    if dt is None:
        dt = datetime.now()

    hour = dt.hour
    minute = dt.minute
    dow = dt.weekday()
    month = dt.month
    is_weekend = int(dow >= 5)
    holidays = _HOLIDAY_CAL.holidays(start=str(dt.year), end=str(dt.year))
    is_holiday = int(pd.Timestamp(dt.date()) in holidays)

    row = {
        "MAC Address": station.mac,
        "temp": weather.temperature,
        "precip": weather.precipitation,
        "clouds": weather.cloud_cover,
        "Minute": minute,
        "Hour": hour,
        "DayOfWeek": dow,
        "Month": month,
        "IsWeekend": is_weekend,
        "IsHoliday": is_holiday,
        "Hour_Sin": np.sin(2 * np.pi * hour / 24),
        "Hour_Cos": np.cos(2 * np.pi * hour / 24),
        "Month_Sin": np.sin(2 * np.pi * month / 12),
        "Month_Cos": np.cos(2 * np.pi * month / 12),
        "Plug Type Encoded": station.plug_encoded,
    }
    return pd.DataFrame([row], columns=FEATURE_COLUMNS)


class InferencePreprocessor:
    """Loads (or re-fits) the preprocessing pipeline used during training.

    Two independent pipelines are maintained — one per target variable — because
    ``TargetEncoder`` learns different mappings for availability (binary) vs
    session duration (continuous).
    """

    def __init__(self):
        self._pipeline_a: Optional[Pipeline] = None  # availability
        self._pipeline_b: Optional[Pipeline] = None  # duration

    def _fit_from_data(self, target_col: str) -> Pipeline:
        df = pd.read_csv(str(CLEANED_DATA_PATH), low_memory=False)
        target = df[target_col].copy()
        feature_df = df.drop(
            columns=[c for c in ("Availability", "Total_Duration_Secs") if c in df.columns],
        )

        self._original_columns = list(feature_df.columns)
        num_attribs = [c for c in feature_df.select_dtypes(include="number").columns]
        cat_attribs = ["MAC Address"]

        preprocessor = ColumnTransformer(
            transformers=[
                ("mac_target", TargetEncoder(), cat_attribs),
                ("std_scaler", StandardScaler(), num_attribs),
            ],
            remainder="passthrough",
        )

        pipe = Pipeline([("preprocessor", preprocessor)])
        pipe.fit(feature_df, target)
        return pipe

    def _get_pipeline(self, model_type: str) -> Pipeline:
        if model_type == "availability":
            if self._pipeline_a is None:
                self._pipeline_a = self._fit_from_data("Availability")
            return self._pipeline_a
        else:
            if self._pipeline_b is None:
                self._pipeline_b = self._fit_from_data("Total_Duration_Secs")
            return self._pipeline_b

    def transform(
        self,
        raw_df: pd.DataFrame,
        model_type: str = "availability",
    ) -> pd.DataFrame:
        pipe = self._get_pipeline(model_type)
        transformed = pipe.transform(raw_df)
        arr = np.asarray(transformed)
        cols = self._original_columns if self._original_columns else [f"f{i}" for i in range(arr.shape[1])]
        return pd.DataFrame(arr, columns=cols)
