"""
SUMO-GUI overlays for EV battery / range (TraCI).
"""
from __future__ import annotations

import math
from typing import TYPE_CHECKING

import traci

if TYPE_CHECKING:
    from logic import EVBatteryState

ROLLING_MIN_WINDOW_M = 150.0
ROLLING_MAX_WINDOW_M = 2_000.0

# Tracked / monitored vehicle — always orange in GUI
TRACKED_VEHICLE_COLOR = (255, 140, 0, 255)


class RollingEnergyTracker:
    def __init__(
        self,
        *,
        min_window_m: float = ROLLING_MIN_WINDOW_M,
        max_window_m: float = ROLLING_MAX_WINDOW_M,
    ) -> None:
        self.min_window_m = min_window_m
        self.max_window_m = max_window_m
        self._points: list[tuple[float, float, float, float]] = []

    def _path_length_m(self) -> float:
        if len(self._points) < 2:
            return 0.0
        total = 0.0
        for i in range(1, len(self._points)):
            x0, y0, _, _ = self._points[i - 1]
            x1, y1, _, _ = self._points[i]
            total += math.hypot(x1 - x0, y1 - y0)
        return total

    def _trim(self) -> None:
        while len(self._points) > 2 and self._path_length_m() > self.max_window_m:
            self._points.pop(0)

    def sample(self, veh_id: str) -> None:
        x, y = traci.vehicle.getPosition(veh_id)
        tec = float(
            traci.vehicle.getParameter(veh_id, "device.battery.totalEnergyConsumed")
        )
        ter = float(
            traci.vehicle.getParameter(veh_id, "device.battery.totalEnergyRegenerated")
        )
        self._points.append((float(x), float(y), tec, ter))
        self._trim()

    def rolling_stats(self) -> tuple[float | None, float | None, float | None]:
        if len(self._points) < 2:
            return None, None, None
        dist = self._path_length_m()
        tec0, ter0 = self._points[0][2], self._points[0][3]
        tec1, ter1 = self._points[-1][2], self._points[-1][3]
        net_wh = (tec1 - tec0) - (ter1 - ter0)
        if dist < self.min_window_m or dist <= 0:
            return dist, net_wh, None
        return dist, net_wh, (net_wh / dist) * 1000.0


def format_vehicle_line(
    *,
    soc_percent: float,
    max_km: float,
    wh_per_km: float,
    rolling_wh_per_km: float | None,
    recommended_station: str | None = None,
    charging: bool = False,
) -> str:
    """Short label above the vehicle on the map (not the parameter table)."""
    tag = "CHG" if charging else "EV"
    return f"{tag} {soc_percent:.0f}% ~{max_km:.0f}km"


def format_ev_summary(
    *,
    range_info: dict[str, float],
    rolling_wh_per_km: float | None = None,
    recommended_station: str | None = None,
    charging: bool = False,
) -> str:
    """One-line EV status for the single custom parameter row."""
    roll = (
        f" roll {rolling_wh_per_km:.0f}"
        if rolling_wh_per_km is not None and rolling_wh_per_km > 0
        else ""
    )
    chg = " CHARGING" if charging else ""
    station = ""
    if recommended_station:
        short = recommended_station[:24]
        station = f" -> {short}"
    return (
        f"SoC {range_info['soc_percent']:.1f}%"
        f" | {range_info['remaining_wh']:.0f} Wh"
        f" | ~{range_info['max_drivable_km']:.0f} km"
        f" | {range_info['wh_per_km']:.0f} Wh/km{roll}{chg}{station}"
    )


# Old multi-row keys — clear so the parameter table stays readable
_LEGACY_EV_PARAM_KEYS = (
    "EV | SoC %",
    "EV | range km",
    "EV | Wh/km",
    "EV | rolling Wh/km",
    "EV | charging",
    "EV | target station",
    "EV | remaining Wh",
)


def update_ev_summary_param(
    veh_id: str,
    *,
    range_info: dict[str, float],
    rolling_wh_per_km: float | None = None,
    recommended_station: str | None = None,
    charging: bool = False,
) -> None:
    """Single custom row in SUMO parameter table (avoids 7 extra cramped rows)."""
    summary = format_ev_summary(
        range_info=range_info,
        rolling_wh_per_km=rolling_wh_per_km,
        recommended_station=recommended_station,
        charging=charging,
    )
    try:
        for key in _LEGACY_EV_PARAM_KEYS:
            traci.vehicle.setParameter(veh_id, key, "")
        traci.vehicle.setParameter(veh_id, "ev.info", summary)
    except traci.TraCIException:
        pass


def update_sumo_vehicle_display(
    veh_id: str,
    state: "EVBatteryState",
    range_info: dict[str, float],
    *,
    rolling_wh_per_km: float | None = None,
    recommended_station: str | None = None,
    write_message: bool = False,
    is_tracked: bool = False,
    charging: bool = False,
) -> None:
    line = format_vehicle_line(
        soc_percent=range_info["soc_percent"],
        max_km=range_info["max_drivable_km"],
        wh_per_km=range_info["wh_per_km"],
        rolling_wh_per_km=rolling_wh_per_km,
        recommended_station=recommended_station,
        charging=charging,
    )
    try:
        traci.vehicle.setLine(veh_id, line)
        update_ev_summary_param(
            veh_id,
            range_info=range_info,
            rolling_wh_per_km=rolling_wh_per_km,
            recommended_station=recommended_station,
            charging=charging,
        )
        if is_tracked:
            traci.vehicle.setColor(veh_id, TRACKED_VEHICLE_COLOR)
        else:
            traci.vehicle.setColor(veh_id, soc_vehicle_color(range_info["soc_percent"]))
    except traci.TraCIException:
        pass

    if write_message:
        status = "CHARGING" if charging else "driving"
        roll_txt = (
            f" | rolling {rolling_wh_per_km:.0f} Wh/km"
            if rolling_wh_per_km is not None
            else ""
        )
        try:
            station_txt = f" | target: {recommended_station}" if recommended_station else ""
            traci.simulation.writeMessage(
                f"[{status}] {veh_id}: {range_info['soc_percent']:.1f}% "
                f"({range_info['remaining_wh']:.0f} Wh) — "
                f"max ~{range_info['max_drivable_km']:.2f} km{roll_txt}{station_txt}"
            )
        except traci.TraCIException:
            pass


def soc_vehicle_color(soc_percent: float) -> tuple[int, int, int, int]:
    if soc_percent >= 25:
        return 0, 200, 80, 255
    if soc_percent >= 12:
        return 255, 200, 0, 255
    return 255, 80, 0, 255


def restore_vehicle_soc_color(veh_id: str) -> None:
    """Restore SoC-based color (green / yellow / red) after user switches tracked vehicle."""
    if veh_id not in traci.vehicle.getIDList():
        return
    try:
        remaining = float(
            traci.vehicle.getParameter(veh_id, "device.battery.actualBatteryCapacity")
        )
        maximum = float(
            traci.vehicle.getParameter(veh_id, "device.battery.maximumBatteryCapacity")
        )
        soc = 100.0 * remaining / maximum if maximum > 0 else 0.0
        traci.vehicle.setColor(veh_id, soc_vehicle_color(soc))
    except traci.TraCIException:
        pass


def get_gui_tracked_vehicle() -> str | None:
    """Vehicle the user is following via Shift+click / Start Tracking in SUMO-GUI."""
    active = set(traci.vehicle.getIDList())
    for view_id in ("View #0",) + tuple(traci.gui.getIDList()):
        try:
            veh_id = traci.gui.getTrackedVehicle(view_id)
            if veh_id and veh_id in active:
                return veh_id
        except traci.TraCIException:
            continue
    return None


def switch_tracked_vehicle_highlight(old_id: str | None, new_id: str) -> None:
    if old_id and old_id != new_id:
        restore_vehicle_soc_color(old_id)
    apply_tracked_vehicle_style(new_id)


def recenter_on_vehicle(veh_id: str, *, zoom: float = 1500) -> None:
    """Move camera to veh_id and start GUI tracking."""
    for view_id in ("View #0",) + tuple(traci.gui.getIDList()):
        try:
            traci.gui.trackVehicle(view_id, veh_id)
            traci.gui.setZoom(view_id, zoom)
            return
        except traci.TraCIException:
            continue


def setup_sumo_gui_tracking(veh_id: str) -> None:
    """Lock SUMO-GUI camera on the tracked vehicle."""
    recenter_on_vehicle(veh_id)


def apply_tracked_vehicle_style(veh_id: str) -> None:
    """Orange color for the vehicle the user follows."""
    try:
        traci.vehicle.setColor(veh_id, TRACKED_VEHICLE_COLOR)
    except traci.TraCIException:
        pass


CHARGING_POI_WIDTH_M = 60.0
CHARGING_POI_HEIGHT_M = 60.0
RECOMMENDED_POI_WIDTH_M = 90.0
RECOMMENDED_POI_HEIGHT_M = 90.0


def setup_charging_poi_display() -> None:
    """Make charging-station markers large enough to see on the map."""
    for poi_id in traci.poi.getIDList():
        if not poi_id.startswith("chg_"):
            continue
        try:
            traci.poi.setWidth(poi_id, CHARGING_POI_WIDTH_M)
            traci.poi.setHeight(poi_id, CHARGING_POI_HEIGHT_M)
            traci.poi.setColor(poi_id, (0, 200, 80, 255))
        except traci.TraCIException:
            pass


def highlight_charging_poi(poi_id: str, *, recommended: bool = False) -> None:
    try:
        if recommended:
            traci.poi.setWidth(poi_id, RECOMMENDED_POI_WIDTH_M)
            traci.poi.setHeight(poi_id, RECOMMENDED_POI_HEIGHT_M)
            traci.poi.setColor(poi_id, (255, 140, 0, 255))
        else:
            traci.poi.setWidth(poi_id, CHARGING_POI_WIDTH_M)
            traci.poi.setHeight(poi_id, CHARGING_POI_HEIGHT_M)
            traci.poi.setColor(poi_id, (0, 200, 80, 255))
    except traci.TraCIException:
        pass
