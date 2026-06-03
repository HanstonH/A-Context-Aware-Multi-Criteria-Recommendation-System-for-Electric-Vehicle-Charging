"""User battery input for range filtering — delegates to ``Algorithm/logic.py``."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import List, Optional, TYPE_CHECKING

_ALGO_DIR = Path(__file__).resolve().parent.parent / "Algorithm"
if str(_ALGO_DIR) not in sys.path:
    sys.path.insert(0, str(_ALGO_DIR))

from logic import (  # noqa: E402
    EVBatteryState,
    describe_ev_range,
    estimate_max_drivable_distance_m,
    parse_user_battery,
)

if TYPE_CHECKING:
    from .stations import Station

__all__ = [
    "EVBatteryState",
    "describe_ev_range",
    "estimate_max_drivable_distance_m",
    "filter_stations_by_battery",
    "parse_user_battery",
    "station_within_battery_range",
]


def filter_stations_by_battery(
    stations: List["Station"],
    user_lat: float,
    user_lon: float,
    ev_battery: EVBatteryState,
) -> tuple[List["Station"], int, Dict[str, float]]:
    """
    Keep stations within estimated drivable range (haversine pre-filter).

    Returns ``(reachable_stations, excluded_count, range_info)``.
    """
    from .stations import _haversine_metres

    max_range_m = estimate_max_drivable_distance_m(ev_battery)
    range_info = describe_ev_range(ev_battery)
    reachable: List[Station] = []
    excluded = 0

    for station in stations:
        dist_m = _haversine_metres(user_lat, user_lon, station.latitude, station.longitude)
        if dist_m <= max_range_m:
            reachable.append(station)
        else:
            excluded += 1

    return reachable, excluded, range_info


def station_within_battery_range(
    station: "Station",
    user_lat: float,
    user_lon: float,
    ev_battery: EVBatteryState,
) -> bool:
    """True if straight-line distance is within estimated drivable range."""
    from .stations import _haversine_metres

    max_range_m = estimate_max_drivable_distance_m(ev_battery)
    dist_m = _haversine_metres(user_lat, user_lon, station.latitude, station.longitude)
    return dist_m <= max_range_m
