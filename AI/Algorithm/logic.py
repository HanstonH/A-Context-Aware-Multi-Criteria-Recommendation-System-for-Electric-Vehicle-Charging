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
from typing import Any, Dict, List, Optional, Union

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
    UNIT_PRICE_PATH,
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

    def total_score(self, stations_df, *, include_llm_context: bool = False):
        """
        Calculates the final recommendation score using weighted sum normalization.
        Expects columns: ['poi_sum', 'distance', 'waiting_time', 'cost'].
        `waiting_time` should be in seconds; lower values are better.

        When ``include_llm_context`` is True, adds ``rank``, weighted ``contrib_*``
        columns, ``score_explanation``, and ``llm_context`` (JSON-serializable dict per row)
        for use with ``llm.generate_ev_explanation``.
        """
        stations_df = self._ensure_cost_column(stations_df.copy())

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

        stations_df['contrib_poi'] = self.w_poi * stations_df['n_poi']
        stations_df['contrib_dist'] = self.w_dist * stations_df['n_dist']
        stations_df['contrib_wait'] = self.w_wait * stations_df['n_wait']
        stations_df['contrib_cost'] = self.w_cost * stations_df['n_cost']

        stations_df['total_score'] = (
            stations_df['contrib_poi']
            + stations_df['contrib_dist']
            + stations_df['contrib_wait']
            + stations_df['contrib_cost']
        )

        ranked = stations_df.sort_values(by='total_score', ascending=False)
        if include_llm_context:
            ranked = self.attach_llm_context(ranked)
        return ranked

    @staticmethod
    def explain_score_row(row: pd.Series) -> Dict[str, Any]:
        """Human-readable score breakdown for one ranked station."""
        def fmt_distance(metres: float) -> str:
            if metres >= 1000:
                return f"{metres / 1000:.1f} km"
            return f"{int(metres)} m"

        def fmt_wait(seconds: float) -> str:
            if seconds <= 0:
                return "likely available when you arrive (no queue wait predicted)"
            if seconds < 60:
                return f"about {int(seconds)} s predicted queue wait"
            return f"about {seconds / 60:.1f} min predicted queue wait"

        factors = [
            ("poi", "nearby places (POI)", row.get("poi_sum"), row["n_poi"], row.get("contrib_poi")),
            ("distance", "travel distance", row.get("distance"), row["n_dist"], row.get("contrib_dist")),
            ("wait", "queue wait", row.get("waiting_time"), row["n_wait"], row.get("contrib_wait")),
            ("cost", "charging cost", row.get("cost"), row["n_cost"], row.get("contrib_cost")),
        ]
        breakdown: Dict[str, Any] = {}
        reasons: List[str] = []
        for key, label, raw, normalized, contribution in factors:
            breakdown[key] = {
                "label": label,
                "raw_value": raw,
                "normalized_score": float(normalized),
                "weight": 0.25,
                "contribution_to_total": float(contribution) if contribution is not None else None,
            }
            if float(normalized) >= 0.75:
                reasons.append(f"Strong {label} compared to other options.")

        poi_nearby = row.get("poi_nearby") or []
        if isinstance(poi_nearby, list) and poi_nearby:
            top = poi_nearby[0]
            reasons.insert(
                0,
                f"Nearby: {top.get('name', 'a place')} "
                f"({top.get('distance_metres', '?')} m, rating {top.get('rating', '?')}).",
            )

        return {
            "summary": (
                f"Total score {row['total_score']:.3f} "
                f"(POI {row['n_poi']:.2f}, distance {row['n_dist']:.2f}, "
                f"wait {row['n_wait']:.2f}, cost {row['n_cost']:.2f})."
            ),
            "reasons": reasons[:5],
            "breakdown": breakdown,
            "distance_text": fmt_distance(float(row.get("distance") or 0)),
            "wait_text": fmt_wait(float(row.get("waiting_time") or 0)),
            "cost_text": f"${float(row.get('cost') or 0):.2f} per kWh (median for this station)",
        }

    def build_llm_station_record(
        self,
        row: pd.Series,
        *,
        user_location: Optional[tuple[float, float]] = None,
    ) -> Dict[str, Any]:
        """Structured per-station payload for the LLM."""
        user_loc = user_location or self.user_location
        poi_nearby = row.get("poi_nearby")
        if poi_nearby is None or (isinstance(poi_nearby, float) and pd.isna(poi_nearby)):
            poi_nearby = []

        explanation = row.get("score_explanation")
        if explanation is None or (isinstance(explanation, float) and pd.isna(explanation)):
            explanation = self.explain_score_row(row)

        return {
            "rank": int(row.get("rank", 0)) if pd.notna(row.get("rank")) else None,
            "station_name": row.get("Station Name") or row.get("station_name"),
            "mac_address": row.get("MAC Address") or row.get("mac_address"),
            "plug_type": row.get("Plug Type") or row.get("plug_type"),
            "coordinates": {
                "latitude": float(row["lat"]) if "lat" in row and pd.notna(row["lat"]) else None,
                "longitude": float(row["lon"]) if "lon" in row and pd.notna(row["lon"]) else None,
            },
            "user_location": {
                "latitude": float(user_loc[0]),
                "longitude": float(user_loc[1]),
            },
            "distance_metres": float(row["distance"]) if pd.notna(row.get("distance")) else None,
            "waiting_time_seconds": float(row["waiting_time"]) if pd.notna(row.get("waiting_time")) else None,
            "cost_per_kwh": float(row["cost"]) if pd.notna(row.get("cost")) else None,
            "poi_sum": float(row["poi_sum"]) if pd.notna(row.get("poi_sum")) else None,
            "poi_count": int(row.get("poi_count") or len(poi_nearby)),
            "nearby_pois": poi_nearby,
            "scores": {
                "total_score": float(row["total_score"]),
                "normalized": {
                    "poi": float(row["n_poi"]),
                    "distance": float(row["n_dist"]),
                    "waiting": float(row["n_wait"]),
                    "cost": float(row["n_cost"]),
                },
                "weighted_contributions": {
                    "poi": float(row.get("contrib_poi", 0)),
                    "distance": float(row.get("contrib_dist", 0)),
                    "waiting": float(row.get("contrib_wait", 0)),
                    "cost": float(row.get("contrib_cost", 0)),
                },
            },
            "explanation": explanation,
        }

    def attach_llm_context(self, ranked_df: pd.DataFrame) -> pd.DataFrame:
        """Add ``rank``, ``score_explanation``, and ``llm_context`` columns."""
        out = ranked_df.copy()
        out["rank"] = np.arange(1, len(out) + 1)
        user_loc = (float(self.user_location[0]), float(self.user_location[1]))
        out["score_explanation"] = out.apply(self.explain_score_row, axis=1)
        out["llm_context"] = out.apply(
            lambda row: self.build_llm_station_record(row, user_location=user_loc),
            axis=1,
        )
        return out

    def get_POI(self, latitude, longitude):
    # Returns JSON file of POI around as well as data of it (max 20 top POI)
        POI = Get_POI()
        return POI.call_API(latitude, longitude)

    def get_distance_score(self, destination_location, user_location):
        return get_distance_ev(destination_location, user_location)
    
    def _places_dataframe(self, data: Optional[Dict[str, Any]]) -> pd.DataFrame:
        """Normalize Google Places nearby-search JSON into a scored places table."""
        if not data or "places" not in data:
            return pd.DataFrame()

        place_list = pd.json_normalize(data, record_path=["places"])

        if "routingSummaries" in data:
            place_distance = pd.json_normalize(data["routingSummaries"], record_path=["legs"])
            place = pd.concat([place_list, place_distance], axis=1)
        else:
            place = place_list
            place["distanceMeters"] = 500

        place["rating"] = place["rating"].fillna(0)
        place["userRatingCount"] = place["userRatingCount"].fillna(0)
        place["poi_score"] = place.apply(self.calculate_poi_score, axis=1)
        return place

    @staticmethod
    def _place_display_name(row: pd.Series) -> str:
        display = row.get("displayName")
        if isinstance(display, dict):
            return str(display.get("text") or "Unknown place")
        if display is not None and not (isinstance(display, float) and pd.isna(display)):
            return str(display)
        return "Unknown place"

    def summarize_poi_places(self, data: Optional[Dict[str, Any]], *, top_n: int = 8) -> List[Dict[str, Any]]:
        """Top nearby POIs as compact dicts for LLM / UI consumption."""
        place = self._places_dataframe(data)
        if place.empty:
            return []

        ranked = place.sort_values("poi_score", ascending=False).head(top_n)
        summaries: List[Dict[str, Any]] = []
        for _, row in ranked.iterrows():
            opening = row.get("currentOpeningHours")
            open_now = None
            if isinstance(opening, dict):
                open_now = opening.get("openNow")

            summaries.append(
                {
                    "name": self._place_display_name(row),
                    "rating": float(row["rating"]),
                    "review_count": int(row["userRatingCount"]),
                    "distance_metres": float(row["distanceMeters"]),
                    "address": row.get("formattedAddress"),
                    "poi_score": round(float(row["poi_score"]), 3),
                    "open_now": open_now,
                    "google_maps_uri": row.get("googleMapsUri"),
                }
            )
        return summaries

    def POI_score(self, data, coordinate_key=None):
        place = self._places_dataframe(data)
        if place.empty:
            return 0
        return float(place["poi_score"].sum())
    
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
            raw_json = self.get_POI(row["lat"], row["lon"])
            nearby = self.summarize_poi_places(raw_json)
            poi_sum = sum(p["poi_score"] for p in nearby) if nearby else 0.0
            return pd.Series(
                {
                    "poi_sum": poi_sum,
                    "poi_nearby": nearby,
                    "poi_count": len(nearby),
                }
            )

        # 2. Apply the pipeline to every row
        print("Fetching POI data and calculating scores... this may take a moment.")
        poi_cols = df.apply(row_pipeline, axis=1)
        df = pd.concat([df, poi_cols], axis=1)

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


def load_unit_prices_by_station(
    price_path: Union[str, Path] = UNIT_PRICE_PATH,
) -> pd.DataFrame:
    """
    Load per-station unit prices from ``unit_price_by_station_palo_alto.csv``.

    Returns a DataFrame indexed by ``Station Name`` with
    ``median_unit_price_per_kwh`` and ``price_tier``.
    """
    path = Path(price_path)
    if not path.is_file():
        raise FileNotFoundError(f"Unit price file not found: {path}")

    prices = pd.read_csv(path)
    if "Station Name" not in prices.columns or "median_unit_price_per_kwh" not in prices.columns:
        raise ValueError(
            "Unit price CSV must include 'Station Name' and 'median_unit_price_per_kwh'."
        )

    prices["Station Name"] = prices["Station Name"].astype(str).str.strip()
    prices["median_unit_price_per_kwh"] = pd.to_numeric(
        prices["median_unit_price_per_kwh"], errors="coerce"
    ).fillna(0.0)

    keep = ["Station Name", "median_unit_price_per_kwh"]
    if "price_tier" in prices.columns:
        keep.append("price_tier")

    return prices[keep].drop_duplicates("Station Name", keep="first").set_index("Station Name")


def attach_station_costs(
    stations_df: pd.DataFrame,
    *,
    price_path: Union[str, Path] = UNIT_PRICE_PATH,
    station_name_col: str = "Station Name",
) -> pd.DataFrame:
    """Merge ``cost`` (and optional ``price_tier``) from the unit-price CSV by station name."""
    if station_name_col not in stations_df.columns:
        raise ValueError(f"stations_df missing column: {station_name_col}")

    out = stations_df.copy()
    price_table = load_unit_prices_by_station(price_path)

    out["cost"] = out[station_name_col].astype(str).str.strip().map(
        price_table["median_unit_price_per_kwh"]
    )
    out["median_unit_price_per_kwh"] = out["cost"]

    if "price_tier" in price_table.columns:
        out["price_tier"] = out[station_name_col].astype(str).str.strip().map(price_table["price_tier"])

    # Stations missing from the price file: keep existing cost or default to 0
    if "cost" in stations_df.columns:
        out["cost"] = out["cost"].fillna(stations_df["cost"])
    out["cost"] = out["cost"].fillna(0.0)
    out["median_unit_price_per_kwh"] = out["cost"]

    return out


def build_chargepoint_test_dataset(
    raw_path: Union[str, Path] = RAW_DATA_PATH,
    *,
    sample_size: int = 4,
    at_time: Optional[datetime] = None,
) -> tuple[tuple[float, float], pd.DataFrame]:
    """
    Build a small station-level test set from the raw ChargePoint sessions.

    The raw dataset has session rows, so this function collapses it to unique
    stations, attaches cost from ``unit_price_by_station_palo_alto.csv``, and adds
    the feature columns needed by the wait-time models.
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

    stations = (
        raw.sort_values("Start Date")
        .drop_duplicates("Station Name", keep="last")
        .rename(columns={"Latitude": "lat", "Longitude": "lon"})
    )
    stations = attach_station_costs(stations)
    stations["fee"] = stations["cost"]
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
    current_user_pos, EV_station_dataset = build_chargepoint_test_dataset(sample_size=8)
    print(f"User test location: {current_user_pos}")

    model = Calculation_Model(current_user_pos)

    EV_station_dataset = model.process_distances(EV_station_dataset)
    EV_station_dataset = model.process_all_stations(EV_station_dataset)
    EV_station_dataset = model.process_waiting_times(EV_station_dataset)

    final_ranked_df = model.total_score(EV_station_dataset, include_llm_context=True)
    export_cols = [
        c
        for c in final_ranked_df.columns
        if c not in ("poi_nearby", "score_explanation", "llm_context")
    ]
    final_ranked_df[export_cols].to_csv("final_recommendations_summary.csv", index=False)
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

    print()
    from llm import print_reflection_report, run_reflection_pipeline

    top_context = final_ranked_df.iloc[0]["llm_context"]
    alternatives = final_ranked_df.iloc[1:4]["llm_context"].tolist()
    reflection = run_reflection_pipeline(
        {"recommended": top_context, "alternatives": alternatives}
    )
    print_reflection_report(reflection)






if __name__ == "__main__":
    main()