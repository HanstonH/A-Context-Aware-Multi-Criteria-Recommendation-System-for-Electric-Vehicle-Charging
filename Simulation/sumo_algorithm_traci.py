"""
TraCI bridge: SUMO simulation with EV battery, charging, and Algorithm recommendations.
"""
from __future__ import annotations

import json
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

from sim_config import MAX_DRAIN_AFTER_END_S, SIM_END_S, TRIP_PERIOD_S

MONITORED_VEHICLE = "MCU_EV_TEST_01"
LOW_BATTERY_WH = 12_000
CHARGE_TARGET_WH = 24_000  # resume driving at ~40% SoC
CHARGE_STOP_DURATION_S = 7_200
DEFAULT_MAX_STATIONS = 10
CHECK_EVERY_STEPS = 10
NET_FILE = _SIM_DIR / "taipei.net.xml"
CFG_FILE = _SIM_DIR / "simulation.sumocfg"
CHARGING_ADD = _SIM_DIR / "charging_stations.add.xml"
CHARGING_MANIFEST = _SIM_DIR / "charging_station_manifest.json"
RECOMMENDED_POI_COLOR = (255, 80, 0, 255)
GUI_UPDATE_EVERY_STEPS = 5
GUI_MESSAGE_EVERY_STEPS = 20

_net: sumolib.net.Net | None = None
_charging_manifest: dict | None = None


def get_net() -> sumolib.net.Net:
    global _net
    if _net is None:
        _net = sumolib.net.readNet(str(NET_FILE))
    return _net


def load_charging_manifest() -> dict:
    global _charging_manifest
    if _charging_manifest is not None:
        return _charging_manifest
    if CHARGING_MANIFEST.is_file():
        _charging_manifest = json.loads(CHARGING_MANIFEST.read_text(encoding="utf-8"))
    else:
        _charging_manifest = {}
    return _charging_manifest


def get_vehicle_max_battery_wh(veh_id: str) -> float:
    for key in (
        "device.battery.maximumBatteryCapacity",
        "device.battery.capacity",
    ):
        try:
            return float(traci.vehicle.getParameter(veh_id, key))
        except traci.TraCIException:
            continue
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


def is_vehicle_charging(veh_id: str) -> bool:
    try:
        cs = traci.vehicle.getParameter(veh_id, "device.battery.chargingStationId")
        if cs and cs != "NULL":
            return True
    except traci.TraCIException:
        pass
    try:
        return traci.vehicle.isStoppedParking(veh_id)
    except traci.TraCIException:
        return False


def vehicle_latlon(veh_id: str) -> tuple[float, float]:
    pos = traci.vehicle.getPosition(veh_id)
    net = get_net()
    lon, lat = net.convertXY2LonLat(pos[0], pos[1])
    return float(lat), float(lon)


def latlon_to_xy(lat: float, lon: float) -> tuple[float, float]:
    net = get_net()
    x, y = net.convertLonLat2XY(lon, lat)
    return float(x), float(y)


def _mac_from_row(station_row) -> str | None:
    for col in ("MAC Address", "mac", "MAC"):
        if col in station_row.index and station_row.get(col):
            return str(station_row[col]).replace(":", "").replace(" ", "")[:20]
    return None


def resolve_charging_station_id(station_row) -> str | None:
    manifest = load_charging_manifest()
    mac = _mac_from_row(station_row)
    if mac and mac in manifest:
        return manifest[mac]["cs_id"]
    lat, lon = float(station_row["lat"]), float(station_row["lon"])
    x, y = latlon_to_xy(lat, lon)
    best_id = None
    best_d = 1e18
    for cs_id in traci.chargingstation.getIDList():
        lx = traci.chargingstation.getLaneID(cs_id)
        try:
            cx, cy = traci.lane.getShape(lx)[0]
        except traci.TraCIException:
            continue
        d = (cx - x) ** 2 + (cy - y) ** 2
        if d < best_d:
            best_d = d
            best_id = cs_id
    return best_id if best_d < 600**2 else None


def highlight_station_poi(station_row, color=RECOMMENDED_POI_COLOR) -> None:
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
        from sumo_ev_display import highlight_charging_poi

        highlight_charging_poi(best_id, recommended=True)


def route_vehicle_to_charging_station(veh_id: str, station_row) -> bool:
    cs_id = resolve_charging_station_id(station_row)
    if not cs_id:
        print(f"  No SUMO chargingStation near {station_row.get('Station Name')}")
        return False
    if cs_id not in traci.chargingstation.getIDList():
        print(f"  chargingStation {cs_id} not loaded in simulation")
        return False

    try:
        cs_lane = traci.chargingstation.getLaneID(cs_id)
        cs_edge = traci.lane.getEdgeID(cs_lane)
        from_edge = traci.vehicle.getRoadID(veh_id)
        if from_edge.startswith(":"):
            from_edge = traci.lane.getEdgeID(traci.vehicle.getLaneID(veh_id))
        vtype = traci.vehicle.getTypeID(veh_id)
        route = traci.simulation.findRoute(from_edge, cs_edge, vType=vtype)
        if not route.edges:
            print(f"  No SUMO route to {cs_id} from {from_edge}")
            return False

        traci.vehicle.setRoute(veh_id, list(route.edges))
        traci.vehicle.setChargingStationStop(
            veh_id,
            cs_id,
            duration=CHARGE_STOP_DURATION_S,
        )
        print(
            f"  Charging stop queued: {cs_id} ({station_row.get('Station Name')}) "
            f"via {len(route.edges)} edges"
        )
        return True
    except traci.TraCIException as exc:
        print(f"  Charging stop failed: {exc}")
        return False


def is_charger_reachable(veh_id: str, cs_id: str) -> bool:
    """Quick check whether SUMO can route this vehicle to the charger."""
    try:
        cs_lane = traci.chargingstation.getLaneID(cs_id)
        cs_edge = traci.lane.getEdgeID(cs_lane)
        from_edge = traci.vehicle.getRoadID(veh_id)
        if from_edge.startswith(":"):
            from_edge = traci.lane.getEdgeID(traci.vehicle.getLaneID(veh_id))
        route = traci.simulation.findRoute(
            from_edge, cs_edge, vType=traci.vehicle.getTypeID(veh_id)
        )
        return bool(route.edges)
    except traci.TraCIException:
        return False


def maybe_resume_after_charge(veh_id: str, recorder=None) -> bool:
    """Leave the charger when target SoC is reached."""
    battery = get_vehicle_battery_wh(veh_id)
    if battery is None or battery < CHARGE_TARGET_WH:
        return False
    try:
        if traci.vehicle.isStopped(veh_id):
            traci.vehicle.resume(veh_id)
            print(
                f"\n>>> {veh_id} finished charging ({battery:.0f} Wh) — resuming trip.\n"
            )
            if recorder is not None:
                recorder.log_event(
                    "charging_complete",
                    vehicle=veh_id,
                    remaining_wh=battery,
                )
            return True
    except traci.TraCIException:
        pass
    return False


def build_live_ev_battery(veh_id: str, remaining_wh: float, tracker) -> "EVBatteryState":
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
    is_tracked: bool = True,
    charging: bool = False,
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
        is_tracked=is_tracked,
        charging=charging,
    )


def ensure_charging_stations_xml() -> None:
    if CHARGING_ADD.is_file() and CHARGING_MANIFEST.is_file():
        return
    print("Generating charging_stations.add.xml + manifest (first run)...")
    from generate_charging_stations import main as gen_main

    gen_main()


def run_integrated_simulation(
    *,
    use_gui: bool = True,
    max_steps: int | None = None,
    reroute_on_low_battery: bool = True,
    use_google_apis: bool | None = None,
    tracked_vehicle: str = MONITORED_VEHICLE,
    export_telemetry: bool = True,
    telemetry_every: int = 5,
) -> None:
    ensure_charging_stations_xml()
    load_charging_manifest()

    sumo_bin = "sumo-gui" if use_gui else "sumo"
    sumo_exe = os.path.join(sumo_path, "bin", f"{sumo_bin}.exe")
    cfg_args = [sumo_exe, "-c", str(CFG_FILE), "-g", str(_SIM_DIR / "taiwan_gui.settings.xml")]
    if use_gui:
        cfg_args.extend(["--delay", "80"])

    print("--- SUMO Taiwan (TraCI + charging + recommendations) ---")
    est_vehicles = SIM_END_S // TRIP_PERIOD_S
    drain_note = (
        f" + up to {MAX_DRAIN_AFTER_END_S // 60} min drain"
        if MAX_DRAIN_AFTER_END_S
        else ""
    )
    print(
        f"Simulation length: {SIM_END_S} s ({SIM_END_S // 60} min){drain_note} "
        f"| ~{est_vehicles} EVs | 150 kW fast charge"
    )
    print(f"Default vehicle: {tracked_vehicle} (orange) | Shift+click any EV to switch")
    print(f"Press F to jump back to {MONITORED_VEHICLE}")
    print(f"Low battery: < {LOW_BATTERY_WH} Wh")
    print(f"Charge target: {CHARGE_TARGET_WH} Wh (~{100*CHARGE_TARGET_WH/60000:.0f}%)\n")
    if use_gui:
        print(
            "EV details: read param 'ev.info' or the Message panel at the bottom "
            "(drag parameter window corner if text overlaps).\n"
        )
    if export_telemetry:
        print("Backend export: Simulation/output/telemetry.csv (+ tripinfo, battery, summary)\n")

    from sumo_ev_display import (
        RollingEnergyTracker,
        apply_tracked_vehicle_style,
        get_gui_tracked_vehicle,
        setup_charging_poi_display,
        setup_sumo_gui_tracking,
        switch_tracked_vehicle_highlight,
    )

    recorder = None
    if export_telemetry:
        from sumo_telemetry_export import TelemetryRecorder

        recorder = TelemetryRecorder(
            tracked_vehicle=tracked_vehicle,
            sample_every=telemetry_every,
        )
        recorder.start()

    traci.start(cfg_args)
    if use_gui:
        setup_charging_poi_display()
    active_vehicle = tracked_vehicle
    recommended_vehicles: set[str] = set()
    recommended_station_name: str | None = None
    step = 0
    tracker = RollingEnergyTracker()
    tracked_camera = False
    main_vehicle_hotkey = None
    if use_gui:
        from sumo_hotkey import MainVehicleHotkey

        main_vehicle_hotkey = MainVehicleHotkey()
        if not main_vehicle_hotkey.start():
            print("Note: F hotkey unavailable — use Locate > Vehicles > MCU_EV_TEST_01\n")

    def _xy_to_latlon(x: float, y: float) -> tuple[float, float]:
        lon, lat = get_net().convertXY2LonLat(x, y)
        return float(lat), float(lon)

    try:
        while traci.simulation.getMinExpectedNumber() > 0:
            traci.simulationStep()
            step += 1
            sim_time = traci.simulation.getTime()

            if max_steps is not None and step >= max_steps:
                break
            if sim_time >= SIM_END_S + MAX_DRAIN_AFTER_END_S:
                print(
                    f"\n>>> Simulation time cap ({SIM_END_S + MAX_DRAIN_AFTER_END_S}s) reached.\n"
                )
                break

            if recorder is not None:
                recorder.maybe_record_step(step, xy_to_latlon=_xy_to_latlon)

            if use_gui:
                if main_vehicle_hotkey is not None and main_vehicle_hotkey.consume():
                    if MONITORED_VEHICLE in traci.vehicle.getIDList():
                        if active_vehicle != MONITORED_VEHICLE:
                            switch_tracked_vehicle_highlight(
                                active_vehicle, MONITORED_VEHICLE
                            )
                        setup_sumo_gui_tracking(MONITORED_VEHICLE)
                        active_vehicle = MONITORED_VEHICLE
                        tracker = RollingEnergyTracker()
                        recommended_station_name = None
                        if recorder is not None:
                            recorder.tracked_vehicle = active_vehicle
                        print(f"\n>>> [F] Jumped to main vehicle {MONITORED_VEHICLE}\n")
                        try:
                            traci.simulation.writeMessage(
                                f"[F] Tracking main vehicle {MONITORED_VEHICLE}"
                            )
                        except traci.TraCIException:
                            pass
                    else:
                        try:
                            traci.simulation.writeMessage(
                                f"[F] {MONITORED_VEHICLE} not in simulation right now"
                            )
                        except traci.TraCIException:
                            pass

                gui_tracked = get_gui_tracked_vehicle()
                if gui_tracked and gui_tracked != active_vehicle:
                    switch_tracked_vehicle_highlight(active_vehicle, gui_tracked)
                    print(f"\n>>> Tracking switched to {gui_tracked} (orange)\n")
                    active_vehicle = gui_tracked
                    tracker = RollingEnergyTracker()
                    recommended_station_name = None
                    if recorder is not None:
                        recorder.tracked_vehicle = active_vehicle

                if not tracked_camera and active_vehicle in traci.vehicle.getIDList():
                    setup_sumo_gui_tracking(active_vehicle)
                    apply_tracked_vehicle_style(active_vehicle)
                    tracked_camera = True

            if active_vehicle not in traci.vehicle.getIDList():
                continue

            charging = is_vehicle_charging(active_vehicle)
            maybe_resume_after_charge(active_vehicle, recorder)

            try:
                tracker.sample(active_vehicle)
            except traci.TraCIException:
                pass

            if use_gui and step % GUI_UPDATE_EVERY_STEPS == 0:
                refresh_sumo_gui_ev_overlay(
                    active_vehicle,
                    tracker,
                    write_message=(step % GUI_MESSAGE_EVERY_STEPS == 0),
                    recommended_station=recommended_station_name,
                    is_tracked=True,
                    charging=charging,
                )

            if step % CHECK_EVERY_STEPS != 0:
                continue

            battery = get_vehicle_battery_wh(active_vehicle)
            if battery is None:
                continue

            lat, lon = vehicle_latlon(active_vehicle)
            ev_battery = build_live_ev_battery(active_vehicle, battery, tracker)
            from logic import describe_ev_range

            ri = describe_ev_range(ev_battery)
            _d, _n, roll = tracker.rolling_stats()
            roll_s = f" rolling={roll:.0f} Wh/km" if roll else ""
            chg_s = " CHARGING" if charging else ""
            print(
                f"[t={traci.simulation.getTime():.0f}s] {active_vehicle} "
                f"SoC={ri['soc_percent']:.1f}%{chg_s} range~{ri['max_drivable_km']:.1f}km "
                f"({ri['wh_per_km']:.0f} Wh/km{roll_s})"
            )

            if battery >= LOW_BATTERY_WH or active_vehicle in recommended_vehicles:
                continue

            from recommend import print_recommendations, rank_stations_algorithm

            print("\n*** LOW BATTERY — running Algorithm ranking ***")
            if recorder is not None:
                recorder.log_event(
                    "low_battery",
                    vehicle=active_vehicle,
                    remaining_wh=battery,
                    lat=lat,
                    lon=lon,
                )
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
                    active_vehicle,
                    tracker,
                    write_message=True,
                    recommended_station=recommended_station_name,
                    is_tracked=True,
                    charging=charging,
                )
            if reroute_on_low_battery:
                ok = False
                ranked_list = list(ranked.iterrows())
                reachable = []
                unreachable = []
                for idx, row in ranked_list:
                    cs_id = resolve_charging_station_id(row)
                    if cs_id and is_charger_reachable(active_vehicle, cs_id):
                        reachable.append((idx, row))
                    else:
                        unreachable.append((idx, row))
                for _, row in reachable + unreachable:
                    if route_vehicle_to_charging_station(active_vehicle, row):
                        print(
                            f"\n>>> {active_vehicle} routing to charger: {row['Station Name']}\n"
                        )
                        if recorder is not None:
                            recorder.log_event(
                                "charging_stop_queued",
                                vehicle=active_vehicle,
                                station=str(row.get("Station Name", "")),
                                mac=str(row.get("MAC Address", "")),
                            )
                        ok = True
                        break
                if not ok:
                    print(f"\n>>> Could not queue a valid charging stop — try rerunning "
                          f"generate_charging_stations.py\n")

            out_csv = _ALGO_DIR / "final_recommendations_summary.csv"
            export_cols = [c for c in ranked.columns if c not in ("poi_nearby", "llm_context")]
            ranked[export_cols].to_csv(out_csv, index=False)
            rec_out = _SIM_DIR / "output" / "recommendations.csv"
            rec_out.parent.mkdir(parents=True, exist_ok=True)
            ranked[export_cols].to_csv(rec_out, index=False)
            print(f"Saved rankings: {out_csv}\n")
            recommended_vehicles.add(active_vehicle)

    finally:
        if main_vehicle_hotkey is not None:
            main_vehicle_hotkey.stop()
        summary_path = None
        if recorder is not None:
            try:
                end_s = traci.simulation.getTime()
            except traci.TraCIException:
                end_s = step
            summary_path = recorder.close(
                extra_summary={
                    "simulation_end_s": end_s,
                    "steps_run": step,
                    "recommended_station": recommended_station_name,
                    "tracked_vehicle": active_vehicle,
                }
            )
            print(f"\n--- Backend export ---")
            print(f"  telemetry.csv  -> {_SIM_DIR / 'output' / 'telemetry.csv'}")
            print(f"  sim_summary    -> {summary_path}")
            print(f"  battery_log    -> {_SIM_DIR / 'output' / 'battery_log.xml'}")
            print(f"  tripinfo       -> {_SIM_DIR / 'output' / 'tripinfo.xml'}")
            print(f"  summary        -> {_SIM_DIR / 'output' / 'summary.xml'}")
        if use_gui:
            traci.close(wait=True)
            print("SUMO closed by user.")
        else:
            traci.close()
            print("Simulation ended.")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="SUMO Taiwan sim + backend telemetry export")
    parser.add_argument("--headless", action="store_true", help="Run without GUI (faster for batch)")
    parser.add_argument("--max-steps", type=int, default=None)
    parser.add_argument("--no-telemetry", action="store_true", help="Disable CSV/JSON export")
    parser.add_argument("--telemetry-every", type=int, default=5, help="Sample every N steps")
    parser.add_argument("--google", action="store_true", help="Use Google APIs for ranking")
    args = parser.parse_args()

    run_integrated_simulation(
        use_gui=not args.headless,
        max_steps=args.max_steps,
        export_telemetry=not args.no_telemetry,
        telemetry_every=args.telemetry_every,
        use_google_apis=args.google,
    )
