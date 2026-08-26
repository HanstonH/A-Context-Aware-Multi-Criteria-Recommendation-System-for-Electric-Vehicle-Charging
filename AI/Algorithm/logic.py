'''
EV charging-station recommender (Taiwan / TDX data).

Flow:
1. Given the user's battery percentage and urgency, derive how far they can still
   drive and what the user context is (critical / normal / comfort).
2. Fetch all stations in the city (TDX), keep only stations that are reachable
   AND have at least one connector available right now.
3. Pick the 10 closest candidates (straight-line prefilter to limit API calls).
4. Enrich each candidate with:
   - Road distance  (Google Routes API)
   - POI score      (Google Places API New)
   - Cost           (TDX charging rates)
   - Live connector counts (TDX ConnectorLiveStatus)
5. Rank candidates with the TOPSIS algorithm using exponential context-aware weights
   derived from battery level (survival growth + comfort decay curves).
'''
from __future__ import annotations

import os
import sys
from pathlib import Path
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from dotenv import load_dotenv

from API import TDXClient
from get_Distance_EV import get_distance_ev
from get_POI import Get_POI

load_dotenv()

# TDX ConnectorStatus: 1 = available (idle), 2 = occupied/charging, 3 = fault.
_CONNECTOR_AVAILABLE = 1
# TDX RateType: 1 = free, 2 = per kWh, 3 = per minute, 4 = per hour.
_RATE_FREE = 1
_RATE_PER_KWH = 2

_EARTH_RADIUS_M = 6_371_000.0
_FAILED_DISTANCE_M = 999_999  # penalty when the routing API fails

def load_all_stations_from_snapshot(city: str) -> pd.DataFrame:
    """Return every station for a city from the local snapshot (no ranking).

    Used to plot all pins on the map. Availability is synthesized since the
    snapshot has no live status.
    """
    snapshot_path = (
        Path(__file__).parent.parent.parent
        / "static" / "processed" / "stations_master.parquet"
    )
    df = pd.read_parquet(snapshot_path)
    df = df[df["city"] == city].copy()
    df = df[["StationID", "station_name", "lat", "lon",
             "spaces", "charging_points", "cost"]]
    df = df.dropna(subset=["StationID", "lat", "lon"]).drop_duplicates("StationID")
    df["total_connectors"] = df["charging_points"].fillna(0).astype(int)
    df["available_points"] = (df["total_connectors"] * 0.7).round().astype(int)
    if df["cost"].isna().all():
        df["cost"] = 0.0
    else:
        df["cost"] = df["cost"].fillna(df["cost"].median())
    return df.reset_index(drop=True)


def haversine_metres(lat1: float, lon1: float, lat2, lon2):
    """Straight-line distance in metres. lat2/lon2 may be arrays (vectorized)."""
    lat1, lon1 = np.radians(lat1), np.radians(lon1)
    lat2, lon2 = np.radians(np.asarray(lat2, dtype=float)), np.radians(np.asarray(lon2, dtype=float))
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    return 2 * _EARTH_RADIUS_M * np.arcsin(np.sqrt(a))


# =============================================================================
# Part A: Exponential Context-Aware Weight Engine
# =============================================================================

# Survival growth parameters (distance & available pots increase as battery drops).
_W_BASE_DIST = 0.10
_W_SURVIVAL_AMP_DIST = 0.60
_W_BASE_POTS = 0.15
_W_SURVIVAL_AMP_POTS = 0.30
_K_SURVIVAL = 7.0

# Comfort decay parameters (cost & POI increase as battery rises).
_W_MAX_COST = 0.40
_W_MAX_POI = 0.35
_K_COMFORT = 4.0

# Hardcoded urgency override — already sums to 1.0.
_URGENCY_WEIGHTS = [0.55, 0.05, 0.05, 0.35]  # [w_distance, w_poi, w_cost, w_pots]


@dataclass(frozen=True)
class WeightVector:
    """Criterion weights for TOPSIS; must sum to 1.0.

    Column order matches the TOPSIS decision matrix:
        [distance, poi, cost, pots]
    """
    w_distance: float
    w_poi: float
    w_cost: float
    w_pots: float

    def __post_init__(self):
        total = self.w_distance + self.w_poi + self.w_cost + self.w_pots
        if not np.isclose(total, 1.0, atol=1e-6):
            raise ValueError(f"Weights must sum to 1.0, got {total:.6f}")

    def as_array(self) -> np.ndarray:
        """Return weights as a 1-D numpy array [w_distance, w_poi, w_cost, w_pots]."""
        return np.array([self.w_distance, self.w_poi, self.w_cost, self.w_pots])


def get_exponential_weights(
    battery_percentage: float,
    is_available_now: bool,
) -> List[float]:
    """Compute TOPSIS weight vector via independent exponential growth/decay curves.

    Parameters
    ----------
    battery_percentage:
        Remaining battery as a fraction in [0.0, 1.0] (clamped if out of range).
    is_available_now:
        When True, bypass exponential math and return the hardcoded urgency vector.

    Returns
    -------
    list[float]
        Strictly normalised ``[w_distance, w_poi, w_cost, w_pots]`` summing to 1.0.

    Formulas (B = clamped battery fraction)
    ---------------------------------------
    w_dist_raw  = W_base_dist  + A      * exp(-k_survival * B)
    w_pots_raw  = W_base_pots  + B_amp  * exp(-k_survival * B)
    w_cost_raw  = W_max_cost   * (1 - exp(-k_comfort * B))
    w_poi_raw   = W_max_poi    * (1 - exp(-k_comfort * B))
    """
    if is_available_now:
        return list(_URGENCY_WEIGHTS)

    B = float(np.clip(battery_percentage, 0.0, 1.0))

    survival_decay = np.exp(-_K_SURVIVAL * B)
    comfort_growth = 1.0 - np.exp(-_K_COMFORT * B)

    w_dist_raw = _W_BASE_DIST + _W_SURVIVAL_AMP_DIST * survival_decay
    w_pots_raw = _W_BASE_POTS + _W_SURVIVAL_AMP_POTS * survival_decay
    w_cost_raw = _W_MAX_COST * comfort_growth
    w_poi_raw  = _W_MAX_POI  * comfort_growth

    raw = np.array([w_dist_raw, w_poi_raw, w_cost_raw, w_pots_raw], dtype=float)
    total = raw.sum()
    if total <= 0.0:
        raise ValueError("Exponential weight raw sum is zero; cannot normalise.")
    return (raw / total).tolist()


def get_dynamic_weights(battery_percentage: float, is_available_now: bool) -> WeightVector:
    """Return context-aware weights as a ``WeightVector`` for TOPSIS.

    Delegates to ``get_exponential_weights`` and wraps the result.
    """
    w_dist, w_poi, w_cost, w_pots = get_exponential_weights(
        battery_percentage, is_available_now
    )
    return WeightVector(w_distance=w_dist, w_poi=w_poi, w_cost=w_cost, w_pots=w_pots)


# TOPSIS column order: [distance, poi, cost, pots]
# True  = cost criterion (lower is better) → PIS = min, NIS = max
# False = benefit criterion (higher is better) → PIS = max, NIS = min
_IS_COST_CRITERION = np.array([True, False, True, False])

# Distance added to stations with zero available pots when the user is urgent,
# making them sort last without hard-removing them (edge case: all stations full).
_OCCUPIED_PENALTY = 1e9


# =============================================================================
# Part B: Pure Vectorized TOPSIS Algorithm
# =============================================================================

def topsis_rank(
    stations: List[Dict[str, Any]],
    battery_percentage: float,
    is_available_now: bool,
) -> List[Dict[str, Any]]:
    """Rank EV station candidates using TOPSIS with context-aware weights.

    Parameters
    ----------
    stations:
        Up to 10 station dicts, each with:
          ``id``             – string identifier
          ``distance``       – metres from user (minimise)
          ``poi_count``      – nearby POI count (maximise)
          ``cost``           – charging fee per kWh (minimise)
          ``available_pots`` – idle connector count right now (maximise)
    battery_percentage:
        Remaining battery as a fraction [0.0, 1.0].
    is_available_now:
        True when the user cannot wait and needs an immediate slot.

    Returns
    -------
    The input list sorted best-first, each dict extended with ``topsis_score``
    (the TOPSIS closeness coefficient C_i ∈ [0, 1]).
    """
    if not stations:
        return []

    weights = get_dynamic_weights(battery_percentage, is_available_now)
    w = weights.as_array()  # shape (4,)

    # ------------------------------------------------------------------
    # Pre-filtering guardrail: add a massive distance penalty to any station
    # with zero available pots when the user is urgent, ensuring they rank
    # last.  We penalise rather than drop so the user always gets N results.
    # ------------------------------------------------------------------
    working: List[Dict[str, Any]] = [dict(s) for s in stations]
    if is_available_now:
        for s in working:
            if s.get("available_pots", 0) == 0:
                s["distance"] = float(s.get("distance", 0)) + _OCCUPIED_PENALTY

    # ------------------------------------------------------------------
    # Step 1 — Decision matrix X  (n × 4)
    # Column order: [distance, poi_count, cost, available_pots]
    # ------------------------------------------------------------------
    X = np.array(
        [
            [
                float(s.get("distance", 0)),
                float(s.get("poi_count", 0)),
                float(s.get("cost", 0)),
                float(s.get("available_pots", 0)),
            ]
            for s in working
        ],
        dtype=float,
    )  # (n, 4)

    # ------------------------------------------------------------------
    # Step 2 — Vector normalisation:  r_ij = x_ij / ||x_j||
    # Guard against all-zero columns (constant criterion).
    # ------------------------------------------------------------------
    col_norms = np.sqrt((X ** 2).sum(axis=0))          # (4,)
    col_norms = np.where(col_norms == 0.0, 1.0, col_norms)
    R = X / col_norms                                   # (n, 4)

    # ------------------------------------------------------------------
    # Step 3 — Weighted normalised matrix  V = R ⊙ w
    # ------------------------------------------------------------------
    V = R * w                                           # (n, 4)

    # ------------------------------------------------------------------
    # Step 4 — Ideal (PIS / A+) and Anti-Ideal (NIS / A-) solutions
    # Cost criteria  [distance, cost]:  PIS = col_min,  NIS = col_max
    # Benefit criteria [poi, pots]:     PIS = col_max,  NIS = col_min
    # ------------------------------------------------------------------
    PIS = np.where(_IS_COST_CRITERION, V.min(axis=0), V.max(axis=0))  # (4,)
    NIS = np.where(_IS_COST_CRITERION, V.max(axis=0), V.min(axis=0))  # (4,)

    # ------------------------------------------------------------------
    # Step 5 — Euclidean distances to PIS and NIS for each station
    # ------------------------------------------------------------------
    S_pos = np.sqrt(((V - PIS) ** 2).sum(axis=1))      # (n,)
    S_neg = np.sqrt(((V - NIS) ** 2).sum(axis=1))      # (n,)

    # ------------------------------------------------------------------
    # Step 6 — Closeness coefficient  C_i = S_neg / (S_pos + S_neg)
    # When all stations are identical the denominator is 0; return 0.5 uniformly.
    # ------------------------------------------------------------------
    denom = S_pos + S_neg
    with np.errstate(invalid="ignore", divide="ignore"):
        C = np.where(denom == 0.0, 0.5, S_neg / denom)   # (n,)

    # ------------------------------------------------------------------
    # Step 7 — Attach score to original dicts (not penalised copies) and sort.
    # ------------------------------------------------------------------
    scored = [
        {**original, "topsis_score": float(round(score, 6))}
        for original, score in zip(stations, C)
    ]
    scored.sort(key=lambda s: s["topsis_score"], reverse=True)
    return scored


# =============================================================================
# Calculation_Model — full TDX pipeline
# =============================================================================

class Calculation_Model:
    """Scores candidate EV stations using TOPSIS with context-aware weights."""

    def __init__(
        self,
        user_location: Tuple[float, float],
        battery_percent: float,
        *,
        is_available_now: bool = False,
        city: str = "Taipei",
        full_range_km: float = 300.0,
        range_safety_factor: float = 0.8,
        max_candidates: int = 10,
        tdx_client: Optional[TDXClient] = None,
        use_snapshot: bool = False,
    ):
        self.user_location = (float(user_location[0]), float(user_location[1]))
        # Stored as 0-100 for human readability; converted to 0-1 when calling
        # the weight engine.
        self.battery_percent = float(battery_percent)
        self.is_available_now = is_available_now
        self.city = city
        self.full_range_km = full_range_km
        self.range_safety_factor = range_safety_factor
        self.max_candidates = max_candidates
        self.use_snapshot = use_snapshot

        self._tdx = tdx_client or TDXClient(
            os.getenv("TDX_CLIENT_ID"),
            os.getenv("TDX_CLIENT_SECRET"),
        )

    # ------------------------------------------------------------------
    # Convenience properties
    # ------------------------------------------------------------------
    @property
    def battery_fraction(self) -> float:
        """Battery level in [0.0, 1.0] for use with the weight engine."""
        return max(self.battery_percent, 0.0) / 100.0

    @property
    def weights(self) -> WeightVector:
        """Current context-aware weight vector."""
        return get_dynamic_weights(self.battery_fraction, self.is_available_now)

    @property
    def reachable_metres(self) -> float:
        """Estimated remaining driving range in metres."""
        return self.battery_fraction * self.full_range_km * 1000.0 * self.range_safety_factor

    # ------------------------------------------------------------------
    # Step 1-2: fetch TDX data and build the station table
    # ------------------------------------------------------------------
    def build_station_dataframe(self) -> pd.DataFrame:
        """Fetch stations + live status + charging rates and merge into one table."""
        stations = self._tdx.get_ev_stations(self.city)
        live = self._tdx.get_ev_connector_live_status(self.city)
        rates = self._tdx.get_ev_charging_rate(self.city)

        df = pd.DataFrame(
            {
                "StationID": s.get("StationID"),
                "station_name": (s.get("StationName") or {}).get("Zh_tw"),
                "lat": s.get("PositionLat"),
                "lon": s.get("PositionLon"),
                "spaces": s.get("Spaces"),
                "charging_points": s.get("ChargingPoints"),
            }
            for s in stations
        )
        df = df.dropna(subset=["StationID", "lat", "lon"]).drop_duplicates("StationID")
        df = self._attach_availability(df, live)
        df = self._attach_costs(df, rates)
        return df.reset_index(drop=True)

    
    def build_station_dataframe_from_snapshot(self) -> pd.DataFrame:
        """Load stations from the local static snapshot instead of live TDX.

        Offline/demo mode. Availability is synthesized because the snapshot
        has no live ConnectorLiveStatus data.
        """
        snapshot_path = (
            Path(__file__).parent.parent.parent
            / "static" / "processed" / "stations_master.parquet"
        )
        df = pd.read_parquet(snapshot_path)
        df = df[df["city"] == self.city].copy()
        df = df[["StationID", "station_name", "lat", "lon",
                 "spaces", "charging_points", "cost"]]
        df = df.dropna(subset=["StationID", "lat", "lon"]).drop_duplicates("StationID")

        df["total_connectors"] = df["charging_points"].fillna(0).astype(int)
        df["available_points"] = (df["total_connectors"] * 0.7).round().astype(int)

        if df["cost"].isna().all():
            df["cost"] = 0.0
        else:
            df["cost"] = df["cost"].fillna(df["cost"].median())
        return df.reset_index(drop=True)

    @staticmethod
    def _attach_availability(df: pd.DataFrame, live_statuses: List[Dict[str, Any]]) -> pd.DataFrame:
        if live_statuses:
            live = pd.DataFrame(live_statuses)
            grouped = live.groupby("StationID")["ConnectorStatus"].agg(
                available_points=lambda s: int((s == _CONNECTOR_AVAILABLE).sum()),
                total_connectors="size",
            )
            df = df.merge(grouped, on="StationID", how="left")
        else:
            df["available_points"] = np.nan
            df["total_connectors"] = np.nan

        df["available_points"] = df["available_points"].fillna(0).astype(int)
        df["total_connectors"] = df["total_connectors"].fillna(0).astype(int)
        return df

    @staticmethod
    def _station_cost_from_rates(rate_records: List[Dict[str, Any]]) -> pd.DataFrame:
        """Collapse TDX rate records to a single median price per station.

        Prefers per-kWh rates (RateType 2); free stations count as 0.
        """
        rows = []
        for record in rate_records:
            station_id = record.get("StationID")
            for rate in record.get("Rates") or []:
                rate_type = rate.get("RateType")
                price = rate.get("RatePrice")
                if rate_type == _RATE_FREE:
                    rows.append((station_id, 0.0, True))
                elif price is not None:
                    rows.append((station_id, float(price), rate_type == _RATE_PER_KWH))

        if not rows:
            return pd.DataFrame(columns=["StationID", "cost"])

        rates_df = pd.DataFrame(rows, columns=["StationID", "price", "preferred"])
        preferred = rates_df[rates_df["preferred"]].groupby("StationID")["price"].median()
        fallback = rates_df.groupby("StationID")["price"].median()
        return preferred.combine_first(fallback).rename("cost").reset_index()

    def _attach_costs(self, df: pd.DataFrame, rate_records: List[Dict[str, Any]]) -> pd.DataFrame:
        cost_table = self._station_cost_from_rates(rate_records)
        df = df.merge(cost_table, on="StationID", how="left")
        median_cost = df["cost"].median()
        df["cost"] = df["cost"].fillna(0.0 if pd.isna(median_cost) else median_cost)
        return df

    # ------------------------------------------------------------------
    # Step 3: vicinity search → candidate selection
    # ------------------------------------------------------------------
    def select_candidates(self, stations_df: pd.DataFrame) -> pd.DataFrame:
        """Return up to max_candidates reachable + available stations."""
        df = stations_df.copy()
        df["straight_line_m"] = haversine_metres(
            self.user_location[0], self.user_location[1], df["lat"], df["lon"]
        )

        reachable = df["straight_line_m"] <= self.reachable_metres
        available = df["available_points"] >= 1
        candidates = df[reachable & available]

        if candidates.empty:
            candidates = df[reachable]  # fallback: all reachable even if busy
        if candidates.empty:
            raise ValueError(
                f"No station reachable within {self.reachable_metres / 1000:.1f} km "
                f"(battery {self.battery_percent:.0f}%)."
            )

        return (
            candidates.sort_values("straight_line_m")
            .head(self.max_candidates)
            .reset_index(drop=True)
        )

    # ------------------------------------------------------------------
    # Step 4a: road distance (Google Routes)
    # ------------------------------------------------------------------
    def process_distances(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add a road ``distance`` (metres) column for every candidate."""
        def get_row_dist(row):
            dest = (row["lat"], row["lon"])
            result = get_distance_ev(dest, self.user_location)
            if result and result.get("routes"):
                route = result["routes"][0]
                distance = route.get("distanceMeters")
                if distance is not None:
                    return distance
                # Degenerate ~0 s trip: Routes API omits distanceMeters.
                if "straight_line_m" in row and pd.notna(row["straight_line_m"]):
                    return float(row["straight_line_m"])
            return _FAILED_DISTANCE_M

        df = df.copy()
        df["distance"] = df.apply(get_row_dist, axis=1)
        return df

    # ------------------------------------------------------------------
    # Step 4b: POI around each station (Google Places)
    # ------------------------------------------------------------------
    def get_POI(self, latitude, longitude):
        """Raw nearby-POI JSON for one coordinate (max 20 places)."""
        return Get_POI().call_API(latitude, longitude)

    @staticmethod
    def calculate_poi_score(row):
        rating = row["rating"]
        reviews = row["userRatingCount"]
        distance = row["distanceMeters"]
        return (rating * np.log10(reviews + 1)) / (1 + distance / 100)

    def _places_dataframe(self, data: Optional[Dict[str, Any]]) -> pd.DataFrame:
        if not data or "places" not in data:
            return pd.DataFrame()

        place_list = pd.json_normalize(data, record_path=["places"])

        if "routingSummaries" in data:
            place_distance = pd.json_normalize(data["routingSummaries"], record_path=["legs"])
            place = pd.concat([place_list, place_distance], axis=1)
        else:
            place = place_list
            place["distanceMeters"] = 500

        place["rating"] = place.get("rating", pd.Series(dtype=float)).fillna(0)
        place["userRatingCount"] = place.get("userRatingCount", pd.Series(dtype=float)).fillna(0)
        place["poi_score"] = place.apply(self.calculate_poi_score, axis=1)
        return place

    def POI_score(self, data) -> float:
        place = self._places_dataframe(data)
        return 0.0 if place.empty else float(place["poi_score"].sum())

    def process_all_stations(self, df: pd.DataFrame) -> pd.DataFrame:
        """Fetch POI data and add ``poi_sum`` / ``poi_count`` per station."""
        def row_pipeline(row):
            raw_json = self.get_POI(row["lat"], row["lon"])
            place = self._places_dataframe(raw_json)
            return pd.Series(
                {
                    "poi_sum": self.POI_score(raw_json),
                    "poi_count": len(place),
                }
            )

        print("Fetching POI data and calculating scores... this may take a moment.")
        poi_cols = df.apply(row_pipeline, axis=1)
        return pd.concat([df, poi_cols], axis=1)

    # ------------------------------------------------------------------
    # Step 5a: weighted-sum score (auxiliary breakdown columns)
    # ------------------------------------------------------------------
    @staticmethod
    def _normalize_higher_is_better(series: pd.Series) -> pd.Series:
        values = pd.to_numeric(series, errors="coerce")
        min_value = values.min()
        max_value = values.max()
        if pd.isna(max_value) or max_value <= 0:
            return pd.Series(0.0, index=series.index)
        if max_value == min_value:
            # No spread across candidates — neutral score, not "best for everyone".
            return pd.Series(0.5, index=series.index)
        return values.fillna(0.0) / max_value

    @staticmethod
    def _normalize_lower_is_better(series: pd.Series) -> pd.Series:
        values = pd.to_numeric(series, errors="coerce")
        lo, hi = values.min(), values.max()
        if pd.isna(lo) or pd.isna(hi):
            return pd.Series(0.0, index=series.index)
        if hi == lo:
            return pd.Series(1.0, index=series.index)
        return ((hi - values) / (hi - lo)).fillna(0.0)

    def total_score(self, stations_df: pd.DataFrame) -> pd.DataFrame:
        """Add normalised columns and weighted-sum ``total_score``.

        Uses the current dynamic weights — not hardcoded 0.25.
        """
        stations_df = stations_df.copy()
        required = ["poi_sum", "distance", "cost", "available_points"]
        missing = [c for c in required if c not in stations_df.columns]
        if missing:
            raise ValueError(f"total_score() missing required columns: {missing}")

        w = self.weights
        stations_df["n_poi"]   = self._normalize_higher_is_better(stations_df["poi_sum"])
        stations_df["n_avail"] = self._normalize_higher_is_better(stations_df["available_points"])
        stations_df["n_dist"]  = self._normalize_lower_is_better(stations_df["distance"])
        stations_df["n_cost"]  = self._normalize_lower_is_better(stations_df["cost"])

        stations_df["contrib_poi"]   = w.w_poi      * stations_df["n_poi"]
        stations_df["contrib_dist"]  = w.w_distance * stations_df["n_dist"]
        stations_df["contrib_cost"]  = w.w_cost     * stations_df["n_cost"]
        stations_df["contrib_avail"] = w.w_pots     * stations_df["n_avail"]

        stations_df["total_score"] = (
            stations_df["contrib_poi"]
            + stations_df["contrib_dist"]
            + stations_df["contrib_cost"]
            + stations_df["contrib_avail"]
        )

        return stations_df

    # ------------------------------------------------------------------
    # Step 5b: TOPSIS ranking — primary sort key
    # ------------------------------------------------------------------
    def apply_topsis(self, candidates_df: pd.DataFrame) -> pd.DataFrame:
        """Convert the enriched candidates DataFrame, run TOPSIS, and merge
        ``topsis_score`` back as the primary ranking column."""
        station_dicts = [
            {
                "id":             row.get("StationID", str(i)),
                "distance":       float(row.get("distance", _FAILED_DISTANCE_M)),
                "poi_count":      float(row.get("poi_count", 0)),
                "cost":           float(row.get("cost", 0)),
                "available_pots": float(row.get("available_points", 0)),
            }
            for i, (_, row) in enumerate(candidates_df.iterrows())
        ]

        ranked_dicts = topsis_rank(station_dicts, self.battery_fraction, self.is_available_now)

        # Map topsis_score back to the DataFrame by station id.
        score_map = {s["id"]: s["topsis_score"] for s in ranked_dicts}
        df = candidates_df.copy()
        df["topsis_score"] = df.apply(
            lambda row: score_map.get(str(row.get("StationID", "")), 0.0), axis=1
        )
        return df

    # ------------------------------------------------------------------
    # Full pipeline
    # ------------------------------------------------------------------
    def recommend(self) -> pd.DataFrame:
        """Run the complete recommendation pipeline.

        Returns a DataFrame ranked best-first by ``topsis_score``.
        Also includes ``total_score`` and normalised / contribution columns.
        """
        context = self.weights
        state = _context_state_label(self.battery_fraction, self.is_available_now)
        print(
            f"[{self.city}] battery {self.battery_percent:.0f}% → "
            f"{self.reachable_metres / 1000:.1f} km range | "
            f"state={state} | weights dist={context.w_distance} poi={context.w_poi} "
            f"cost={context.w_cost} pots={context.w_pots}"
        )

        all_stations = (
            self.build_station_dataframe_from_snapshot()
            if self.use_snapshot
            else self.build_station_dataframe()
        )

        print(f"  {len(all_stations)} stations fetched from TDX.")

        candidates = self.select_candidates(all_stations)
        print(f"  {len(candidates)} candidates selected (reachable + available).")

        candidates = self.process_distances(candidates)
        candidates = self.process_all_stations(candidates)

        candidates = self.total_score(candidates)

        # TOPSIS score — primary sort key.
        candidates = self.apply_topsis(candidates)

        return candidates.sort_values("topsis_score", ascending=False).reset_index(drop=True)


# =============================================================================
# Terminal reporting
# =============================================================================

def _format_distance(metres: float) -> str:
    if metres >= 1000:
        return f"{metres / 1000:.2f} km"
    return f"{int(round(metres))} m"


def _context_state_label(battery_fraction: float, is_available_now: bool) -> str:
    if is_available_now:
        return "URGENT"
    if battery_fraction < 0.20:
        return "LOW BATTERY"
    if battery_fraction < 0.50:
        return "MID BATTERY"
    return "HIGH BATTERY"


def print_recommendation_report(
    ranked_df: pd.DataFrame,
    *,
    city: str,
    battery_percent: float,
    is_available_now: bool,
    weights: WeightVector,
    reachable_km: float,
) -> None:
    """Pretty-print the ranked recommendation table to the terminal."""
    try:
        from rich import box
        from rich.console import Console
        from rich.panel import Panel
        from rich.table import Table
        from rich.text import Text

        console = Console()
        state = _context_state_label(battery_percent / 100.0, is_available_now)

        header = Text.assemble(
            ("City: ", "dim"), (city, "bold cyan"), "  |  ",
            ("Battery: ", "dim"), (f"{battery_percent:.0f}%", "bold yellow"), "  |  ",
            ("State: ", "dim"), (state, "bold magenta"), "  |  ",
            ("Range: ", "dim"), (f"{reachable_km:.1f} km", "bold green"),
        )
        weights_line = (
            f"Weights  dist={weights.w_distance:.2f}  "
            f"poi={weights.w_poi:.2f}  "
            f"cost={weights.w_cost:.2f}  "
            f"pots={weights.w_pots:.2f}"
        )
        console.print(Panel(header, subtitle=weights_line, border_style="blue"))

        table = Table(
            box=box.ROUNDED,
            show_header=True,
            header_style="bold white on dark_blue",
            row_styles=["", "dim"],
            expand=True,
            title="Ranked EV Charging Stations",
            title_style="bold",
        )
        table.add_column("#", justify="right", style="cyan", width=4)
        table.add_column("Station", style="bold", min_width=24, max_width=32, overflow="ellipsis")
        table.add_column("Distance", justify="right", style="green")
        table.add_column("POI", justify="right", style="magenta")
        table.add_column("Cost", justify="right", style="yellow")
        table.add_column("Avail", justify="center", style="blue")
        table.add_column("TOPSIS", justify="right", style="bold")
        table.add_column("Score", justify="right", style="dim")

        for rank, (_, row) in enumerate(ranked_df.iterrows(), start=1):
            name = str(row.get("station_name") or row.get("StationID") or "—")
            if len(name) > 32:
                name = name[:29] + "..."
            avail = f"{int(row.get('available_points') or 0)}/{int(row.get('total_connectors') or 0)}"
            topsis = float(row.get("topsis_score") or 0)
            total = float(row.get("total_score") or 0)

            rank_cell = f"#{rank}"
            if rank == 1:
                rank_cell = "[bold gold1]★ #1[/]"
                name = f"[bold gold1]{name}[/]"
            elif rank == 2:
                rank_cell = "[bold] #2[/]"
            elif rank == 3:
                rank_cell = "[bold] #3[/]"

            table.add_row(
                rank_cell,
                name,
                _format_distance(float(row.get("distance") or 0)),
                str(int(row.get("poi_count") or 0)),
                f"NT${float(row.get('cost') or 0):.2f}",
                avail,
                f"{topsis:.4f}",
                f"{total:.3f}",
            )

        console.print(table)

        if not ranked_df.empty:
            best = ranked_df.iloc[0]
            console.print(
                Panel(
                    Text.assemble(
                        ("Recommended: ", "bold"),
                        (str(best.get("station_name") or "—"), "bold green"),
                        "\n",
                        ("TOPSIS ", "dim"),
                        (f"{float(best.get('topsis_score') or 0):.4f}", "bold cyan"),
                        ("  ·  ", "dim"),
                        ("Distance ", "dim"),
                        (_format_distance(float(best.get("distance") or 0)), "bold"),
                        ("  ·  ", "dim"),
                        ("Available ", "dim"),
                        (f"{int(best.get('available_points') or 0)} plug(s)", "bold"),
                    ),
                    title="Best Pick",
                    border_style="green",
                )
            )
        return

    except ImportError:
        pass

    # Stdlib fallback when rich is not installed.
    state = _context_state_label(battery_percent / 100.0, is_available_now)
    width = 88
    print()
    print("=" * width)
    print("  EV CHARGING STATION RECOMMENDATIONS".center(width))
    print("=" * width)
    print(
        f"  City: {city}  |  Battery: {battery_percent:.0f}%  |  "
        f"State: {state}  |  Range: {reachable_km:.1f} km"
    )
    print(
        f"  Weights  dist={weights.w_distance:.2f}  poi={weights.w_poi:.2f}  "
        f"cost={weights.w_cost:.2f}  pots={weights.w_pots:.2f}"
    )
    print("-" * width)
    print(
        f"{'#':>3}  {'Station':<28} {'Distance':>10} {'POI':>4} "
        f"{'Cost':>8} {'Avail':>7} {'TOPSIS':>8} {'Score':>7}"
    )
    print("-" * width)

    for rank, (_, row) in enumerate(ranked_df.iterrows(), start=1):
        name = str(row.get("station_name") or row.get("StationID") or "—")
        if len(name) > 28:
            name = name[:25] + "..."
        marker = "★" if rank == 1 else " "
        avail = f"{int(row.get('available_points') or 0)}/{int(row.get('total_connectors') or 0)}"
        print(
            f"{marker}{rank:>2}  {name:<28} "
            f"{_format_distance(float(row.get('distance') or 0)):>10} "
            f"{int(row.get('poi_count') or 0):>4} "
            f"{'NT$' + format(float(row.get('cost') or 0), '.2f'):>8} "
            f"{avail:>7} "
            f"{float(row.get('topsis_score') or 0):>8.4f} "
            f"{float(row.get('total_score') or 0):>7.3f}"
        )

    print("=" * width)
    if not ranked_df.empty:
        best = ranked_df.iloc[0]
        print(
            f"  Best pick: {best.get('station_name')}  "
            f"(TOPSIS {float(best.get('topsis_score') or 0):.4f})"
        )
    print()


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    # # --- Quick TOPSIS self-test (no API calls) --------------------------------
    # sample_stations = [
    #     {"id": "A", "distance": 500,  "poi_count": 8,  "cost": 9.0,  "available_pots": 2},
    #     {"id": "B", "distance": 1200, "poi_count": 15, "cost": 7.5,  "available_pots": 5},
    #     {"id": "C", "distance": 300,  "poi_count": 2,  "cost": 10.0, "available_pots": 0},
    #     {"id": "D", "distance": 800,  "poi_count": 10, "cost": 8.0,  "available_pots": 3},
    # ]
    # print("=== TOPSIS self-test (critical state, urgent) ===")
    # for s in topsis_rank(sample_stations, battery_percentage=0.15, is_available_now=True):
    #     print(f"  {s['id']}  topsis_score={s['topsis_score']:.4f}  pots={s['available_pots']}")

    # print("\n=== TOPSIS self-test (comfort state) ===")
    # for s in topsis_rank(sample_stations, battery_percentage=0.80, is_available_now=False):
    #     print(f"  {s['id']}  topsis_score={s['topsis_score']:.4f}  poi={s['poi_count']}  cost={s['cost']}")

    # --- Full live pipeline ---------------------------------------------------
    print("\n=== Full pipeline (Taipei, 35% battery) ===")
    current_user_pos = (25.0478, 121.5170)
    battery_percent = 35.0

    model = Calculation_Model(
        current_user_pos,
        battery_percent,
        is_available_now=False,
        city="Taipei",
    )
    final_ranked_df = model.recommend()
    final_ranked_df.to_csv("final_recommendations_summary.csv", index=False)

    print_recommendation_report(
        final_ranked_df,
        city=model.city,
        battery_percent=model.battery_percent,
        is_available_now=model.is_available_now,
        weights=model.weights,
        reachable_km=model.reachable_metres / 1000.0,
    )


if __name__ == "__main__":
    main()
