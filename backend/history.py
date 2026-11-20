"""Search history: each logged-in user's recent searches, stored in the users database.

An entry is one of these kinds:
- ``text``: words typed in the search box (``query``)
- ``destination``: a destination the user searched for (``query``)
- ``range``: the battery-range search (needs ``lat``, ``lng`` and ``battery_pct``)
- ``station``: a station the user opened (``station_id``, optional ``query`` = its name)

Searching for the same thing again moves it to the top instead of adding a copy.
Only the newest ``config.HISTORY_MAX`` entries are kept, since this is location data.
"""

from __future__ import annotations

import sqlite3

from . import config
from .auth import AuthError, _db

KINDS = ("text", "destination", "range", "station")
QUERY_MAX = 200
STATION_ID_MAX = 64


def _public(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "kind": row["kind"],
        "query": row["query"],
        "station_id": row["station_id"],
        "lat": row["lat"],
        "lng": row["lng"],
        "battery_pct": row["battery_pct"],
        "created_at": row["created_at"],
    }


def _number(data: dict, key: str, lo: float, hi: float) -> float | None:
    raw = data.get(key)
    if raw is None:
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        raise AuthError(f"'{key}' must be a number.") from None
    if not lo <= value <= hi:
        raise AuthError(f"'{key}' must be between {lo} and {hi}.")
    return value


def _text(data: dict, key: str, limit: int) -> str | None:
    raw = data.get(key)
    if raw is None:
        return None
    value = " ".join(str(raw).split())[:limit]
    return value or None


def _clean(data: dict) -> dict:
    kind = data.get("kind")
    if kind not in KINDS:
        raise AuthError(f"'kind' must be one of: {', '.join(KINDS)}.")
    entry = {
        "kind": kind,
        "query": _text(data, "query", QUERY_MAX),
        "station_id": _text(data, "station_id", STATION_ID_MAX),
        "lat": _number(data, "lat", -90, 90),
        "lng": _number(data, "lng", -180, 180),
        "battery_pct": _number(data, "battery_pct", 0, 100),
    }
    if (entry["lat"] is None) != (entry["lng"] is None):
        raise AuthError("Send both 'lat' and 'lng', or neither.")
    if kind in ("text", "destination") and not entry["query"]:
        raise AuthError("'query' is required for this kind.")
    if kind == "station" and not entry["station_id"]:
        raise AuthError("'station_id' is required for kind 'station'.")
    if kind == "range" and (entry["lat"] is None or entry["battery_pct"] is None):
        raise AuthError("'lat', 'lng' and 'battery_pct' are required for kind 'range'.")
    return entry


def add(user_id: int, data: dict) -> dict:
    """Save one search and return it. A repeat of an earlier search replaces it."""
    entry = _clean(data)
    with _db() as conn:
        if entry["kind"] == "range":
            # Every range search differs slightly in position; keep only the latest one.
            conn.execute("DELETE FROM search_history WHERE user_id = ? AND kind = 'range'", (user_id,))
        elif entry["kind"] == "station":
            conn.execute(
                "DELETE FROM search_history WHERE user_id = ? AND kind = 'station' AND station_id = ?",
                (user_id, entry["station_id"]),
            )
        else:
            conn.execute(
                "DELETE FROM search_history WHERE user_id = ? AND kind = ? AND lower(query) = lower(?)",
                (user_id, entry["kind"], entry["query"]),
            )
        cur = conn.execute(
            "INSERT INTO search_history (user_id, kind, query, station_id, lat, lng, battery_pct) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (user_id, entry["kind"], entry["query"], entry["station_id"], entry["lat"], entry["lng"], entry["battery_pct"]),
        )
        conn.execute(
            "DELETE FROM search_history WHERE user_id = ? AND id NOT IN "
            "(SELECT id FROM search_history WHERE user_id = ? ORDER BY id DESC LIMIT ?)",
            (user_id, user_id, config.HISTORY_MAX),
        )
        row = conn.execute("SELECT * FROM search_history WHERE id = ?", (cur.lastrowid,)).fetchone()
    return _public(row)


def recent(user_id: int, limit: int = 20) -> list[dict]:
    """Newest first."""
    with _db() as conn:
        rows = conn.execute(
            "SELECT * FROM search_history WHERE user_id = ? ORDER BY id DESC LIMIT ?",
            (user_id, max(1, min(limit, config.HISTORY_MAX))),
        ).fetchall()
    return [_public(r) for r in rows]


def delete(user_id: int, entry_id: int) -> bool:
    """Remove one entry; False if it doesn't exist or belongs to someone else."""
    with _db() as conn:
        cur = conn.execute("DELETE FROM search_history WHERE id = ? AND user_id = ?", (entry_id, user_id))
    return cur.rowcount > 0


def clear(user_id: int) -> int:
    """Remove all of a user's entries; returns how many were removed."""
    with _db() as conn:
        cur = conn.execute("DELETE FROM search_history WHERE user_id = ?", (user_id,))
    return cur.rowcount
