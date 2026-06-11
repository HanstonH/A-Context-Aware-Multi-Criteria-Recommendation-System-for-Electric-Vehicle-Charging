'''
EV charging-station recommender (Taiwan / TDX data).

Flow:
1. Given the user's battery percentage, work out how far they can still drive.
2. Fetch all stations in the city (TDX), keep only stations that are reachable
   AND have at least one connector available right now.
3. Pick the 10 closest candidates (straight-line prefilter to limit API calls).
4. Score each candidate on:
   1. Distance from user to station (road distance, Google Routes)
   2. POI around the station (Google Places)
   3. Cost of the station (TDX charging rates)
   4. How many charging connectors are usable right now (TDX live status)
5. Highest total score wins. Equal weights for now (will be tuned later).
'''
from __future__ import annotations

import os
import sys
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


def haversine_metres(lat1: float, lon1: float, lat2, lon2):
    """Straight-line distance in metres. lat2/lon2 may be arrays (vectorized)."""
    lat1, lon1 = np.radians(lat1), np.radians(lon1)
    lat2, lon2 = np.radians(np.asarray(lat2, dtype=float)), np.radians(np.asarray(lon2, dtype=float))
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    return 2 * _EARTH_RADIUS_M * np.arcsin(np.sqrt(a))


class Calculation_Model:
    """Scores candidate EV stations and picks the best one."""

    def __init__(
        self,
        user_location: Tuple[float, float],
        battery_percent: float,
        *,
        city: str = "Taipei",
        full_range_km: float = 300.0,
        range_safety_factor: float = 0.8,
        max_candidates: int = 10,
        tdx_client: Optional[TDXClient] = None,
    ):
        # Equal weights for now; will be tuned later.
        self.w_dist = 0.25
        self.w_poi = 0.25
        self.w_cost = 0.25
        self.w_avail = 0.25

        self.user_location = (float(user_location[0]), float(user_location[1]))
        self.battery_percent = float(battery_percent)
        self.city = city
        self.full_range_km = full_range_km
        self.range_safety_factor = range_safety_factor
        self.max_candidates = max_candidates

        # Prefer .env credentials; fall back to the demo key used in API.py.
        self._tdx = tdx_client or TDXClient(
            os.getenv("TDX_CLIENT_ID"),
            os.getenv("TDX_CLIENT_SECRET"),
        )

    # ------------------------------------------------------------------
    # Step 1-2: fetch TDX data and build the station table
    # ------------------------------------------------------------------
    @property
    def reachable_metres(self) -> float:
        """How far the user can still drive on the current battery."""
        fraction = max(self.battery_percent, 0.0) / 100.0
        return fraction * self.full_range_km * 1000.0 * self.range_safety_factor

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

    @staticmethod
    def _attach_availability(df: pd.DataFrame, live_statuses: List[Dict[str, Any]]) -> pd.DataFrame:
        """Add per-station connector counts from the live status feed."""
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

        # Stations without live data: assume nothing is available (can't verify).
        df["available_points"] = df["available_points"].fillna(0).astype(int)
        df["total_connectors"] = df["total_connectors"].fillna(0).astype(int)
        return df

    @staticmethod
    def _station_cost_from_rates(rate_records: List[Dict[str, Any]]) -> pd.DataFrame:
        """Collapse TDX charging-rate records to one price per station.

        Prefers per-kWh rates (RateType 2); free stations count as 0.
        Returns a DataFrame with ``StationID`` and ``cost``.
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
        # Use per-kWh (or free) prices when a station has them, else any price.
        preferred = rates_df[rates_df["preferred"]].groupby("StationID")["price"].median()
        fallback = rates_df.groupby("StationID")["price"].median()
        cost = preferred.combine_first(fallback).rename("cost").reset_index()
        return cost

    def _attach_costs(self, df: pd.DataFrame, rate_records: List[Dict[str, Any]]) -> pd.DataFrame:
        cost_table = self._station_cost_from_rates(rate_records)
        df = df.merge(cost_table, on="StationID", how="left")
        # Stations without published rates: assume the city's median price.
        median_cost = df["cost"].median()
        df["cost"] = df["cost"].fillna(0.0 if pd.isna(median_cost) else median_cost)
        return df

    # ------------------------------------------------------------------
    # Step 3: vicinity search -> candidate selection
    # ------------------------------------------------------------------
    def select_candidates(self, stations_df: pd.DataFrame) -> pd.DataFrame:
        """Reachable + available-now stations, the N closest by straight line."""
        df = stations_df.copy()
        df["straight_line_m"] = haversine_metres(
            self.user_location[0], self.user_location[1], df["lat"], df["lon"]
        )

        reachable = df["straight_line_m"] <= self.reachable_metres
        available = df["available_points"] >= 1
        candidates = df[reachable & available]

        if candidates.empty:
            # Battery too low / everything busy: fall back to reachable stations
            # so the user still gets a ranked answer instead of nothing.
            candidates = df[reachable]
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
                # Routes API sometimes omits distanceMeters on ~0 s trips
                # (e.g. underground parking 30–50 m from origin).
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
        # +1 review to avoid log(0)
        return (rating * np.log10(reviews + 1)) / (1 + distance / 100)

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

        place["rating"] = place.get("rating", pd.Series(dtype=float)).fillna(0)
        place["userRatingCount"] = place.get("userRatingCount", pd.Series(dtype=float)).fillna(0)
        place["poi_score"] = place.apply(self.calculate_poi_score, axis=1)
        return place

    @staticmethod
    def _place_display_name(row: pd.Series) -> str:
        display = row.get("displayName")
        if isinstance(display, dict):
            return str(display.get("text") or "Unknown place")
        text = row.get("displayName.text")
        if isinstance(text, str) and text:
            return text
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
            open_now = opening.get("openNow") if isinstance(opening, dict) else None
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

    def POI_score(self, data) -> float:
        place = self._places_dataframe(data)
        if place.empty:
            return 0.0
        return float(place["poi_score"].sum())

    def process_all_stations(self, df: pd.DataFrame) -> pd.DataFrame:
        """Fetch POI data and add ``poi_sum`` / ``poi_nearby`` / ``poi_count`` per station."""
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

        print("Fetching POI data and calculating scores... this may take a moment.")
        poi_cols = df.apply(row_pipeline, axis=1)
        return pd.concat([df, poi_cols], axis=1)

    # ------------------------------------------------------------------
    # Step 5: scoring
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
        min_value = values.min()
        max_value = values.max()
        if pd.isna(min_value) or pd.isna(max_value):
            return pd.Series(0.0, index=series.index)
        if max_value == min_value:
            # Identical values (e.g. all free, all zero wait) must not score as "best".
            return pd.Series(0.5, index=series.index)
        return ((max_value - values) / (max_value - min_value)).fillna(0.0)

    def total_score(self, stations_df: pd.DataFrame, *, include_llm_context: bool = False) -> pd.DataFrame:
        """
        Weighted-sum score over ['distance', 'poi_sum', 'cost', 'available_points'].
        Lower distance/cost are better; higher POI/availability are better.
        Returns the DataFrame ranked best-first.
        """
        stations_df = stations_df.copy()

        required = ["poi_sum", "distance", "cost", "available_points"]
        missing = [c for c in required if c not in stations_df.columns]
        if missing:
            raise ValueError(f"total_score() missing required columns: {missing}")

        stations_df["n_poi"] = self._normalize_higher_is_better(stations_df["poi_sum"])
        stations_df["n_avail"] = self._normalize_higher_is_better(stations_df["available_points"])
        stations_df["n_dist"] = self._normalize_lower_is_better(stations_df["distance"])
        stations_df["n_cost"] = self._normalize_lower_is_better(stations_df["cost"])

        stations_df["contrib_poi"] = self.w_poi * stations_df["n_poi"]
        stations_df["contrib_dist"] = self.w_dist * stations_df["n_dist"]
        stations_df["contrib_cost"] = self.w_cost * stations_df["n_cost"]
        stations_df["contrib_avail"] = self.w_avail * stations_df["n_avail"]

        stations_df["total_score"] = (
            stations_df["contrib_poi"]
            + stations_df["contrib_dist"]
            + stations_df["contrib_cost"]
            + stations_df["contrib_avail"]
        )

        ranked = stations_df.sort_values(by="total_score", ascending=False)
        if include_llm_context:
            ranked = self.attach_llm_context(ranked)
        return ranked

    # ------------------------------------------------------------------
    # Full pipeline
    # ------------------------------------------------------------------
    def recommend(self, *, include_llm_context: bool = False) -> pd.DataFrame:
        """Run the whole pipeline and return the ranked candidate table."""
        stations = self.build_station_dataframe()
        print(f"[{self.city}] {len(stations)} stations total; "
              f"battery {self.battery_percent:.0f}% -> reachable {self.reachable_metres / 1000:.1f} km")

        candidates = self.select_candidates(stations)
        print(f"Selected {len(candidates)} candidate stations (closest, available now).")

        candidates = self.process_distances(candidates)
        candidates = self.process_all_stations(candidates)
        return self.total_score(candidates, include_llm_context=include_llm_context)

    # ------------------------------------------------------------------
    # Explanations / LLM context
    # ------------------------------------------------------------------
    @staticmethod
    def explain_score_row(row: pd.Series) -> Dict[str, Any]:
        """Human-readable score breakdown for one ranked station."""
        def fmt_distance(metres: float) -> str:
            if metres >= 1000:
                return f"{metres / 1000:.1f} km"
            return f"{int(metres)} m"

        factors = [
            ("poi", "nearby places (POI)", row.get("poi_sum"), row["n_poi"], row.get("contrib_poi")),
            ("distance", "travel distance", row.get("distance"), row["n_dist"], row.get("contrib_dist")),
            ("cost", "charging cost", row.get("cost"), row["n_cost"], row.get("contrib_cost")),
            ("availability", "connectors free now", row.get("available_points"), row["n_avail"], row.get("contrib_avail")),
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
                f"cost {row['n_cost']:.2f}, availability {row['n_avail']:.2f})."
            ),
            "reasons": reasons[:5],
            "breakdown": breakdown,
            "distance_text": fmt_distance(float(row.get("distance") or 0)),
            "cost_text": f"NT${float(row.get('cost') or 0):.2f} (typical charging rate)",
            "availability_text": (
                f"{int(row.get('available_points') or 0)} of "
                f"{int(row.get('total_connectors') or 0)} connectors free now"
            ),
        }

    def build_llm_station_record(
        self,
        row: pd.Series,
        *,
        user_location: Optional[Tuple[float, float]] = None,
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
            "station_id": row.get("StationID"),
            "station_name": row.get("station_name"),
            "coordinates": {
                "latitude": float(row["lat"]) if pd.notna(row.get("lat")) else None,
                "longitude": float(row["lon"]) if pd.notna(row.get("lon")) else None,
            },
            "user_location": {
                "latitude": float(user_loc[0]),
                "longitude": float(user_loc[1]),
            },
            "distance_metres": float(row["distance"]) if pd.notna(row.get("distance")) else None,
            "cost": float(row["cost"]) if pd.notna(row.get("cost")) else None,
            "available_points": int(row.get("available_points") or 0),
            "total_connectors": int(row.get("total_connectors") or 0),
            "poi_sum": float(row["poi_sum"]) if pd.notna(row.get("poi_sum")) else None,
            "poi_count": int(row.get("poi_count") or len(poi_nearby)),
            "nearby_pois": poi_nearby,
            "scores": {
                "total_score": float(row["total_score"]),
                "normalized": {
                    "poi": float(row["n_poi"]),
                    "distance": float(row["n_dist"]),
                    "cost": float(row["n_cost"]),
                    "availability": float(row["n_avail"]),
                },
                "weighted_contributions": {
                    "poi": float(row.get("contrib_poi", 0)),
                    "distance": float(row.get("contrib_dist", 0)),
                    "cost": float(row.get("contrib_cost", 0)),
                    "availability": float(row.get("contrib_avail", 0)),
                },
            },
            "explanation": explanation,
        }

    def attach_llm_context(self, ranked_df: pd.DataFrame) -> pd.DataFrame:
        """Add ``rank``, ``score_explanation``, and ``llm_context`` columns."""
        out = ranked_df.copy()
        out["rank"] = np.arange(1, len(out) + 1)
        out["score_explanation"] = out.apply(self.explain_score_row, axis=1)
        out["llm_context"] = out.apply(
            lambda row: self.build_llm_station_record(row), axis=1
        )
        return out


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    # Example: user near Taipei Main Station with 35% battery.
    current_user_pos = (25.0478, 121.5170)
    battery_percent = 35.0

    model = Calculation_Model(current_user_pos, battery_percent, city="Taipei")
    final_ranked_df = model.recommend(include_llm_context=True)

    export_cols = [
        c
        for c in final_ranked_df.columns
        if c not in ("poi_nearby", "score_explanation", "llm_context")
    ]
    final_ranked_df[export_cols].to_csv("final_recommendations_summary.csv", index=False)

    print(
        final_ranked_df[
            [
                "station_name",
                "distance",
                "poi_sum",
                "cost",
                "available_points",
                "total_score",
            ]
        ]
    )

    best = final_ranked_df.iloc[0]
    print(f"\nBest station: {best['station_name']} (score {best['total_score']:.3f})")

    try:
        from llm import print_reflection_report, run_reflection_pipeline

        top_context = best["llm_context"]
        alternatives = final_ranked_df.iloc[1:4]["llm_context"].tolist()
        reflection = run_reflection_pipeline(
            {"recommended": top_context, "alternatives": alternatives}
        )
        print_reflection_report(reflection)
    except Exception as exc:  # LLM step is optional; ranking already done.
        print(f"(Skipping LLM reflection: {exc})")


if __name__ == "__main__":
    main()
