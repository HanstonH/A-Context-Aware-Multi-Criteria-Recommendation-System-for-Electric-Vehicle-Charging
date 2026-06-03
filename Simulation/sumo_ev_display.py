"""
SUMO-GUI overlays for EV battery / range (TraCI).

- ``RollingEnergyTracker``: recent Wh/km from the last N metres of driving
- ``update_sumo_vehicle_display``: vehicle label (setLine) + message window
"""
from __future__ import annotations

import math
from typing import TYPE_CHECKING

import traci

if TYPE_CHECKING:
    from logic import EVBatteryState

# Use at least this much road distance before trusting rolling Wh/km
ROLLING_MIN_WINDOW_M = 150.0
# Keep only the last this many metres of samples (rolling window)
ROLLING_MAX_WINDOW_M = 2_000.0


class RollingEnergyTracker:
    """
    Rolling Wh/km = energy used over the *recent* trip segment, not since depart.

    Each simulation step we append (x, y, totalEnergyConsumed, totalEnergyRegenerated).
    Old samples are dropped so the path length stays under ``ROLLING_MAX_WINDOW_M``.
    Once path length >= ``ROLLING_MIN_WINDOW_M``, Wh/km = net_Wh / distance_km.
    """

    def __init__(
        self,
        *,
        min_window_m: float = ROLLING_MIN_WINDOW_M,
        max_window_m: float = ROLLING_MAX_WINDOW_M,
    ) -> None:
        self.min_window_m = min_window_m
        self.max_window_m = max_window_m
        self._points: list[tuple[float, float, float, float]] = []  # x, y, tec, ter

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
        """
        Returns ``(distance_m, net_wh, wh_per_km)`` for the current window.

        ``wh_per_km`` is None until at least ``min_window_m`` were driven.
        """
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
) -> str:
    """Short label drawn under the vehicle in SUMO-GUI (``vehicle.setLine``)."""
    roll = (
        f" roll {rolling_wh_per_km:.0f}"
        if rolling_wh_per_km is not None and rolling_wh_per_km > 0
        else ""
    )
    base = f"SoC {soc_percent:.0f}% | ~{max_km:.1f} km | {wh_per_km:.0f} Wh/km{roll}"
    if recommended_station:
        short = recommended_station[:28] + ("…" if len(recommended_station) > 28 else "")
        return f"{base} -> {short}"
    return base


def soc_vehicle_color(soc_percent: float) -> tuple[int, int, int, int]:
    if soc_percent >= 25:
        return 0, 200, 80, 255
    if soc_percent >= 12:
        return 255, 200, 0, 255
    return 255, 80, 0, 255


def update_sumo_vehicle_display(
    veh_id: str,
    state: "EVBatteryState",
    range_info: dict[str, float],
    *,
    rolling_wh_per_km: float | None = None,
    recommended_station: str | None = None,
    write_message: bool = False,
) -> None:
    """
    Show battery / range on SUMO-GUI.

    - Vehicle subtitle: ``traci.vehicle.setLine`` (always visible above car when labels on)
    - Optional: ``traci.simulation.writeMessage`` (bottom message panel)
    """
    line = format_vehicle_line(
        soc_percent=range_info["soc_percent"],
        max_km=range_info["max_drivable_km"],
        wh_per_km=range_info["wh_per_km"],
        rolling_wh_per_km=rolling_wh_per_km,
        recommended_station=recommended_station,
    )
    try:
        traci.vehicle.setLine(veh_id, line)
        traci.vehicle.setColor(veh_id, soc_vehicle_color(range_info["soc_percent"]))
    except traci.TraCIException:
        pass

    if write_message:
        roll_txt = (
            f" | rolling {rolling_wh_per_km:.0f} Wh/km"
            if rolling_wh_per_km is not None
            else " | rolling Wh/km: calibrating…"
        )
        try:
            traci.simulation.writeMessage(
                f"{veh_id}: {range_info['soc_percent']:.1f}% "
                f"({range_info['remaining_wh']:.0f} Wh) — "
                f"max ~{range_info['max_drivable_km']:.2f} km{roll_txt}"
            )
        except traci.TraCIException:
            pass


def setup_sumo_gui_tracking(veh_id: str) -> None:
    """Centre camera on the EV (SUMO-GUI only)."""
    try:
        traci.gui.trackVehicle("View #0", veh_id)
    except traci.TraCIException:
        try:
            traci.gui.trackVehicle(traci.gui.getIDList()[0], veh_id)
        except traci.TraCIException:
            pass
