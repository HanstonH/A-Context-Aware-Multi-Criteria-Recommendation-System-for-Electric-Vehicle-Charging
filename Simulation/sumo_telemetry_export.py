"""
Export SUMO simulation telemetry for backend ingestion (CSV + JSON summary).
"""
from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import traci

_SIM_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT_DIR = _SIM_DIR / "output"

TELEMETRY_FIELDS = [
    "time_s",
    "vehicle_id",
    "lat",
    "lon",
    "x",
    "y",
    "speed_mps",
    "acceleration_mps2",
    "edge_id",
    "lane_id",
    "remaining_wh",
    "max_wh",
    "soc_percent",
    "charging",
    "charging_station_id",
    "total_energy_consumed_wh",
    "total_energy_regenerated_wh",
    "energy_charged_wh",
    "distance_m",
    "is_tracked",
]


@dataclass
class TelemetryRecorder:
    """Sample vehicle state every N steps into CSV; write JSON summary on close."""

    output_dir: Path = DEFAULT_OUTPUT_DIR
    sample_every: int = 5
    tracked_vehicle: str = "MCU_EV_TEST_01"
    csv_name: str = "telemetry.csv"
    summary_name: str = "sim_summary.json"
    _rows: int = field(default=0, init=False)
    _events: list[dict[str, Any]] = field(default_factory=list, init=False)
    _csv_path: Path | None = field(default=None, init=False)
    _writer: csv.DictWriter | None = field(default=None, init=False)
    _file = None

    def __post_init__(self) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._csv_path = self.output_dir / self.csv_name

    def start(self) -> None:
        self._file = self._csv_path.open("w", newline="", encoding="utf-8")
        self._writer = csv.DictWriter(self._file, fieldnames=TELEMETRY_FIELDS)
        self._writer.writeheader()

    def log_event(self, event_type: str, **payload: Any) -> None:
        self._events.append(
            {"time_s": traci.simulation.getTime(), "type": event_type, **payload}
        )

    def maybe_record_step(
        self,
        step: int,
        *,
        xy_to_latlon,
    ) -> None:
        if self._writer is None or step % self.sample_every != 0:
            return
        t = traci.simulation.getTime()
        for veh_id in traci.vehicle.getIDList():
            row = self._snapshot_vehicle(veh_id, t, xy_to_latlon)
            self._writer.writerow(row)
            self._rows += 1

    def _snapshot_vehicle(self, veh_id: str, t: float, xy_to_latlon) -> dict[str, Any]:
        pos = traci.vehicle.getPosition(veh_id)
        x, y = float(pos[0]), float(pos[1])
        try:
            lat, lon = xy_to_latlon(x, y)
        except Exception:
            lat, lon = 0.0, 0.0

        remaining = _fparam(veh_id, "device.battery.actualBatteryCapacity")
        maximum = _fparam(veh_id, "device.battery.maximumBatteryCapacity") or _fparam(
            veh_id, "device.battery.capacity"
        )
        if remaining is None:
            remaining = _fparam(veh_id, "device.battery.chargeLevel")
        max_wh = maximum or 60_000.0
        rem_wh = remaining if remaining is not None else 0.0
        soc = 100.0 * rem_wh / max_wh if max_wh > 0 else 0.0

        cs_id = _sparam(veh_id, "device.battery.chargingStationId")
        charging = bool(cs_id and cs_id != "NULL")
        try:
            if not charging:
                charging = traci.vehicle.isStoppedParking(veh_id)
        except traci.TraCIException:
            pass

        return {
            "time_s": round(t, 1),
            "vehicle_id": veh_id,
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "x": round(x, 2),
            "y": round(y, 2),
            "speed_mps": round(traci.vehicle.getSpeed(veh_id), 2),
            "acceleration_mps2": round(_vehicle_acceleration(veh_id), 2),
            "edge_id": traci.vehicle.getRoadID(veh_id),
            "lane_id": traci.vehicle.getLaneID(veh_id),
            "remaining_wh": round(rem_wh, 2),
            "max_wh": round(max_wh, 2),
            "soc_percent": round(soc, 2),
            "charging": int(charging),
            "charging_station_id": cs_id if cs_id and cs_id != "NULL" else "",
            "total_energy_consumed_wh": round(
                _fparam(veh_id, "device.battery.totalEnergyConsumed") or 0.0, 2
            ),
            "total_energy_regenerated_wh": round(
                _fparam(veh_id, "device.battery.totalEnergyRegenerated") or 0.0, 2
            ),
            "energy_charged_wh": round(
                _fparam(veh_id, "device.battery.energyCharged") or 0.0, 2
            ),
            "distance_m": round(traci.vehicle.getDistance(veh_id), 2),
            "is_tracked": int(veh_id == self.tracked_vehicle),
        }

    def close(self, *, extra_summary: dict[str, Any] | None = None) -> Path:
        if self._file:
            self._file.close()
            self._file = None

        summary = {
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "telemetry_csv": str(self._csv_path),
            "sample_every_steps": self.sample_every,
            "row_count": self._rows,
            "tracked_vehicle": self.tracked_vehicle,
            "events": self._events,
        }
        if extra_summary:
            summary.update(extra_summary)

        summary_path = self.output_dir / self.summary_name
        summary_path.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return summary_path


def _vehicle_acceleration(veh_id: str) -> float:
    try:
        return float(traci.vehicle.getAcceleration(veh_id))
    except (traci.TraCIException, TypeError, ValueError):
        return _fparam(veh_id, "acceleration") or 0.0


def _fparam(veh_id: str, key: str) -> float | None:
    try:
        return float(traci.vehicle.getParameter(veh_id, key))
    except (traci.TraCIException, TypeError, ValueError):
        return None


def _sparam(veh_id: str, key: str) -> str | None:
    try:
        return str(traci.vehicle.getParameter(veh_id, key))
    except traci.TraCIException:
        return None
