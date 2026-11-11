"""
SUMO simulation + AI/Algorithm charging-station ranking (Calculation_Model).

Scoring: distance, POI, predicted wait (Model A/B), cost — see AI/README.md.
"""
from __future__ import annotations

import os
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

# ── SUMO / TraCI ─────────────────────────────────────────────────────────────
sumo_path = r"C:\Program Files (x86)\Eclipse\Sumo"
os.environ["SUMO_HOME"] = sumo_path
sys.path.append(os.path.join(sumo_path, "tools"))

import traci  # noqa: E402

# ── Algorithm stack (AI/Algorithm) ───────────────────────────────────────────
_SIM_DIR = Path(__file__).resolve().parent
_AI_DIR = _SIM_DIR.parent / "AI"
_ALGO_DIR = _AI_DIR / "Algorithm"

try:
    from dotenv import load_dotenv

    load_dotenv(_AI_DIR / ".env")
    load_dotenv(_SIM_DIR.parent / ".env")
except ImportError:
    pass
if str(_ALGO_DIR) not in sys.path:
    sys.path.insert(0, str(_ALGO_DIR))

from config import GOOGLE_MAPS_API_KEY, PALO_ALTO_CENTER  # noqa: E402
from logic import (  # noqa: E402
    Calculation_Model,
    EVBatteryState,
    _haversine_metres,
    build_palo_alto_station_dataset,
    describe_ev_range,
)

# ── Thresholds ─────────────────────────────────────────────────────────────────
LOW_BATTERY_WH = 12_000
DEFAULT_MAX_STATIONS = 10


def estimate_taiwan_wait_seconds(
    row,
    *,
    at_time: datetime | None = None,
) -> float:
    """Heuristic queue wait (seconds) when ML is unavailable or predicts zero."""
    at_time = at_time or datetime.now()
    hour = at_time.hour
    if 8 <= hour <= 10 or 17 <= hour <= 19:
        base = 720.0
    elif 11 <= hour <= 16:
        base = 480.0
    else:
        base = 240.0
    mac = str(row.get("MAC Address", row.get("mac", "")))
    jitter = (hash(mac) % 120) - 60
    return max(90.0, base + jitter)


def apply_wait_times(
    stations,
    model: Calculation_Model,
    *,
    at_time: datetime | None = None,
):
    """ML wait times with Taiwan heuristic floor so ranking uses realistic queues."""
    at_time = at_time or datetime.now()
    out = stations.copy()
    waits: list[float] = []
    ml_ok = False
    for _, row in out.iterrows():
        wait = estimate_taiwan_wait_seconds(row, at_time=at_time)
        try:
            ml_wait = float(
                model.predict_waiting_time(
                    row.to_dict(), at_time=at_time, return_minutes=False
                )
            )
            wait = max(ml_wait, wait * 0.4)
            ml_ok = True
        except Exception:
            pass
        waits.append(wait)
    out["waiting_time"] = waits
    if ml_ok:
        print("(Wait-time: ML + Taiwan heuristic floor)")
    else:
        print("(Wait-time: Taiwan heuristic — ML models skipped)")
    return out


def get_current_ev_status(
    xml_file: str | Path,
    *,
    vehicle_id: str = "MCU_EV_TEST_01",
) -> dict | None:
    """Last timestep for ``vehicle_id`` from SUMO ``battery-output`` XML."""
    xml_file = Path(xml_file)
    if not xml_file.is_file():
        return None
    try:
        root = ET.parse(xml_file).getroot()
        timesteps = root.findall(".//timestep")
        if not timesteps:
            return None

        vehicle = None
        for ts in reversed(timesteps):
            for v in ts.findall("vehicle"):
                if v.get("id") == vehicle_id:
                    vehicle = v
                    break
            if vehicle is not None:
                break
        if vehicle is None:
            return None

        attrs = dict(vehicle.attrib)
        charge = attrs.get("device.battery.chargeLevel") or attrs.get("actualBatteryCapacity")
        if charge is None:
            return None

        return {
            "vehicle_id": vehicle_id,
            "remaining_battery": float(charge),
            "x": float(attrs["x"]) if attrs.get("x") else None,
            "y": float(attrs["y"]) if attrs.get("y") else None,
            "sumo_attrs": attrs,
        }
    except Exception as exc:
        print(f"Error reading battery log: {exc}")
        return None


def build_ev_battery_state(
    ev_status: dict | None,
    *,
    distance_travelled_m: float | None = None,
) -> EVBatteryState | None:
    """Normalize SUMO export / TraCI dict into ``EVBatteryState`` for range logic."""
    if not ev_status:
        return None
    if "sumo_attrs" in ev_status:
        return EVBatteryState.from_sumo_export(
            ev_status["sumo_attrs"],
            distance_travelled_m=distance_travelled_m,
        )
    return EVBatteryState(
        remaining_wh=float(ev_status["remaining_battery"]),
        distance_travelled_m=distance_travelled_m,
        total_energy_consumed_wh=ev_status.get("total_energy_consumed_wh"),
        total_energy_regenerated_wh=ev_status.get("total_energy_regenerated_wh"),
        avg_speed_mps=ev_status.get("avg_speed_mps"),
        maximum_wh=float(ev_status.get("maximum_wh", 60_000)),
        stopping_threshold_wh=float(ev_status.get("stopping_threshold_wh", 0.1)),
    )


def sumo_xy_to_latlon(x: float, y: float, net_file: Path) -> tuple[float, float]:
    """Convert SUMO network coordinates to WGS84 (lat, lon)."""
    import sumolib

    net = sumolib.net.readNet(str(net_file))
    lon, lat = net.convertXY2LonLat(x, y)
    return float(lat), float(lon)


def resolve_user_location(
    ev_status: dict | None,
    *,
    net_file: Path,
) -> tuple[float, float]:
    if ev_status and ev_status.get("x") is not None and ev_status.get("y") is not None:
        try:
            return sumo_xy_to_latlon(ev_status["x"], ev_status["y"], net_file)
        except Exception as exc:
            print(f"Could not map SUMO position to lat/lon: {exc}")
    return PALO_ALTO_CENTER


def run_sumo_simulation(steps: int = 50) -> None:
    sumo_binary = os.path.join(sumo_path, "bin", "sumo-gui.exe")
    cfg = _SIM_DIR / "simulation.sumocfg"
    print(f"Launching SUMO: {sumo_binary}")
    traci.start([sumo_binary, "-c", str(cfg)])
    for _ in range(steps):
        traci.simulationStep()
    traci.close()
    print("Simulation complete. Battery log updated.\n")


def apply_offline_proxies(model: Calculation_Model, stations_df):
    """Haversine distance + zero POI when Google APIs are unavailable."""
    user_lat, user_lon = model.user_location

    out = stations_df.copy()
    out["distance"] = out.apply(
        lambda r: _haversine_metres(user_lat, user_lon, float(r["lat"]), float(r["lon"])) * 1.35,
        axis=1,
    )
    out["poi_sum"] = 0.0
    out["poi_nearby"] = [[] for _ in range(len(out))]
    out["poi_count"] = 0
    print("(Offline mode: straight-line distance, POI skipped — set GOOGLE_MAPS_API_KEY in .env)")
    return out


def rank_stations_algorithm(
    user_location: tuple[float, float],
    *,
    max_stations: int = DEFAULT_MAX_STATIONS,
    use_google: bool | None = None,
    ev_battery: EVBatteryState | None = None,
) -> "pd.DataFrame":
    import pandas as pd

    if use_google is None:
        use_google = bool(GOOGLE_MAPS_API_KEY)

    if ev_battery is not None:
        print("EV range estimate:", describe_ev_range(ev_battery))

    stations = build_palo_alto_station_dataset(
        user_location,
        max_stations=max_stations,
        at_time=datetime.now(),
        ev_battery=ev_battery,
    )
    model = Calculation_Model(user_location)

    if use_google:
        stations = model.process_distances(stations)
        stations = model.process_all_stations(stations)
    else:
        stations = apply_offline_proxies(model, stations)

    try:
        stations = apply_wait_times(stations, model)
    except Exception as exc:
        print(f"(Wait-time fallback: {exc}; using heuristic only)")
        stations = stations.copy()
        stations["waiting_time"] = stations.apply(
            lambda r: estimate_taiwan_wait_seconds(r), axis=1
        )

    ranked = model.total_score(
        stations,
        include_llm_context=bool(os.getenv("GEMINI_API_KEY")),
    )
    return ranked


def print_recommendations(ranked_df, top_n: int = 5) -> None:
    cols = [
        "Station Name",
        "Address 1",
        "distance",
        "poi_sum",
        "waiting_time",
        "cost",
        "total_score",
    ]
    show = [c for c in cols if c in ranked_df.columns]
    print("\n--- Top charging stations (Algorithm total_score) ---")
    print(ranked_df[show].head(top_n).to_string(index=False))
    print("-" * 55)
    print("Weights: distance 25% | POI 25% | wait 25% | cost 25% (see AI/README.md)")


def maybe_run_llm(ranked_df) -> None:
    if not os.getenv("GEMINI_API_KEY") or "llm_context" not in ranked_df.columns:
        return
    try:
        from llm import print_reflection_report, run_reflection_pipeline

        top_context = ranked_df.iloc[0]["llm_context"]
        alternatives = ranked_df.iloc[1:4]["llm_context"].tolist()
        reflection = run_reflection_pipeline(
            {"recommended": top_context, "alternatives": alternatives}
        )
        print("\n--- Gemini explanation ---")
        print_reflection_report(reflection)
    except Exception as exc:
        print(f"(LLM skipped: {exc})")


def main() -> None:
    """Run SUMO with live TraCI + Algorithm (default). Use --offline-only for post-sim CSV only."""
    import argparse

    parser = argparse.ArgumentParser(description="SUMO + Algorithm charging recommendations")
    parser.add_argument(
        "--offline-only",
        action="store_true",
        help="Skip TraCI; rank from last battery log only",
    )
    parser.add_argument("--headless", action="store_true", help="Use sumo instead of sumo-gui")
    parser.add_argument(
        "--max-steps",
        type=int,
        default=None,
        help="Stop TraCI loop after N steps (default: run until no vehicles left)",
    )
    parser.add_argument("--google", action="store_true", help="Use Google APIs during simulation (slower)")
    args = parser.parse_args()

    if not args.offline_only:
        from sumo_algorithm_traci import run_integrated_simulation

        run_integrated_simulation(
            use_gui=not args.headless,
            max_steps=args.max_steps,
            use_google_apis=args.google,
        )
        return

    sumo_log = _SIM_DIR / "output" / "battery_log.xml"
    if not sumo_log.is_file():
        sumo_log = _SIM_DIR / "user_data_log.xml"
    net_file = _SIM_DIR / "taipei.net.xml"
    print("--- Offline ranking from battery log ---\n")

    ev_status = get_current_ev_status(sumo_log)
    if not ev_status:
        ev_status = {
            "vehicle_id": "MCU_EV_TEST_01",
            "remaining_battery": 5000.0,
            "x": None,
            "y": None,
        }

    user_loc = resolve_user_location(ev_status, net_file=net_file)
    ev_battery = build_ev_battery_state(ev_status)
    if ev_battery and ev_status["remaining_battery"] >= LOW_BATTERY_WH:
        print("Battery sufficient. No recommendation needed.")
        print("Headroom:", describe_ev_range(ev_battery))
        return

    ranked = rank_stations_algorithm(
        user_loc,
        max_stations=DEFAULT_MAX_STATIONS,
        ev_battery=ev_battery,
    )
    print_recommendations(ranked)
    ranked.to_csv(_ALGO_DIR / "final_recommendations_summary.csv", index=False)
    maybe_run_llm(ranked)


if __name__ == "__main__":
    main()
