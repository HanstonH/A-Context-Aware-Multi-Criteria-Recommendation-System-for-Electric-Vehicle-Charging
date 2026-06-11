"""Full recommendation scoring via Algorithm/logic.py (distance, POI, wait, cost).

Mirrors the working ``logic.py`` ``main()`` pipeline:
    process_all_stations -> process_waiting_times -> total_score
Distance is taken from the route already computed by the orchestrator.
"""

from __future__ import annotations

import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from .feature_engineering import complete_model_row, station_fee
from .weather import WeatherService, WeatherSnapshot

_ALGORITHM_DIR = Path(__file__).resolve().parent.parent / "Algorithm"
if str(_ALGORITHM_DIR) not in sys.path:
    sys.path.insert(0, str(_ALGORITHM_DIR))

from logic import Calculation_Model  # noqa: E402


class RecommendationScoringService:
    """Builds a ranked score table using the same steps as ``logic.py``."""

    def rank_stations(
        self,
        user_lat: float,
        user_lon: float,
        evaluated: List[Dict[str, Any]],
        *,
        weather: Optional[WeatherSnapshot] = None,
        at_time: Optional[datetime] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Parameters
        ----------
        evaluated : list of dicts with keys:
            mac, station_name, lat, lon, plug_encoded, distance_metres
        """
        if not evaluated:
            return {}

        at_time = at_time or datetime.now()
        weather = weather or WeatherService().get_current()
        records: List[Dict[str, Any]] = []

        for item in evaluated:
            name = str(item["station_name"]).strip()
            fee = station_fee(name)
            base_row = {
                "MAC Address": item["mac"],
                "temp": weather.temperature,
                "precip": weather.precipitation,
                "clouds": weather.cloud_cover,
                "Plug Type Encoded": item["plug_encoded"],
            }
            feature_row = complete_model_row(base_row, dt=at_time, fee=fee).iloc[0].to_dict()
            feature_row.update({
                "mac": item["mac"],
                "Station Name": name,
                "lat": item["lat"],
                "lon": item["lon"],
                "distance": float(item["distance_metres"]),
                "cost": fee,
                "fee": fee,
            })
            records.append(feature_row)

        df = pd.DataFrame(records)
        model = Calculation_Model((user_lat, user_lon))

        print(f"[Scoring] Running logic.py pipeline for {len(df)} station(s)...")
        df = model.process_all_stations(df)
        df = model.process_waiting_times(df, at_time=at_time)
        ranked = model.total_score_with_breakdown(df)

        scores: Dict[str, Dict[str, Any]] = {}
        for _, row in ranked.iterrows():
            mac = row["mac"]
            explanation = Calculation_Model.explain_score_row(row)
            queue_secs = float(row.get("waiting_time", 0))
            scores[mac] = {
                "total_score": explanation["total_score"],
                "poi_sum": float(row.get("poi_sum", 0)),
                "distance_metres": float(row.get("distance", 0)),
                "waiting_time_secs": queue_secs,
                "waiting_time_mins": round(queue_secs / 60, 1),
                "queue_wait_secs": queue_secs,
                "queue_wait_mins": round(queue_secs / 60, 1),
                "cost": float(row.get("cost", 0)),
                "n_poi": float(row.get("n_poi", 0)),
                "n_dist": float(row.get("n_dist", 0)),
                "n_wait": float(row.get("n_wait", 0)),
                "n_cost": float(row.get("n_cost", 0)),
                "contrib_poi": float(row.get("contrib_poi", 0)),
                "contrib_dist": float(row.get("contrib_dist", 0)),
                "contrib_wait": float(row.get("contrib_wait", 0)),
                "contrib_cost": float(row.get("contrib_cost", 0)),
                "factors": explanation["factors"],
                "reasons": explanation["reasons"],
                "summary": explanation["summary"],
            }
        return scores

    @staticmethod
    def format_error(exc: Exception) -> str:
        return f"{exc.__class__.__name__}: {exc}\n{traceback.format_exc()}"
