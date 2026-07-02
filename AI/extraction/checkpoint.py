"""Write and update checkpoint.json for human-readable progress."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from .manifest import Manifest
from .paths import checkpoint_json, now_local
from .tdx import SUPPORTED_EV_CITIES


def _read() -> dict[str, Any]:
    path = checkpoint_json()
    if path.is_file():
        with path.open(encoding="utf-8") as f:
            return json.load(f)
    return {}


def _write(data: dict[str, Any]) -> None:
    path = checkpoint_json()
    path.parent.mkdir(parents=True, exist_ok=True)
    data["last_updated"] = datetime.now(timezone.utc).isoformat()
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def update_static(*, date_str: str, run_summary: dict[str, int]) -> None:
    data = _read()
    total_tasks = len(SUPPORTED_EV_CITIES) * 3
    manifest = Manifest()
    counts = manifest.count_by_phase_status("static")
    done = counts.get("success", 0)

    data["static"] = {
        "complete": done >= total_tasks,
        "date": date_str,
        "cities_total": len(SUPPORTED_EV_CITIES),
        "tasks_total": total_tasks,
        "tasks_success": done,
        "tasks_failed": counts.get("failed", 0),
        "last_run": run_summary,
    }
    _write(data)


def update_live(
    *,
    date_str: str,
    hour_str: str,
    run_summary: dict[str, int],
    stations_with_availability: int | None = None,
) -> None:
    data = _read()
    local = now_local()
    next_hour = local.replace(minute=5, second=0, microsecond=0)
    if local.minute >= 5:
        from datetime import timedelta

        next_hour = next_hour + timedelta(hours=1)

    data["live"] = {
        "enabled": True,
        "last_archive_path": f"live/raw/{date_str}/hour-{hour_str}",
        "last_refresh": datetime.now(timezone.utc).isoformat(),
        "snapshot_at": f"{date_str}T{hour_str}:00:00+08:00",
        "cities_written": run_summary.get("cities_ok", 0),
        "stations_with_availability": stations_with_availability,
        "next_scheduled_refresh": next_hour.isoformat(),
        "last_run": run_summary,
    }
    _write(data)


def show_status() -> dict[str, Any]:
    data = _read()
    manifest = Manifest()
    data["manifest_static"] = manifest.count_by_phase_status("static")
    data["manifest_live"] = manifest.count_by_phase_status("live")
    data["last_static_run"] = manifest.last_run("static")
    data["last_live_run"] = manifest.last_run("live")
    return data
