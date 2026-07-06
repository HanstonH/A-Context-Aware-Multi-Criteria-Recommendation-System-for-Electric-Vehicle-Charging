"""Merge raw JSON archives into Parquet for the recommender."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from .paths import (
    live_daily_parquet,
    live_processed_latest,
    live_slot_dir,
    snapshot_at_from_slot,
    static_processed_master,
    static_raw_path,
)
from .tdx import TDX_CITIES

_CONNECTOR_AVAILABLE = 1
_RATE_FREE = 1
_RATE_PER_KWH = 2


def _unwrap(body: Any, array_key: str) -> list[dict[str, Any]]:
    if isinstance(body, dict):
        return body.get(array_key, []) or []
    if isinstance(body, list):
        return body
    return []


def _load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def _latest_static_date(endpoint: str, city: str) -> str | None:
    folder = static_raw_path(endpoint, city, "placeholder").parent
    if not folder.is_dir():
        return None
    dates = sorted(p.stem for p in folder.glob("*.json"))
    return dates[-1] if dates else None


def _station_cost_from_rates(rate_records: list[dict[str, Any]]) -> pd.DataFrame:
    rows: list[tuple[Any, float, bool]] = []
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
    preferred = rates_df[rates_df["preferred"]].groupby("StationID")["price"].median()
    fallback = rates_df.groupby("StationID")["price"].median()
    return preferred.combine_first(fallback).rename("cost").reset_index()


def _parking_cost_from_rates(rate_records: list[dict[str, Any]]) -> pd.DataFrame:
    """Median parking price per station (same collapse logic as charging)."""
    return _station_cost_from_rates(rate_records).rename(columns={"cost": "parking_cost"})


def merge_static_master(date_str: str | None = None) -> pd.DataFrame:
    """Build stations_master.parquet from archived static JSON."""
    frames: list[pd.DataFrame] = []

    for city in TDX_CITIES:
        station_date = date_str or _latest_static_date("stations", city)
        if not station_date:
            continue

        station_path = static_raw_path("stations", city, station_date)
        if not station_path.is_file():
            continue

        stations_body = _load_json(station_path)
        stations = _unwrap(stations_body, "Stations")
        if not stations:
            continue

        df = pd.DataFrame(
            {
                "StationID": [s.get("StationID") for s in stations],
                "station_name": [
                    (s.get("StationName") or {}).get("Zh_tw") for s in stations
                ],
                "lat": [s.get("PositionLat") for s in stations],
                "lon": [s.get("PositionLon") for s in stations],
                "spaces": [s.get("Spaces") for s in stations],
                "charging_points": [s.get("ChargingPoints") for s in stations],
                "city": city,
                "static_fetched_at": station_date,
            }
        )
        df = df.dropna(subset=["StationID", "lat", "lon"]).drop_duplicates("StationID")

        charge_date = date_str or _latest_static_date("charging_rates", city)
        if charge_date:
            charge_path = static_raw_path("charging_rates", city, charge_date)
            if charge_path.is_file():
                charge_body = _load_json(charge_path)
                rates = _unwrap(charge_body, "ChargingRates")
                cost_table = _station_cost_from_rates(rates)
                df = df.merge(cost_table, on="StationID", how="left")
                median_cost = df["cost"].median()
                df["cost"] = df["cost"].fillna(
                    0.0 if pd.isna(median_cost) else median_cost
                )

        parking_date = date_str or _latest_static_date("parking_rates", city)
        if parking_date:
            parking_path = static_raw_path("parking_rates", city, parking_date)
            if parking_path.is_file():
                parking_body = _load_json(parking_path)
                parking_rates = _unwrap(parking_body, "ParkingRates")
                parking_table = _parking_cost_from_rates(parking_rates)
                df = df.merge(parking_table, on="StationID", how="left")
                median_parking = df["parking_cost"].median()
                df["parking_cost"] = df["parking_cost"].fillna(
                    0.0 if pd.isna(median_parking) else median_parking
                )

        frames.append(df)

    if not frames:
        raise FileNotFoundError(
            "No static JSON files found. Run `python -m extraction static` first."
        )

    master = pd.concat(frames, ignore_index=True)
    out = static_processed_master()
    out.parent.mkdir(parents=True, exist_ok=True)
    master.to_parquet(out, index=False)

    return master


def _live_rows_from_body(
    body: Any, *, city: str, snapshot_at: str
) -> list[dict[str, Any]]:
    live = _unwrap(body, "LiveStatuses")
    if not live:
        return []

    live_df = pd.DataFrame(live)
    if live_df.empty or "StationID" not in live_df.columns:
        return []

    grouped = live_df.groupby("StationID")["ConnectorStatus"].agg(
        available_points=lambda s: int((s == _CONNECTOR_AVAILABLE).sum()),
        total_connectors="size",
    )
    rows = grouped.reset_index().to_dict(orient="records")
    for row in rows:
        row["city"] = city
        row["snapshot_at"] = snapshot_at
    return rows


def merge_live_from_slot(date_str: str, slot_str: str) -> pd.DataFrame:
    """Aggregate one time-slot folder into latest.parquet and append daily rollup."""
    slot_dir = live_slot_dir(date_str, slot_str)
    if not slot_dir.is_dir():
        raise FileNotFoundError(f"Live slot folder not found: {slot_dir}")

    snapshot_at = snapshot_at_from_slot(date_str, slot_str)
    all_rows: list[dict[str, Any]] = []

    for city in TDX_CITIES:
        path = slot_dir / f"{city}.json"
        if not path.is_file():
            continue
        body = _load_json(path)
        all_rows.extend(_live_rows_from_body(body, city=city, snapshot_at=snapshot_at))

    if not all_rows:
        raise FileNotFoundError(f"No live city JSON in {slot_dir}")

    df = pd.DataFrame(all_rows)
    latest_path = live_processed_latest()
    latest_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(latest_path, index=False)

    daily_path = live_daily_parquet(date_str)
    if daily_path.is_file():
        existing = pd.read_parquet(daily_path)
        combined = pd.concat([existing, df], ignore_index=True)
        combined = combined.drop_duplicates(
            subset=["StationID", "snapshot_at"], keep="last"
        )
        combined.to_parquet(daily_path, index=False)
    else:
        df.to_parquet(daily_path, index=False)

    return df


def merge_live_from_hour(date_str: str, slot_str: str) -> pd.DataFrame:
    """Deprecated alias; use merge_live_from_slot."""
    return merge_live_from_slot(date_str, slot_str)


def iter_live_slot_dirs() -> Iterable[tuple[str, str]]:
    """Yield (date_str, slot_str) for every archived live slot folder."""
    root = live_slot_dir("placeholder", "00-00").parent.parent
    if not root.is_dir():
        return
    for date_dir in sorted(root.iterdir()):
        if not date_dir.is_dir():
            continue
        for slot_dir in sorted(date_dir.iterdir()):
            if slot_dir.is_dir() and slot_dir.name.startswith("hour-"):
                yield date_dir.name, slot_dir.name.replace("hour-", "")


def iter_live_hour_dirs() -> Iterable[tuple[str, str]]:
    """Deprecated alias; use iter_live_slot_dirs."""
    yield from iter_live_slot_dirs()
