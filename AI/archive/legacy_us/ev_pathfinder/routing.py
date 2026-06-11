"""Routing service — Google Routes API integration for real-time travel time."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

import requests

from .config import GOOGLE_MAPS_API_KEY, ROUTES_API_URL


@dataclass
class RouteResult:
    distance_metres: int
    duration_secs: int
    duration_mins: float
    polyline: str               # encoded polyline
    decoded_points: List[Tuple[float, float]]


def _decode_polyline(encoded: str) -> List[Tuple[float, float]]:
    points: List[Tuple[float, float]] = []
    index = lat = lng = 0

    while index < len(encoded):
        for is_lat in (True, False):
            shift = result = 0
            while True:
                byte = ord(encoded[index]) - 63
                index += 1
                result |= (byte & 0x1F) << shift
                shift += 5
                if byte < 0x20:
                    break
            delta = ~(result >> 1) if result & 1 else result >> 1
            if is_lat:
                lat += delta
            else:
                lng += delta
        points.append((lat / 1e5, lng / 1e5))

    return points


class RoutingService:
    """Wraps the Google Routes API ``computeRoutes`` endpoint."""

    def get_route(
        self,
        origin: Tuple[float, float],
        destination: Tuple[float, float],
    ) -> Optional[RouteResult]:
        if not GOOGLE_MAPS_API_KEY:
            return self._fallback_estimate(origin, destination)

        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": GOOGLE_MAPS_API_KEY,
            "X-Goog-FieldMask": "routes.distanceMeters,routes.duration,routes.polyline.encodedPolyline",
        }
        payload = {
            "origin": {"location": {"latLng": {"latitude": origin[0], "longitude": origin[1]}}},
            "destination": {"location": {"latLng": {"latitude": destination[0], "longitude": destination[1]}}},
            "travelMode": "DRIVE",
            "routingPreference": "TRAFFIC_AWARE",
            "computeAlternativeRoutes": False,
            "units": "METRIC",
        }

        try:
            resp = requests.post(ROUTES_API_URL, json=payload, headers=headers, timeout=10)
            if resp.status_code != 200:
                print(f"[Routing] API error {resp.status_code}: {resp.text[:200]}")
                return self._fallback_estimate(origin, destination)

            data = resp.json()
            route = data["routes"][0]
            dist = int(route["distanceMeters"])
            dur_str = route["duration"]  # e.g. "523s"
            dur_secs = int(dur_str.rstrip("s"))
            enc_poly = route.get("polyline", {}).get("encodedPolyline", "")

            return RouteResult(
                distance_metres=dist,
                duration_secs=dur_secs,
                duration_mins=round(dur_secs / 60, 1),
                polyline=enc_poly,
                decoded_points=_decode_polyline(enc_poly) if enc_poly else [],
            )
        except Exception as exc:
            print(f"[Routing] Exception: {exc}")
            return self._fallback_estimate(origin, destination)

    @staticmethod
    def _fallback_estimate(
        origin: Tuple[float, float],
        destination: Tuple[float, float],
    ) -> RouteResult:
        """Haversine-based straight-line estimate when the API is unavailable."""
        import math
        R = 6_371_000
        lat1, lon1 = math.radians(origin[0]), math.radians(origin[1])
        lat2, lon2 = math.radians(destination[0]), math.radians(destination[1])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        dist = int(2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a)))
        speed_ms = 11.0  # ~40 km/h urban
        dur_secs = int(dist / speed_ms)
        return RouteResult(
            distance_metres=dist,
            duration_secs=dur_secs,
            duration_mins=round(dur_secs / 60, 1),
            polyline="",
            decoded_points=[origin, destination],
        )
