"""
TraCI bridge: run SUMO simulation with live Algorithm recommendations.

- Shows charging stations on the map (charging_stations.add.xml)
- Monitors EV battery each step
- On low battery: ranks stations (Calculation_Model) and reroutes vehicle to the best one
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

_SIM_DIR = Path(__file__).resolve().parent
_AI_DIR = _SIM_DIR.parent / "AI"
_ALGO_DIR = _AI_DIR / "Algorithm"

sumo_path = os.environ.get(
    "SUMO_HOME",
    r"C:\Users\USER\Downloads\sumo-win64extra-1.26.0\sumo-1.26.0",
)
os.environ["SUMO_HOME"] = sumo_path
sys.path.insert(0, os.path.join(sumo_path, "tools"))

import traci  # noqa: E402

try:
    from dotenv import load_dotenv

    load_dotenv(_AI_DIR / ".env")
    load_dotenv(_SIM_DIR.parent / ".env")
except ImportError:
    pass

if str(_ALGO_DIR) not in sys.path:
    sys.path.insert(0, str(_ALGO_DIR))

import sumolib  # noqa: E402

MONITORED_VEHICLE = "MCU_EV_TEST_01"
LOW_BATTERY_WH = 12_000
DEFAULT_MAX_STATIONS = 10
CHECK_EVERY_STEPS = 10
NET_FILE = _SIM_DIR / "paloalto.net.xml"
CFG_FILE = _SIM_DIR / "simulation.sumocfg"
CHARGING_ADD = _SIM_DIR / "charging_stations.add.xml"
RECOMMENDED_POI_COLOR = (255, 80, 0, 255)
DEFAULT_POI_COLOR = (0, 160, 0, 255)
GUI_UPDATE_EVERY_STEPS = 5
GUI_MESSAGE_EVERY_STEPS = 50


_net: sumolib.net.Net | None = None


def get_net() -> sumolib.net.Net:
    global _net
    if _net is None:
        _net = sumolib.net.readNet(str(NET_FILE))
    return _net


def get_vehicle_max_battery_wh(veh_id: str) -> float:
    try:
        return float(
            traci.vehicle.getParameter(veh_id, "device.battery.maximumBatteryCapacity")
        )
    except traci.TraCIException:
        return 60_000.0


def get_vehicle_battery_wh(veh_id: str) -> float | None:
    for key in (
        "device.battery.actualBatteryCapacity",
        "device.battery.chargeLevel",
    ):
        try:
            return float(traci.vehicle.getParameter(veh_id, key))
        except traci.TraCIException:
            continue
    return None


def vehicle_latlon(veh_id: str) -> tuple[float, float]:
    pos = traci.vehicle.getPosition(veh_id)
    net = get_net()
    lon, lat = net.convertXY2LonLat(pos[0], pos[1])
    return float(lat), float(lon)


def latlon_to_xy(lat: float, lon: float) -> tuple[float, float]:
    net = get_net()
    x, y = net.convertLonLat2XY(lon, lat)
    return float(x), float(y)


def nearest_edge_id(lat: float, lon: float, radius: float = 400.0) -> str | None:
    net = get_net()
    x, y = net.convertLonLat2XY(lon, lat)
    neighbors = net.getNeighboringEdges(x, y, radius)
    if not neighbors:
        return None
    edge, _dist = min(neighbors, key=lambda item: item[1])
    return edge.getID()


def highlight_station_poi(station_row, color=RECOMMENDED_POI_COLOR) -> None:
    """Try to highlight a charging POI near the station coordinates."""
    lat, lon = float(station_row["lat"]), float(station_row["lon"])
    x, y = latlon_to_xy(lat, lon)
    best_id = None
    best_d = 1e18
    for poi_id in traci.poi.getIDList():
        if not poi_id.startswith("chg_"):
            continue
        px, py = traci.poi.getPosition(poi_id)
        d = (px - x) ** 2 + (py - y) ** 2
        if d < best_d:
            best_d = d
            best_id = poi_id
    if best_id and best_d < 500**2:
        traci.poi.setColor(best_id, color)
        traci.poi.setParameter(best_id, "recommended", "true")


def route_vehicle_to_station(veh_id: str, station_row) -> bool:
    lat, lon = float(station_row["lat"]), float(station_row["lon"])
    to_edge = nearest_edge_id(lat, lon)
    if not to_edge:
        print(f"  Could not find road edge near station {station_row.get('Station Name')}")
        return False

    try:
        from_edge = traci.vehicle.getRoadID(veh_id)
        if from_edge.startswith(":"):
            from_edge = traci.vehicle.getRoute(veh_id)[0]
        route = traci.simulation.findRoute(from_edge, to_edge)
        if not route.edges:
            return False
        traci.vehicle.setRoute(veh_id, list(route.edges))
        try:
            traci.vehicle.setParameter(
                veh_id, "recommended_station", str(station_row.get("Station Name", ""))
            )
        except traci.TraCIException:
            pass
        return True
    except traci.TraCIException as exc:
        print(f"  Route change failed: {exc}")
        return False


def build_live_ev_battery(veh_id: str, remaining_wh: float, tracker) -> "EVBatteryState":
    """Build ``EVBatteryState`` with optional rolling Wh/km from recent driving."""
    from logic import EVBatteryState

    dist_m, _net_wh, rolling_wh_km = tracker.rolling_stats()
    state = EVBatteryState(
        remaining_wh=remaining_wh,
        maximum_wh=get_vehicle_max_battery_wh(veh_id),
    )
    try:
        state.total_energy_consumed_wh = float(
            traci.vehicle.getParameter(veh_id, "device.battery.totalEnergyConsumed")
        )
        state.total_energy_regenerated_wh = float(
            traci.vehicle.getParameter(veh_id, "device.battery.totalEnergyRegenerated")
        )
    except traci.TraCIException:
        pass
    if rolling_wh_km is not None and rolling_wh_km > 0:
        state.wh_per_metre = rolling_wh_km / 1000.0
        state.distance_travelled_m = dist_m
    return state


def refresh_sumo_gui_ev_overlay(
    veh_id: str,
    tracker,
    *,
    write_message: bool = False,
    recommended_station: str | None = None,
) -> None:
    from logic import describe_ev_range
    from sumo_ev_display import update_sumo_vehicle_display

    battery = get_vehicle_battery_wh(veh_id)
    if battery is None:
        return
    state = build_live_ev_battery(veh_id, battery, tracker)
    _dist, _net, rolling_km = tracker.rolling_stats()
    update_sumo_vehicle_display(
        veh_id,
        state,
        describe_ev_range(state),
        rolling_wh_per_km=rolling_km,
        recommended_station=recommended_station,
        write_message=write_message,
    )


def ensure_charging_stations_xml() -> None:
    if CHARGING_ADD.is_file():
        return
    print("Generating charging_stations.add.xml (first run)...")
    from generate_charging_stations import main as gen_main

    gen_main()


def run_integrated_simulation(
    *,
    use_gui: bool = True,
    max_steps: int | None = None,
    reroute_on_low_battery: bool = True,
    use_google_apis: bool | None = None,
) -> None:
    """
    Start SUMO under TraCI control and apply Algorithm when battery is low.

    Parameters
    ----------
    use_gui : bool
        If True, opens sumo-gui; otherwise headless sumo.
    max_steps : int, optional
        Stop after this many steps (default: until simulation end).
    reroute_on_low_battery : bool
        If True, send MONITORED_VEHICLE to the top-ranked station.
    use_google_apis : bool, optional
        Pass to rank_stations_algorithm (default: offline in-loop for speed).
    """
    ensure_charging_stations_xml()

    sumo_bin = "sumo-gui" if use_gui else "sumo"
    sumo_exe = os.path.join(sumo_path, "bin", f"{sumo_bin}.exe")

    # Do NOT use --quit-on-end: otherwise SUMO-GUI vanishes when the sim finishes.
    cfg_args = [sumo_exe, "-c", str(CFG_FILE), "--delay", "80"]

    print("--- SUMO + Algorithm (TraCI integrated) ---")
    print(f"Binary: {sumo_exe}")
    print(f"Monitor vehicle: {MONITORED_VEHICLE} | Low battery: < {LOW_BATTERY_WH} Wh")
    if use_gui:
        print("Tip: Press Play in SUMO if the sim is paused; GUI stays open when Python exits.\n")
    else:
        print()

    from sumo_ev_display import RollingEnergyTracker, setup_sumo_gui_tracking

    traci.start(cfg_args)
    recommended_once = False
    recommended_station_name: str | None = None
    step = 0
    tracker = RollingEnergyTracker()
    tracked_camera = False

    if use_gui:
        print(
            "GUI: EV label shows SoC, max range (km), Wh/km, and rolling Wh/km when calibrated.\n"
            "     Enable vehicle names in SUMO: View → Show vehicle names/subline.\n"
        )

    try:
        while traci.simulation.getMinExpectedNumber() > 0:
            traci.simulationStep()
            step += 1

            if max_steps is not None and step >= max_steps:
                break

            if MONITORED_VEHICLE not in traci.vehicle.getIDList():
                continue

            if use_gui and not tracked_camera:
                setup_sumo_gui_tracking(MONITORED_VEHICLE)
                tracked_camera = True

            try:
                tracker.sample(MONITORED_VEHICLE)
            except traci.TraCIException:
                pass

            if use_gui and step % GUI_UPDATE_EVERY_STEPS == 0:
                refresh_sumo_gui_ev_overlay(
                    MONITORED_VEHICLE,
                    tracker,
                    write_message=(step % GUI_MESSAGE_EVERY_STEPS == 0),
                    recommended_station=recommended_station_name,
                )

            if step % CHECK_EVERY_STEPS != 0:
                continue

            battery = get_vehicle_battery_wh(MONITORED_VEHICLE)
            if battery is None:
                continue

            lat, lon = vehicle_latlon(MONITORED_VEHICLE)
            ev_battery = build_live_ev_battery(MONITORED_VEHICLE, battery, tracker)
            from logic import describe_ev_range

            ri = describe_ev_range(ev_battery)
            _d, _n, roll = tracker.rolling_stats()
            roll_s = f" rolling={roll:.0f} Wh/km" if roll else ""
            print(
                f"[t={traci.simulation.getTime():.0f}s] {MONITORED_VEHICLE} "
                f"SoC={ri['soc_percent']:.1f}% range~{ri['max_drivable_km']:.1f}km "
                f"({ri['wh_per_km']:.0f} Wh/km{roll_s}) pos=({lat:.4f}, {lon:.4f})"
            )

            if battery >= LOW_BATTERY_WH:
                continue

            if recommended_once:
                continue

            from recommend import print_recommendations, rank_stations_algorithm

            print("\n*** LOW BATTERY — running Algorithm ranking ***")
            ranked = rank_stations_algorithm(
                (lat, lon),
                max_stations=DEFAULT_MAX_STATIONS,
                use_google=use_google_apis if use_google_apis is not None else False,
                ev_battery=ev_battery,
            )
            print_recommendations(ranked, top_n=5)

            top = ranked.iloc[0]
            recommended_station_name = str(top.get("Station Name", ""))
            highlight_station_poi(top)
            if use_gui:
                refresh_sumo_gui_ev_overlay(
                    MONITORED_VEHICLE,
                    tracker,
                    write_message=True,
                    recommended_station=recommended_station_name,
                )
            if reroute_on_low_battery:
                ok = route_vehicle_to_station(MONITORED_VEHICLE, top)
                if ok:
                    print(f"\n>>> Rerouted {MONITORED_VEHICLE} toward: {top['Station Name']}")
                    print(f"    {top.get('Address 1', '')}\n")
                else:
                    print(
                        f"\n>>> Could not auto-reroute (see map: green POI = chargers, "
                        f"orange vehicle = {MONITORED_VEHICLE}).\n"
                    )

            out_csv = _ALGO_DIR / "final_recommendations_summary.csv"
            export_cols = [c for c in ranked.columns if c not in ("poi_nearby", "llm_context")]
            ranked[export_cols].to_csv(out_csv, index=False)
            print(f"Saved rankings: {out_csv}\n")
            recommended_once = True

    finally:
        if use_gui:
            # Keep SUMO-GUI open until the user closes the window (avoids instant disappear).
            traci.close(wait=True)
            print("SUMO closed by user.")
        else:
            traci.close()
            print("Simulation ended.")


if __name__ == "__main__":
    run_integrated_simulation(use_gui=True)
