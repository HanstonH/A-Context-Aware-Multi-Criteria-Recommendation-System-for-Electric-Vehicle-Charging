"""Charger ranking: range filter first, then context-aware TOPSIS over distance, wait and cost.

This follows AI/Algorithm/logic.py (``get_exponential_weights`` and ``topsis_rank``)
without its numpy/pandas imports:

* range = 0.85 × usable Wh ÷ Wh per km
* weights depend on the battery level (exponential curves): low battery puts
  weight on distance and on getting a charger; high battery shifts it to price.
  "Need a charger now" mode uses a fixed urgency vector.
* ``total_score`` is the TOPSIS closeness coefficient C ∈ [0, 1]: how close the
  station is to an ideal one (shortest, no wait, cheapest) relative to the worst.
* ``normalized`` (min-max, "lower is better", all-equal = 1.0) and
  ``contributions`` (weight × normalized) are kept as an explanation of the score.

Differences from logic.py, on purpose:
* logic.py's third criterion is "available connectors" (more is better); here it is
  predicted waiting time (less is better). Both answer "will I get a charger?", so
  waiting time gets that weight. It is a placeholder (see wait_model.py) that is the
  same for every station, so it can't change the order until the real model lands.
* POI is not used.
* Stations with no price get the median price of the other candidates, so a
  missing price neither helps nor hurts. logic.py filled them with 0, which
  made unknown prices look cheapest.
"""

from __future__ import annotations

import math
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


# ── Context-aware weights (same curves and constants as AI/Algorithm/logic.py) ──
# Survival: distance and charger availability matter more as the battery drops.
_W_BASE_DIST = 0.10
_W_SURVIVAL_AMP_DIST = 0.60
_W_BASE_WAIT = 0.15  # logic.py: _W_BASE_POTS
_W_SURVIVAL_AMP_WAIT = 0.30  # logic.py: _W_SURVIVAL_AMP_POTS
_K_SURVIVAL = 7.0
# Comfort: price matters more as the battery rises.
_W_MAX_COST = 0.40
_K_COMFORT = 4.0
# "Need a charger now": [distance, cost, wait] in logic.py order [dist, cost, pots].
_URGENCY_WEIGHTS = {"distance": 0.60, "cost": 0.05, "wait": 0.35}
# When urgent, a station known to be busy gets this × the farthest distance, so it
# ranks last without being dropped (same as logic.py's _OCCUPIED_DISTANCE_FACTOR).
_OCCUPIED_DISTANCE_FACTOR = 2.0


def context_weights(battery_pct: float, available_now: bool = False) -> dict[str, float]:
    """Criterion weights for the current context; they always sum to 1."""
    if available_now:
        return dict(_URGENCY_WEIGHTS)
    b = max(0.0, min(1.0, float(battery_pct) / 100))
    survival = math.exp(-_K_SURVIVAL * b)
    comfort = 1.0 - math.exp(-_K_COMFORT * b)
    raw = {
        "distance": _W_BASE_DIST + _W_SURVIVAL_AMP_DIST * survival,
        "wait": _W_BASE_WAIT + _W_SURVIVAL_AMP_WAIT * survival,
        "cost": _W_MAX_COST * comfort,
    }
    total = sum(raw.values())
    return {k: v / total for k, v in raw.items()}


def topsis_scores(rows: list[list[float]], weights: list[float]) -> list[float]:
    """TOPSIS closeness coefficient per row, for criteria that are all "lower is better".

    Vector-normalize each column, weight it, then score each row by its distance to the
    worst value per column relative to its distances to the best and the worst. An
    all-zero column (e.g. the placeholder wait) scores the same for everyone and so
    has no effect. Identical rows score 0.5.
    """
    if not rows:
        return []
    cols = range(len(weights))
    norms = [math.sqrt(sum(r[j] ** 2 for r in rows)) or 1.0 for j in cols]
    v = [[r[j] / norms[j] * weights[j] for j in cols] for r in rows]
    best = [min(r[j] for r in v) for j in cols]
    worst = [max(r[j] for r in v) for j in cols]
    scores = []
    for r in v:
        d_best = math.sqrt(sum((r[j] - best[j]) ** 2 for j in cols))
        d_worst = math.sqrt(sum((r[j] - worst[j]) ** 2 for j in cols))
        denom = d_best + d_worst
        scores.append(0.5 if denom == 0 else d_worst / denom)
    return scores


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
    available_now: bool = False,
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

    weights = context_weights(battery_pct, available_now)
    base = {
        "range": rng,
        "method": "topsis",
        "available_now": available_now,
        "weights": {k: round(v, 4) for k, v in weights.items()},
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

    # TOPSIS decides the order. When urgent, stations known to be busy are scored
    # as if they were twice as far as the farthest candidate (ranked last, not dropped).
    topsis_dist = [r["distance_m"] for r in rows]
    if available_now:
        far = _OCCUPIED_DISTANCE_FACTOR * max(max(topsis_dist), 1.0)
        topsis_dist = [far if r["wait"].available is False else d for r, d in zip(rows, topsis_dist)]
    closeness = topsis_scores(
        [[d, r["wait"].seconds, c] for r, d, c in zip(rows, topsis_dist, costs)],
        [weights["distance"], weights["wait"], weights["cost"]],
    )

    results = []
    for r, nd, nw, nc, cost, total in zip(rows, n_dist, n_wait, n_cost, costs, closeness):
        s: Station = r["station"]
        # Explanation only: how much each factor favours this station (weight × min-max score).
        contrib = {
            "distance": weights["distance"] * nd,
            "wait": weights["wait"] * nw,
            "cost": weights["cost"] * nc,
        }
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
