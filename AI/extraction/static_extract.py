"""Fetch static TDX data (stations, charging rates, parking rates)."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Callable

from .checkpoint import update_static
from .config import REQUEST_INTERVAL_SEC
from .manifest import Manifest
from .merge import merge_static_master
from .paths import date_hour_strings, ensure_layout, log_file, static_raw_path
from .tdx import (
    TDX_CITIES,
    UNSUPPORTED_EV_CITIES,
    RawTDXClient,
    build_client,
)
import requests

_STATIC_JOBS: list[tuple[str, str, Callable[[RawTDXClient, str], Any]]] = [
    ("stations", "stations", lambda c, city: c.fetch_stations_body(city)),
    (
        "charging_rates",
        "charging_rates",
        lambda c, city: c.fetch_charging_rate_body(city),
    ),
    (
        "parking_rates",
        "parking_rates",
        lambda c, city: c.fetch_parking_rate_body(city),
    ),
]


def _log(msg: str) -> None:
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} [static] {msg}"
    print(line)
    path = log_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def _atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    tmp.replace(path)


def run_static_extract(*, force: bool = False, date_str: str | None = None) -> dict[str, int]:
    ensure_layout()
    manifest = Manifest()
    manifest.reset_stale_in_progress("static")

    date_str = date_str or date_hour_strings()[0]
    client = build_client()
    run_id = manifest.start_run("static")

    ok = failed = skipped = api_calls = 0

    for city in TDX_CITIES:
        for endpoint, folder_name, fetch_fn in _STATIC_JOBS:
            task_id = f"static:{endpoint}:{city}"
            out_path = static_raw_path(folder_name, city, date_str)

            if city in UNSUPPORTED_EV_CITIES:
                skipped += 1
                manifest.upsert_task(
                    task_id,
                    "static",
                    "skipped",
                    last_error="Skipped: TDX EV endpoint returns 400 for this city.",
                )
                _log(f"SKIP {task_id} (unsupported by endpoint)")
                continue

            existing = manifest.get_task(task_id)
            if out_path.is_file() and not force:
                if existing and existing.get("status") == "success":
                    skipped += 1
                    _log(f"SKIP {task_id} (already exists)")
                    continue

            manifest.upsert_task(
                task_id, "static", "in_progress", increment_attempt=True
            )
            try:
                _log(f"FETCH {task_id}")
                body = fetch_fn(client, city)
                _atomic_write_json(out_path, body)
                manifest.upsert_task(
                    task_id,
                    "static",
                    "success",
                    output_path=str(out_path),
                )
                ok += 1
                api_calls += 1
            except requests.HTTPError as exc:
                status = getattr(exc.response, "status_code", None)
                if status == 400:
                    skipped += 1
                    manifest.upsert_task(
                        task_id,
                        "static",
                        "skipped",
                        last_error=str(exc),
                    )
                    _log(f"SKIP {task_id} (HTTP 400)")
                else:
                    manifest.upsert_task(
                        task_id,
                        "static",
                        "failed",
                        last_error=str(exc),
                    )
                    failed += 1
                    _log(f"FAIL {task_id}: {exc}")
            except Exception as exc:
                manifest.upsert_task(
                    task_id,
                    "static",
                    "failed",
                    last_error=str(exc),
                )
                failed += 1
                _log(f"FAIL {task_id}: {exc}")

            time.sleep(REQUEST_INTERVAL_SEC)

    summary = {
        "cities_ok": ok,
        "cities_failed": failed,
        "cities_skipped": skipped,
        "api_calls": api_calls,
    }
    manifest.finish_run(run_id, **summary, notes=f"date={date_str}")

    try:
        master = merge_static_master(date_str)
        _log(f"Merged stations_master.parquet ({len(master)} rows)")
    except Exception as exc:
        _log(f"Merge warning: {exc}")

    update_static(date_str=date_str, run_summary=summary)
    _log(
        f"Done: ok={ok} failed={failed} skipped={skipped} api_calls={api_calls}"
    )
    return summary
