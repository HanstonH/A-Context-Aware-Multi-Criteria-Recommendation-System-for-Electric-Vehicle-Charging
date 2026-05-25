'''
Make a model that chooses based on 
1. Distance, done
Distance logic that needs to follow the road (not just a straight line from A to B) 

2. Waiting time (How many people are using) done
use a machine learning model to predict whether it will be vacant when you get there. 
Then use that value to the algorithm

3. Cost (how expensive the station is)

4. POI score (make own logic), done
'''
from __future__ import annotations

import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Union

import numpy as np
import pandas as pd
from pandas.tseries.holiday import USFederalHolidayCalendar

from get_Distance_EV import get_distance_ev
from get_POI import Get_POI

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from config import (  # noqa: E402
    FEATURE_COLUMNS,
    MODEL_A_DIR,
    PLUG_TYPE_MAP,
    RAW_DATA_PATH,
)
from model_a import ModelAService  # noqa: E402
from model_b import ModelBService  # noqa: E402
from preprocessing import InferencePreprocessor  # noqa: E402

_HOLIDAY_CAL = USFederalHolidayCalendar()
_CLOUD_FRACTION_SCALE = 100.0
_LIGHT_PRECIP_MM = 2.5
_COMFORT_TEMP_C = 22.5

WaitInput = Union[Dict[str, Any], pd.Series, pd.DataFrame]


class Calculation_Model:

    def __init__(self, user_location):
        self.w_poi = 0.25
        self.w_cost = 0.25
        self.w_dist = 0.25
        self.w_wait = 0.25
        self.user_location = user_location
        self._preprocessor: Optional[InferencePreprocessor] = None
        self._model_a: Optional[ModelAService] = None
        self._model_b: Optional[ModelBService] = None

    def _ensure_wait_models(self) -> None:
        """Lazy-load Model A, Model B, and the inference preprocessor."""
        if self._preprocessor is None:
            self._preprocessor = InferencePreprocessor()
            self._model_a = ModelAService()
            self._model_b = ModelBService()

    @staticmethod
    def _encode_plug_type(value: Any) -> int:
        if isinstance(value, (int, np.integer)) and not isinstance(value, bool):
            return int(value)
        if isinstance(value, float) and value in (0.0, 1.0):
            return int(value)
        key = str(value).strip()
        if key in PLUG_TYPE_MAP:
            return PLUG_TYPE_MAP[key]
        raise ValueError(
            f"Unknown plug type {value!r}. Use 0/1 or one of {list(PLUG_TYPE_MAP)}."
        )

    @classmethod
    def _add_time_features(cls, row: Dict[str, Any], dt: datetime) -> None:
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

    @staticmethod
    def _holiday_proximity(dt: datetime) -> tuple[int, int]:
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

    @staticmethod
    def _parasitic_load_probability(temp: float, precip: float) -> int:
        if temp <= 0 and precip > 0:
            return 3
        if temp < 5 or temp > 30:
            return 2
        if (5 <= temp < 15) or (0 < precip <= _LIGHT_PRECIP_MM):
            return 1
        if 15 <= temp <= 25 and precip <= 0:
            return 0
        return 1

    @classmethod
    def _add_engineered_model_features(cls, row: Dict[str, Any], dt: datetime) -> None:
        days_until, days_since = cls._holiday_proximity(dt)
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
        row.setdefault("Parasitic_Load_Probability_Index", cls._parasitic_load_probability(temp, precip))

    @classmethod
    def _feature_row_from_input(
        cls,
        data: WaitInput,
        *,
        at_time: Optional[datetime] = None,
    ) -> pd.DataFrame:
        """Normalize dict / Series / single-row DataFrame to one model-ready row."""
        if isinstance(data, pd.DataFrame):
            if len(data) != 1:
                raise ValueError("Expected a single-row DataFrame.")
            row = data.iloc[0].to_dict()
        elif isinstance(data, pd.Series):
            row = data.to_dict()
        elif isinstance(data, dict):
            row = dict(data)
        else:
            raise TypeError("data must be a dict, pandas Series, or single-row DataFrame.")

        if "Plug Type Encoded" not in row and "Plug Type" in row:
            row["Plug Type Encoded"] = cls._encode_plug_type(row.pop("Plug Type"))

        dt = at_time or datetime.now()
        if any(k not in row for k in ("Hour", "Minute", "DayOfWeek", "Month")):
            cls._add_time_features(row, dt)

        if "fee" not in row:
            row["fee"] = row.get("cost", 0.0)

        cls._add_engineered_model_features(row, dt)

        missing = [c for c in FEATURE_COLUMNS if c not in row]
        if missing:
            raise ValueError(
                f"Missing required feature columns: {missing}. "
                f"Expected schema: {FEATURE_COLUMNS}"
            )

        return pd.DataFrame([{c: row[c] for c in FEATURE_COLUMNS}], columns=FEATURE_COLUMNS)

    @staticmethod
    def _normalize_higher_is_better(series: pd.Series) -> pd.Series:
        values = pd.to_numeric(series, errors="coerce")
        max_value = values.max()
        if pd.isna(max_value) or max_value <= 0:
            return pd.Series(0.0, index=series.index)
        return values.fillna(0.0) / max_value

    @staticmethod
    def _normalize_lower_is_better(series: pd.Series) -> pd.Series:
        values = pd.to_numeric(series, errors="coerce")
        min_value = values.min()
        max_value = values.max()
        if pd.isna(min_value) or pd.isna(max_value):
            return pd.Series(0.0, index=series.index)
        if max_value == min_value:
            return pd.Series(1.0, index=series.index)
        return ((max_value - values) / (max_value - min_value)).fillna(0.0)

    @staticmethod
    def _ensure_cost_column(stations_df: pd.DataFrame) -> pd.DataFrame:
        if "cost" in stations_df.columns:
            return stations_df

        for column in ("median_unit_price_per_kwh", "price_tier", "fee", "price"):
            if column in stations_df.columns:
                stations_df["cost"] = stations_df[column]
                return stations_df

        raise ValueError(
            "total_score() requires a cost column. Add `cost`, `median_unit_price_per_kwh`, "
            "`price_tier`, `fee`, or `price` to the station DataFrame."
        )

    def total_score(self, stations_df):
        """
        Calculates the final recommendation score using weighted sum normalization.
        Expects columns: ['poi_sum', 'distance', 'waiting_time', 'cost'].
        `waiting_time` should be in seconds; lower values are better.
        """
        stations_df = self._ensure_cost_column(stations_df)

        required_columns = ["poi_sum", "distance", "waiting_time", "cost"]
        missing = [column for column in required_columns if column not in stations_df.columns]
        if missing:
            raise ValueError(f"total_score() missing required columns: {missing}")

        # Benefit: higher POI score is better.
        stations_df['n_poi'] = self._normalize_higher_is_better(stations_df['poi_sum'])

        # Costs: lower distance, waiting time, and price are better.
        stations_df['n_dist'] = self._normalize_lower_is_better(stations_df['distance'])
        stations_df['n_wait'] = self._normalize_lower_is_better(stations_df['waiting_time'])
        stations_df['n_cost'] = self._normalize_lower_is_better(stations_df['cost'])

        stations_df['total_score'] = (
            (self.w_poi * stations_df['n_poi']) +
            (self.w_dist * stations_df['n_dist']) +
            (self.w_wait * stations_df['n_wait']) +
            (self.w_cost * stations_df['n_cost'])
        )

        return stations_df.sort_values(by='total_score', ascending=False)

    def get_POI(self, latitude, longitude):
    # Returns JSON file of POI around as well as data of it (max 20 top POI)
        POI = Get_POI()
        return POI.call_API(latitude, longitude)

    def get_distance_score(self, destination_location, user_location):
        return get_distance_ev(destination_location, user_location)
    
    def POI_score(self, data, coordinate_key):
        # Google Places API (New) returns a dict with 'places' and 'routingSummaries' keys
        if not data or 'places' not in data:
            return 0
        
        place_list = pd.json_normalize(data, record_path=["places"])
        
        if 'routingSummaries' in data:
            place_distance = pd.json_normalize(data['routingSummaries'], record_path=['legs'])
            place = pd.concat([place_list, place_distance], axis=1)
        else:
            place = place_list
            # Provide a default distance if routing failed (e.g., 500m)
            place['distanceMeters'] = 500 

        # Handle cases where rating or userRatingCount might be missing from some POIs
        place['rating'] = place['rating'].fillna(0)
        place['userRatingCount'] = place['userRatingCount'].fillna(0)

        place['poi_score'] = place.apply(self.calculate_poi_score, axis=1)
        return place['poi_score'].sum()
    
    # Helper function
    def calculate_poi_score(self, row):
        rating = row['rating']
        reviews = row['userRatingCount']
        distance = row['distanceMeters']
        
        # We add 1 to reviews to avoid log(0)
        score = (rating * np.log10(reviews + 1))/ (1 + distance/100)
        return score

    def process_all_stations(self, df):
        """
        Iterates through the dataframe, fetches POI data, 
        and calculates the POI sum for each row.
        """
        # 1. Create a unique key for each station based on coordinates
        # This matches the 'coordinate_key' used in your JSON data
        df['coord_key'] = df.apply(lambda row: f"{row['lat']},{row['lon']}", axis=1)
        
        def row_pipeline(row):
            # A. Fetch the raw JSON data (API Call)
            # Pro-tip: In a real scenario, you'd check a CACHE here first!
            raw_json = self.get_POI(row['lat'], row['lon'])
            
            # B. Calculate the POI Score for this specific row
            # We pass the coord_key so the function knows which part of the JSON to read
            score = self.POI_score(raw_json, row['coord_key'])
            return score

        # 2. Apply the pipeline to every row
        print("Fetching POI data and calculating scores... this may take a moment.")
        df['poi_sum'] = df.apply(row_pipeline, axis=1)
        
        return df
        
    def process_distances(self, df):
        """
        Applies the external distance function to every row in the dataframe.
        """
        def get_row_dist(row):
            dest = (row['lat'], row['lon'])
            # Call the imported function
            result = get_distance_ev(dest, self.user_location)
            
            # Extract just the meters from the JSON result
            if result and 'routes' in result:
                return result['routes'][0]['distanceMeters']
            return 999999 # Penalty for failed API call
            
        df['distance'] = df.apply(get_row_dist, axis=1)
        return df

    def predict_waiting_time(
        self,
        data: WaitInput,
        *,
        at_time: Optional[datetime] = None,
        return_minutes: bool = True,
        return_details: bool = False,
    ) -> Union[float, Dict[str, Any]]:
        """
        Predict waiting time for one station using Model A (``model/``) and Model B (``model_B/``).

        Model A classifies availability. If the station is predicted **available**, waiting
        time is 0. If **occupied**, Model B predicts session duration in seconds (ensemble
        average of regressors).

        Parameters
        ----------
        data : dict, Series, or single-row DataFrame
            Must include training features, e.g. ``MAC Address``, weather (``temp``,
            ``precip``, ``clouds``), and ``Plug Type Encoded`` (or ``Plug Type`` as
            ``J1772`` / ``NEMA 5-20R``). Time fields are filled from ``at_time`` when
            omitted.
        at_time : datetime, optional
            Timestamp for cyclical / calendar features when not provided in ``data``.
        return_minutes : bool
            If True (default), return waiting time in **minutes**.
            If False, return seconds.
        return_details : bool
            If True, return a dict with availability consensus, per-model outputs, and
            wait time.

        Returns
        -------
        float or dict
            Waiting time in minutes (default) or seconds, or a details dict when
            ``return_details=True``.
        """
        self._ensure_wait_models()
        raw_df = self._feature_row_from_input(data, at_time=at_time)

        if not self._model_a.loaded:
            raise RuntimeError(
                f"No Model A (availability) artifacts found in {MODEL_A_DIR}. "
                "Train with Time Series Forecast.ipynb and save classifiers to model/."
            )

        features_a = self._preprocessor.transform(raw_df, model_type="availability")
        consensus = self._model_a.predict_consensus(features_a)
        available = consensus.available if consensus else True

        wait_secs = 0.0
        duration_preds = []
        if not available:
            if not self._model_b.loaded:
                raise RuntimeError(
                    "Station predicted occupied but no Model B artifacts found in model_B/."
                )
            features_b = self._preprocessor.transform(raw_df, model_type="duration")
            duration_preds = self._model_b.predict(features_b)
            ensemble = self._model_b.predict_ensemble(features_b)
            if ensemble:
                wait_secs = ensemble.duration_secs

        wait_mins = round(wait_secs / 60, 1)
        value = wait_mins if return_minutes else wait_secs

        if not return_details:
            return value

        return {
            "waiting_time": value,
            "waiting_time_secs": wait_secs,
            "waiting_time_mins": wait_mins,
            "available": available,
            "status": "Available" if available else "Occupied",
            "availability_consensus": asdict(consensus) if consensus else None,
            "duration_predictions": [asdict(p) for p in duration_preds],
        }

    def process_waiting_times(
        self,
        df: pd.DataFrame,
        *,
        feature_columns: Optional[list] = None,
        at_time: Optional[datetime] = None,
    ) -> pd.DataFrame:
        """Add ``waiting_time`` (seconds) column by applying ``predict_waiting_time`` to each row."""
        if feature_columns is not None:
            missing = [c for c in feature_columns if c not in df.columns]
            if missing:
                raise ValueError(f"DataFrame missing columns for wait prediction: {missing}")

        def _row_wait(row: pd.Series) -> float:
            payload = row.to_dict()
            if feature_columns is not None:
                payload = {c: row[c] for c in feature_columns}
            return self.predict_waiting_time(payload, at_time=at_time, return_minutes=False)

        df = df.copy()
        df["waiting_time"] = df.apply(_row_wait, axis=1)
        return df


def build_chargepoint_test_dataset(
    raw_path: Union[str, Path] = RAW_DATA_PATH,
    *,
    sample_size: int = 4,
    at_time: Optional[datetime] = None,
) -> tuple[tuple[float, float], pd.DataFrame]:
    """
    Build a small station-level test set from the raw ChargePoint sessions.

    The raw dataset has session rows, so this function collapses it to unique
    stations, derives cost from historical fees, and adds the feature columns
    needed by the wait-time models.
    """
    columns = [
        "Station Name",
        "MAC Address",
        "Start Date",
        "Energy (kWh)",
        "Plug Type",
        "Latitude",
        "Longitude",
        "Fee",
    ]
    raw = pd.read_csv(raw_path, usecols=columns)
    raw = raw.dropna(subset=["Station Name", "MAC Address", "Latitude", "Longitude", "Plug Type"])
    raw = raw[raw["Plug Type"].isin(PLUG_TYPE_MAP)]

    raw["Start Date"] = pd.to_datetime(raw["Start Date"], errors="coerce")
    raw["Fee"] = pd.to_numeric(raw["Fee"], errors="coerce").fillna(0.0)
    raw["Energy (kWh)"] = pd.to_numeric(raw["Energy (kWh)"], errors="coerce")

    raw["unit_cost"] = np.where(
        raw["Energy (kWh)"] > 0,
        raw["Fee"] / raw["Energy (kWh)"],
        raw["Fee"],
    )
    raw["unit_cost"] = (
        raw["unit_cost"]
        .replace([np.inf, -np.inf], np.nan)
        .fillna(raw["Fee"])
        .fillna(0.0)
    )

    cost_by_station = raw.groupby("Station Name")["unit_cost"].median()
    stations = (
        raw.sort_values("Start Date")
        .drop_duplicates("Station Name", keep="last")
        .rename(columns={"Latitude": "lat", "Longitude": "lon"})
    )
    stations["cost"] = stations["Station Name"].map(cost_by_station).fillna(0.0)
    stations["Plug Type Encoded"] = stations["Plug Type"].apply(Calculation_Model._encode_plug_type)

    stations = stations.head(sample_size + 1).copy()
    if len(stations) < 2:
        raise ValueError("Need at least two valid ChargePoint stations to run the test pipeline.")

    user_row = stations.iloc[0]
    candidates = stations.iloc[1:].head(sample_size).copy()
    current_user_pos = (float(user_row["lat"]), float(user_row["lon"]))

    # The raw ChargePoint file has no weather columns, so use stable defaults
    # to exercise the inference pipeline.
    candidates["temp"] = 16.2
    candidates["precip"] = 0.0
    candidates["clouds"] = 56

    feature_time = {}
    Calculation_Model._add_time_features(feature_time, at_time or datetime.now())
    for column, value in feature_time.items():
        candidates[column] = value

    return current_user_pos, candidates


def main():
    current_user_pos, EV_station_dataset = build_chargepoint_test_dataset(sample_size=4)
    print(f"User test location: {current_user_pos}")

    model = Calculation_Model(current_user_pos)

    EV_station_dataset = model.process_distances(EV_station_dataset)
    EV_station_dataset = model.process_all_stations(EV_station_dataset)
    EV_station_dataset = model.process_waiting_times(EV_station_dataset)

    final_ranked_df = model.total_score(EV_station_dataset)
    final_ranked_df.to_csv("final_recommendations_summary.csv")
    print(
        final_ranked_df[
            [
                "Station Name",
                "distance",
                "poi_sum",
                "waiting_time",
                "cost",
                "total_score",
            ]
        ]
    )






if __name__ == "__main__":
    main()