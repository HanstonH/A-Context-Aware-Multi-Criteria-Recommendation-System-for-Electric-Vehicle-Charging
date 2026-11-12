"""Road distances from OSRM, falling back to straight line × detour factor."""

from __future__ import annotations

import logging

import requests

from . import config
from .geo import haversine_km

log = logging.getLogger(__name__)


def road_distances(
    origin: tuple[float, float], dests: list[tuple[float, float]]
) -> tuple[list[float], list[float | None], str]:
    """Return (metres, seconds, source) for each destination, from one OSRM table call.

    ``source`` is "osrm" or "estimate". Points OSRM can't route get an estimate too.
    """
    estimate = [
        haversine_km(origin[0], origin[1], lat, lng) * 1000 * config.ROAD_DETOUR_FACTOR
        for lat, lng in dests
    ]
    if not dests:
        return [], [], "estimate"
    coords = ";".join(f"{lng:.6f},{lat:.6f}" for lat, lng in [origin, *dests])
    url = f"{config.OSRM_URL}/table/v1/driving/{coords}"
    try:
        resp = requests.get(
            url,
            params={"sources": "0", "annotations": "distance,duration"},
            timeout=config.OSRM_TIMEOUT_S,
        )
        data = resp.json()
        if data.get("code") != "Ok":
            raise ValueError(data.get("message") or data.get("code"))
        dist_row = data["distances"][0][1:]
        dur_row = data["durations"][0][1:]
    except Exception as exc:  # network, rate limit, bad JSON
        log.warning("OSRM table failed, using straight-line estimate: %s", exc)
        return estimate, [None] * len(dests), "estimate"

    metres = [d if d is not None else e for d, e in zip(dist_row, estimate)]
    return metres, list(dur_row), "osrm"
