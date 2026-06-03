"""Core decision engine -- coordinates Models A & B, routing, and weather.

Implements the full decision flow:
    T_total  =  T_travel  +  T_wait

When a user-selected timestamp is provided, the Data Context Engine
(``SequenceBuilder``) retrieves the 12 most recent historical sessions
for the station and feeds them to the LSTM models alongside the
traditional single-point classifiers / regressors.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

from .battery import (
    EVBatteryState,
    describe_ev_range,
    filter_stations_by_battery,
    station_within_battery_range,
)
from .config import AVAILABILITY_THRESHOLD
from .model_a import AvailabilityPrediction, ModelAService
from .model_b import DurationPrediction, ModelBService
from .preprocessing import InferencePreprocessor, build_raw_feature_row
from .routing import RouteResult, RoutingService
from .sequence_builder import SequenceBuilder
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
    sequence_context: Optional[Dict] = None       # LSTM confidence context


@dataclass
class OrchestratorResponse:
    success: bool
    message: str
    best: Optional[Dict] = None
    all_results: List[Dict] = field(default_factory=list)
    user_location: Optional[Dict] = None
    range_estimate: Optional[Dict] = None
    stations_excluded_by_range: int = 0


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
        self.seq_builder = SequenceBuilder()
        self.seq_builder.set_preprocessor(self.preprocessor)

    # ── Public API ───────────────────────────────────────────────────────────

    def evaluate_station(
        self,
        user_lat: float,
        user_lon: float,
        station_mac: str,
        selected_time: Optional[datetime] = None,
    ) -> StationResult:
        """Run the full pipeline for **one** station."""
        station = self.registry.get(station_mac)
        if station is None:
            raise ValueError(f"Unknown station MAC: {station_mac}")
        return self._run_pipeline(user_lat, user_lon, station, selected_time)

    def find_best_station(
        self,
        user_lat: float,
        user_lon: float,
        selected_time: Optional[datetime] = None,
        ev_battery: Optional[EVBatteryState] = None,
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

        range_info: Optional[Dict] = None
        excluded = 0
        if ev_battery is not None:
            nearby, excluded, range_info = filter_stations_by_battery(
                nearby, user_lat, user_lon, ev_battery,
            )
            if not nearby:
                ri = range_info or describe_ev_range(ev_battery)
                return OrchestratorResponse(
                    success=False,
                    message=(
                        f"No stations within your estimated range "
                        f"(~{ri['max_drivable_km']:.1f} km at {ri['soc_percent']:.0f}% battery)."
                    ),
                    range_estimate=range_info,
                    stations_excluded_by_range=excluded,
                    user_location={"lat": user_lat, "lon": user_lon},
                )

        results: List[StationResult] = []
        for station in nearby:
            try:
                results.append(self._run_pipeline(user_lat, user_lon, station, selected_time))
            except Exception as exc:
                print(f"[Orchestrator] Skipping {station.mac}: {exc}")

        if not results:
            return OrchestratorResponse(success=False, message="All station evaluations failed.")

        results.sort(key=lambda r: r.total_mins)
        msg = f"Evaluated {len(results)} station(s). Best option shown first."
        if ev_battery is not None and excluded:
            msg += f" ({excluded} station(s) removed — out of battery range.)"
        return OrchestratorResponse(
            success=True,
            message=msg,
            best=self._serialise(results[0]),
            all_results=[self._serialise(r) for r in results],
            user_location={"lat": user_lat, "lon": user_lon},
            range_estimate=range_info,
            stations_excluded_by_range=excluded,
        )

    def evaluate_single(
        self,
        user_lat: float,
        user_lon: float,
        station_mac: str,
        selected_time: Optional[datetime] = None,
        ev_battery: Optional[EVBatteryState] = None,
    ) -> OrchestratorResponse:
        """Evaluate a specific station."""
        if not is_within_palo_alto(user_lat, user_lon):
            return OrchestratorResponse(
                success=False,
                message="Your location is outside the Palo Alto boundary.",
            )

        station = self.registry.get(station_mac)
        if station is None:
            return OrchestratorResponse(success=False, message=f"Unknown station MAC: {station_mac}")

        range_info: Optional[Dict] = None
        if ev_battery is not None:
            range_info = describe_ev_range(ev_battery)
            if not station_within_battery_range(station, user_lat, user_lon, ev_battery):
                return OrchestratorResponse(
                    success=False,
                    message=(
                        f"{station.name} is outside your estimated range "
                        f"(~{range_info['max_drivable_km']:.1f} km at "
                        f"{range_info['soc_percent']:.0f}% battery)."
                    ),
                    range_estimate=range_info,
                    user_location={"lat": user_lat, "lon": user_lon},
                )

        try:
            result = self.evaluate_station(user_lat, user_lon, station_mac, selected_time)
        except ValueError as exc:
            return OrchestratorResponse(success=False, message=str(exc))

        return OrchestratorResponse(
            success=True,
            message="Station evaluation complete.",
            best=self._serialise(result),
            all_results=[self._serialise(result)],
            user_location={"lat": user_lat, "lon": user_lon},
            range_estimate=range_info,
        )

    # ── Internal pipeline ────────────────────────────────────────────────────

    def _run_pipeline(
        self,
        user_lat: float,
        user_lon: float,
        station: Station,
        selected_time: Optional[datetime] = None,
    ) -> StationResult:
        now = selected_time or datetime.now()
        weather = self.weather.get_current()

        # 1. Build single-row feature vector for traditional models
        raw_df = build_raw_feature_row(station, weather, now)

        # 2. Model A -- availability (traditional classifiers)
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

        # 2b. Model A -- LSTM availability (sequence-based)
        seq_context = None
        if self.model_a.lstm_loaded:
            try:
                seq_a, ctx_a = self.seq_builder.get_sequence(
                    station.mac, target_time=now, model_type="availability",
                )
                lstm_avail = self.model_a.predict_lstm(seq_a)
                if lstm_avail:
                    availability_preds.append(lstm_avail)
                    seq_context = ctx_a
            except Exception as exc:
                print(f"[Orchestrator] Model A LSTM skipped: {exc}")

        # 3. Model B -- duration (only when occupied)
        wait_secs = 0.0
        duration_preds = []
        if status == "Occupied":
            # 3a. Traditional regressors
            if self.model_b.loaded:
                features_b = self.preprocessor.transform(raw_df, model_type="duration")
                duration_preds = self.model_b.predict(features_b)

                ensemble = self.model_b.predict_ensemble(features_b)
                if ensemble:
                    wait_secs = ensemble.duration_secs

            # 3b. LSTM duration prediction (sequence-based)
            if self.model_b.lstm_model is not None:
                try:
                    seq_b, ctx_b = self.seq_builder.get_sequence(
                        station.mac, target_time=now, model_type="duration",
                    )
                    lstm_dur = self.model_b.predict_lstm(seq_b)
                    if lstm_dur:
                        duration_preds.append(lstm_dur)
                        if seq_context is None:
                            seq_context = ctx_b
                except Exception as exc:
                    print(f"[Orchestrator] Model B LSTM skipped: {exc}")

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
            sequence_context=seq_context,
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
            "sequence_context": result.sequence_context,
        }
