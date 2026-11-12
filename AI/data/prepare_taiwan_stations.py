"""Build taiwan_ev_stations.csv and unit_price CSV from chargers.geojson."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent
GEOJSON = DATA_DIR / "chargers.geojson"
STATIONS_OUT = DATA_DIR / "taiwan_ev_stations.csv"
PRICES_OUT = DATA_DIR / "unit_price_by_station_taiwan.csv"

# Taipei + 板橋 — matches SUMO map bbox
REGION_BOUNDS = {
    "lat_min": 24.98,
    "lat_max": 25.08,
    "lon_min": 121.48,
    "lon_max": 121.60,
}
DEFAULT_PLUG = "J1772"
DEFAULT_PRICE_NTD_PER_KWH = 8.5

# Scooter swap / non-car chargers to drop from the car-only dataset
_EXCLUDE_TEXT = (
    "gogoro",
    "go station",
    "gostation",
    "換電",
    "換電站",
    "battery_swap",
    "ionex",
    "光陽機車",
    "光陽",
    "睿能",
    "手機充電",
    "無線上網",
    "scooter batteries",
)

_CAR_TEXT = (
    "tesla",
    "supercharger",
    "u-power",
    "bmw",
    "yes!來電",
    "超級充電",
    "直流高速充電",
)


def _text_blob(props: dict, name: str) -> str:
    keys = ("name", "brand", "operator", "network", "description", "name:zh", "name:en")
    parts = [name] + [str(props.get(k, "")) for k in keys]
    return " ".join(parts).lower()


def _is_car_charger(props: dict, name: str) -> bool:
    """Keep passenger EV chargers; drop Gogoro swap / scooter-only / phone charging."""
    blob = _text_blob(props, name)

    if props.get("motorcar") == "no":
        return False
    if props.get("scooter") == "only":
        return False
    if props.get("charging") == "battery_swap":
        return False
    if props.get("moped") == "yes" and props.get("motorcar") != "yes":
        return False

    for kw in _EXCLUDE_TEXT:
        if kw in blob:
            return False

    if props.get("motorcar") == "yes":
        return True

    for kw in _CAR_TEXT:
        if kw in blob:
            return True

    if props.get("network") in ("BMW", "Tesla", "U-POWER") or props.get("operator") in (
        "BMW",
        "Tesla, Inc.",
        "Tesla",
        "U-POWER",
    ):
        return True

    # Unnamed OSM points with no scooter operator — treat as generic car charger
    operator = str(props.get("operator", "")).lower()
    if operator in ("gogoro", "gogoro taiwan", "gogoro inc.", "睿能創意股份有限公司"):
        return False

    has_label = bool(props.get("name") or props.get("brand"))
    if not has_label and props.get("amenity") == "charging_station":
        return True

    if name.startswith("充電站 ") and "gogoro" not in blob:
        return True

    return False


def _in_bounds(lat: float, lon: float) -> bool:
    b = REGION_BOUNDS
    return b["lat_min"] <= lat <= b["lat_max"] and b["lon_min"] <= lon <= b["lon_max"]


def _mac_for(lon: float, lat: float, idx: int) -> str:
    digest = hashlib.md5(f"{lon:.6f},{lat:.6f},{idx}".encode()).hexdigest()[:12].upper()
    return f"TW{digest}"


def main() -> None:
    raw = json.loads(GEOJSON.read_text(encoding="utf-8"))
    rows: list[dict] = []
    skipped = 0
    for idx, feat in enumerate(raw.get("features", [])):
        geom = feat.get("geometry") or {}
        if geom.get("type") != "Point":
            continue
        lon, lat = geom["coordinates"][:2]
        if not _in_bounds(float(lat), float(lon)):
            continue
        props = feat.get("properties") or {}
        name = props.get("name") or props.get("brand") or f"充電站 {idx}"
        if not _is_car_charger(props, str(name)):
            skipped += 1
            continue
        city = props.get("addr:city", "")
        operator = props.get("operator", "") or props.get("network", "")
        address = " ".join(p for p in (city, operator) if p).strip()
        rows.append(
            {
                "Station Name": str(name)[:120],
                "MAC Address": _mac_for(float(lon), float(lat), idx),
                "Latitude": float(lat),
                "Longitude": float(lon),
                "Plug Type": DEFAULT_PLUG,
                "Address 1": address or "Taiwan",
            }
        )

    if not rows:
        raise SystemExit("No car charging stations in region — check filters or REGION_BOUNDS.")

    stations = pd.DataFrame(rows).drop_duplicates(subset=["MAC Address"], keep="first")
    stations.to_csv(STATIONS_OUT, index=False, encoding="utf-8-sig")

    prices = stations[["Station Name"]].copy()
    prices["median_unit_price_per_kwh"] = DEFAULT_PRICE_NTD_PER_KWH
    prices["price_tier"] = 1.0
    prices.to_csv(PRICES_OUT, index=False, encoding="utf-8-sig")

    print(f"Wrote {len(stations)} car stations -> {STATIONS_OUT} (skipped {skipped} non-car)")
    print(f"Wrote unit prices -> {PRICES_OUT}")


if __name__ == "__main__":
    main()
