"""Core decision engine — coordinates Models A & B, routing, and weather.

Implements the full decision flow:
    T_total  =  T_travel  +  T_wait
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

from .model_a import AvailabilityPrediction, ModelAService
from .model_b import DurationPrediction, ModelBService
from .preprocessing import InferencePreprocessor, build_raw_feature_row
from .routing import RouteResult, RoutingService
from .stations import Station, StationRegistry, is_within_palo_alto
from .weather import WeatherService


@dataclass
class StationResult:
    station: Station
    status: str                                   # "Available" / "Occupied"
    travel_mins: float
    wait_mins: float
    total_mins: float
    route: Optional[RouteResult]
    availability_detail: List[Dict]               # per-model breakdown
    duration_detail: List[Dict]                    # per-model breakdown (empty if available)
    consensus: Optional[Dict] = None
    low_confidence_warning: bool = False


@dataclass
class OrchestratorResponse:
    success: bool
    message: str
    best: Optional[Dict] = None
    all_results: List[Dict] = field(default_factory=list)
    user_location: Optional[Dict] = None


class EVPathfinderOrchestrator:
    """Top-level orchestrator that wires every service together."""

    def __init__(self):
        print("[Orchestrator] Loading station registry...")
        self.registry = StationRegistry()
        print(f"[Orchestrator] {len(self.registry.all_stations)} Palo Alto stations loaded.")

        self.weather = WeatherService()
        self.preprocessor = InferencePreprocessor()
        self.model_a = ModelAService()
        self.model_b = ModelBService()
        self.routing = RoutingService()

    # ── Public API ───────────────────────────────────────────────────────────

    def evaluate_station(
        self,
        user_lat: float,
        user_lon: float,
        station_mac: str,
    ) -> StationResult:
        """Run the full pipeline for **one** station."""
        station = self.registry.get(station_mac)
        if station is None:
            raise ValueError(f"Unknown station MAC: {station_mac}")
        return self._run_pipeline(user_lat, user_lon, station)

    def find_best_station(
        self,
        user_lat: float,
        user_lon: float,
    ) -> OrchestratorResponse:
        """Evaluate all stations within 5 mi and return the optimal one."""
        if not is_within_palo_alto(user_lat, user_lon):
            return OrchestratorResponse(
                success=False,
                message="Your location is outside the Palo Alto boundary. "
                        "Please enter coordinates within Palo Alto, CA.",
            )

        nearby = self.registry.find_nearby(user_lat, user_lon)
        if not nearby:
            return OrchestratorResponse(
                success=False,
                message="No stations found within 5-mile radius.",
            )

        results: List[StationResult] = []
        for station in nearby:
            try:
                results.append(self._run_pipeline(user_lat, user_lon, station))
            except Exception as exc:
                print(f"[Orchestrator] Skipping {station.mac}: {exc}")

        if not results:
            return OrchestratorResponse(success=False, message="All station evaluations failed.")

        results.sort(key=lambda r: r.total_mins)
        return OrchestratorResponse(
            success=True,
            message=f"Evaluated {len(results)} station(s). Best option shown first.",
            best=self._serialise(results[0]),
            all_results=[self._serialise(r) for r in results],
            user_location={"lat": user_lat, "lon": user_lon},
        )

    def evaluate_single(
        self,
        user_lat: float,
        user_lon: float,
        station_mac: str,
    ) -> OrchestratorResponse:
        """Evaluate a specific station."""
        if not is_within_palo_alto(user_lat, user_lon):
            return OrchestratorResponse(
                success=False,
                message="Your location is outside the Palo Alto boundary.",
            )

        try:
            result = self.evaluate_station(user_lat, user_lon, station_mac)
        except ValueError as exc:
            return OrchestratorResponse(success=False, message=str(exc))

        return OrchestratorResponse(
            success=True,
            message="Station evaluation complete.",
            best=self._serialise(result),
            all_results=[self._serialise(result)],
            user_location={"lat": user_lat, "lon": user_lon},
        )

    # ── Internal pipeline ────────────────────────────────────────────────────

    def _run_pipeline(
        self,
        user_lat: float,
        user_lon: float,
        station: Station,
    ) -> StationResult:
        now = datetime.now()
        weather = self.weather.get_current()

        # 1. Build feature row
        raw_df = build_raw_feature_row(station, weather, now)

        # 2. Model A — availability
        availability_preds = []
        consensus = None
        status = "Available"
        low_confidence = False

        if self.model_a.loaded:
            features_a = self.preprocessor.transform(raw_df, model_type="availability")
            availability_preds = self.model_a.predict(features_a)
            consensus = self.model_a.predict_consensus(features_a)
            if consensus:
                status = "Available" if consensus.available else "Occupied"
                low_confidence = consensus.confidence == "low"

        # 3. Model B — duration (only when occupied)
        wait_secs = 0.0
        duration_preds = []
        if status == "Occupied" and self.model_b.loaded:
            features_b = self.preprocessor.transform(raw_df, model_type="duration")
            duration_preds_raw = self.model_b.predict(features_b)
            duration_preds = duration_preds_raw

            ensemble = self.model_b.predict_ensemble(features_b)
            if ensemble:
                wait_secs = ensemble.duration_secs

        # 4. Routing
        route = self.routing.get_route(
            origin=(user_lat, user_lon),
            destination=(station.latitude, station.longitude),
        )
        travel_secs = route.duration_secs if route else 0

        # 5. Final calculation
        wait_mins = round(wait_secs / 60, 1)
        travel_mins = round(travel_secs / 60, 1)
        total_mins = round(travel_mins + wait_mins, 1)

        return StationResult(
            station=station,
            status=status,
            travel_mins=travel_mins,
            wait_mins=wait_mins,
            total_mins=total_mins,
            route=route,
            availability_detail=[asdict(p) for p in availability_preds],
            duration_detail=[asdict(p) for p in duration_preds],
            consensus=asdict(consensus) if consensus else None,
            low_confidence_warning=low_confidence,
        )

    @staticmethod
    def _serialise(result: StationResult) -> Dict:
        route_data = None
        if result.route:
            route_data = {
                "distance_metres": result.route.distance_metres,
                "duration_secs": result.route.duration_secs,
                "duration_mins": result.route.duration_mins,
                "polyline": result.route.polyline,
                "decoded_points": result.route.decoded_points,
            }
        return {
            "station": {
                "mac": result.station.mac,
                "name": result.station.name,
                "address": result.station.address,
                "lat": result.station.latitude,
                "lon": result.station.longitude,
                "plug_type": result.station.plug_type,
            },
            "status": result.status,
            "travel_mins": result.travel_mins,
            "wait_mins": result.wait_mins,
            "total_mins": result.total_mins,
            "route": route_data,
            "availability_detail": result.availability_detail,
            "duration_detail": result.duration_detail,
            "consensus": result.consensus,
            "low_confidence_warning": result.low_confidence_warning,
        }
