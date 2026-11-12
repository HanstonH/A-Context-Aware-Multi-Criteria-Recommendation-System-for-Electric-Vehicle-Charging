"""Charger ranking: range filter first, then a weighted score of distance, wait and cost.

This follows AI/Algorithm/logic.py (``filter_stations_within_range`` and
``Calculation_Model.total_score``) without its heavy imports:

* range = 0.85 × usable Wh ÷ Wh per km
* each factor is min-max normalized with "lower is better"
  (all-equal values score 1.0, exactly like ``_normalize_lower_is_better``)
* total = Σ weight × normalized score

Differences, on purpose:
* POI is not used (its weight is shared by the other three).
* Waiting time is a placeholder (see wait_model.py), so it can't change the order.
* Stations with no price get the median price of the other candidates, so a
  missing price neither helps nor hurts. logic.py filled them with 0, which
  made unknown prices look cheapest.
"""

from __future__ import annotations

import statistics
from datetime import datetime, timedelta, timezone

from . import config
from .data import Station, store
from .geo import City, haversine_km
from .routing import road_distances
from .wait_model import predict_wait_seconds

TAIPEI_TZ = timezone(timedelta(hours=8))


def estimate_range(
    battery_pct: float,
    capacity_kwh: float = config.DEFAULT_CAPACITY_KWH,
    wh_per_km: float = config.DEFAULT_WH_PER_KM,
) -> dict:
    battery_pct = max(0.0, min(100.0, float(battery_pct)))
    usable_wh = max(0.0, battery_pct / 100 * capacity_kwh * 1000 - config.STOPPING_THRESHOLD_WH)
    range_km = config.RANGE_SAFETY_FACTOR * usable_wh / max(1e-6, wh_per_km)
    return {
        "battery_pct": battery_pct,
        "capacity_kwh": capacity_kwh,
        "wh_per_km": wh_per_km,
        "safety_factor": config.RANGE_SAFETY_FACTOR,
        "usable_wh": round(usable_wh),
        "max_range_km": round(range_km, 1),
    }


def _lower_is_better(values: list[float]) -> list[float]:
    lo, hi = min(values), max(values)
    if hi == lo:
        return [1.0] * len(values)
    return [(hi - v) / (hi - lo) for v in values]


def recommend(
    lat: float,
    lng: float,
    battery_pct: float,
    *,
    capacity_kwh: float = config.DEFAULT_CAPACITY_KWH,
    wh_per_km: float = config.DEFAULT_WH_PER_KM,
    city: City | None = None,
    limit: int = 5,
    include_ids: tuple[str, ...] = (),
    lang: str = "en",
) -> dict:
    rng = estimate_range(battery_pct, capacity_kwh, wh_per_km)
    range_km = rng["max_range_km"]
    radius = range_km if city else min(range_km, config.MAX_SEARCH_RADIUS_KM)

    pool = store().nearest(lat, lng, radius_km=radius, city=city, limit=config.CANDIDATE_LIMIT)
    pooled_ids = {s.id for s, _ in pool}
    for sid in include_ids:
        s = store().get(sid)
        if s and sid not in pooled_ids:
            pool.append((s, haversine_km(lat, lng, s.lat, s.lng)))

    weights = {"distance": config.WEIGHT_DISTANCE, "wait": config.WEIGHT_WAIT, "cost": config.WEIGHT_COST}
    base = {
        "range": rng,
        "weights": weights,
        "search_radius_km": round(radius, 1),
        "city": city.code if city else None,
    }
    if not pool:
        return {**base, "ok": False, "reason": "no_station_in_range", "results": [], "considered": 0}

    stations = [s for s, _ in pool]
    metres, seconds, road_source = road_distances((lat, lng), [(s.lat, s.lng) for s in stations])

    now = datetime.now(TAIPEI_TZ)
    rows = []
    for s, straight_km, m, sec in zip(stations, (k for _, k in pool), metres, seconds):
        reachable = m <= range_km * 1000
        if not reachable and s.id not in include_ids:
            continue
        arrival = now + timedelta(seconds=sec or 0)
        wait = predict_wait_seconds(s, arrival=arrival, road_seconds=sec)
        rows.append(
            {
                "station": s,
                "straight_km": straight_km,
                "distance_m": m,
                "duration_s": sec,
                "wait": wait,
                "reachable": reachable,
            }
        )

    excluded = len(stations) - len(rows)
    if not rows:
        return {
            **base,
            "ok": False,
            "reason": "no_station_reachable_by_road",
            "results": [],
            "considered": len(stations),
            "excluded_by_range": excluded,
        }

    known = [r["station"].price_ntd_per_kwh for r in rows if r["station"].price_ntd_per_kwh is not None]
    fill = statistics.median(known) if known else 0.0
    costs = [
        r["station"].price_ntd_per_kwh if r["station"].price_ntd_per_kwh is not None else fill
        for r in rows
    ]

    n_dist = _lower_is_better([r["distance_m"] for r in rows])
    n_wait = _lower_is_better([r["wait"].seconds for r in rows])
    n_cost = _lower_is_better(costs)

    results = []
    for r, nd, nw, nc, cost in zip(rows, n_dist, n_wait, n_cost, costs):
        s: Station = r["station"]
        contrib = {
            "distance": weights["distance"] * nd,
            "wait": weights["wait"] * nw,
            "cost": weights["cost"] * nc,
        }
        total = sum(contrib.values())
        reasons = []
        if nd >= 0.75:
            reasons.append("shorter drive than most options")
        if s.price_ntd_per_kwh is not None and nc >= 0.75 and len(known) > 1:
            reasons.append("cheaper than most options")
        results.append(
            {
                **s.brief(lat, lng, lang),
                "distance_m": round(r["distance_m"]),
                "distance_source": road_source,
                "duration_s": round(r["duration_s"]) if r["duration_s"] is not None else None,
                "reachable": r["reachable"],
                "wait": {
                    "seconds": r["wait"].seconds,
                    "placeholder": r["wait"].placeholder,
                    "available": r["wait"].available,
                },
                "cost": {
                    "ntd_per_kwh": s.price_ntd_per_kwh,
                    "known": s.price_ntd_per_kwh is not None,
                    "value_used": round(cost, 2),
                },
                "normalized": {"distance": round(nd, 3), "wait": round(nw, 3), "cost": round(nc, 3)},
                "contributions": {k: round(v, 3) for k, v in contrib.items()},
                "total_score": round(total, 4),
                "reasons": reasons,
            }
        )

    results.sort(key=lambda x: (-x["total_score"], x["distance_m"]))
    for i, item in enumerate(results, 1):
        item["rank"] = i

    return {
        **base,
        "ok": True,
        "considered": len(stations),
        "excluded_by_range": excluded,
        "prices_known": len(known),
        "wait_is_placeholder": any(r["wait"].placeholder for r in rows),
        "all_results": results,
        "results": [r for r in results if r["reachable"]][:limit],
    }
