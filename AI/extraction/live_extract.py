"""Hourly live connector status extraction."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from .checkpoint import update_live
from .config import REQUEST_INTERVAL_SEC
from .manifest import Manifest
from .merge import merge_live_from_hour
from .paths import date_hour_strings, ensure_layout, live_raw_path, log_file
from .tdx import SUPPORTED_EV_CITIES, TDX_CITIES, UNSUPPORTED_EV_CITIES, build_client
import requests

_CONNECTOR_AVAILABLE = 1


def _log(msg: str) -> None:
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} [live] {msg}"
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


def _hour_complete(date_str: str, hour_str: str) -> bool:
    return all(
        live_raw_path(date_str, hour_str, city).is_file() for city in SUPPORTED_EV_CITIES
    )


def run_live_extract(*, force: bool = False) -> dict[str, int]:
    ensure_layout()
    manifest = Manifest()
    manifest.reset_stale_in_progress("live")

    date_str, hour_str = date_hour_strings()
    if _hour_complete(date_str, hour_str) and not force:
        _log(
            f"SKIP hour-{hour_str} on {date_str} "
            f"(all {len(SUPPORTED_EV_CITIES)} supported cities present)"
        )
        try:
            df = merge_live_from_hour(date_str, hour_str)
            avail = int((df["available_points"] >= 1).sum())
            update_live(
                date_str=date_str,
                hour_str=hour_str,
                run_summary={
                    "cities_ok": 0,
                    "cities_failed": 0,
                    "cities_skipped": len(SUPPORTED_EV_CITIES),
                    "api_calls": 0,
                },
                stations_with_availability=avail,
            )
        except Exception as exc:
            _log(f"Merge on skip: {exc}")
        return {
            "cities_ok": 0,
            "cities_failed": 0,
            "cities_skipped": len(SUPPORTED_EV_CITIES),
            "api_calls": 0,
        }

    client = build_client()
    run_id = manifest.start_run("live")
    ok = failed = skipped = api_calls = 0

    for city in TDX_CITIES:
        task_id = f"live:{date_str}:hour-{hour_str}:{city}"
        out_path = live_raw_path(date_str, hour_str, city)

        if city in UNSUPPORTED_EV_CITIES:
            skipped += 1
            manifest.upsert_task(
                task_id,
                "live",
                "skipped",
                last_error="Skipped: TDX EV endpoint returns 400 for this city.",
            )
            _log(f"SKIP {city} (unsupported by endpoint)")
            continue

        if out_path.is_file() and not force:
            skipped += 1
            _log(f"SKIP {city} (file exists)")
            continue

        manifest.upsert_task(
            task_id, "live", "in_progress", increment_attempt=True
        )
        try:
            _log(f"FETCH {city} -> hour-{hour_str}")
            body = client.fetch_live_status_body(city)
            _atomic_write_json(out_path, body)
            manifest.upsert_task(
                task_id,
                "live",
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
                    task_id, "live", "skipped", last_error=str(exc)
                )
                _log(f"SKIP {city} (HTTP 400)")
            else:
                manifest.upsert_task(
                    task_id, "live", "failed", last_error=str(exc)
                )
                failed += 1
                _log(f"FAIL {city}: {exc}")
        except Exception as exc:
            manifest.upsert_task(
                task_id, "live", "failed", last_error=str(exc)
            )
            failed += 1
            _log(f"FAIL {city}: {exc}")

        time.sleep(REQUEST_INTERVAL_SEC)

    summary = {
        "cities_ok": ok,
        "cities_failed": failed,
        "cities_skipped": skipped,
        "api_calls": api_calls,
    }
    manifest.finish_run(
        run_id,
        **summary,
        notes=f"{date_str} hour-{hour_str}",
    )

    stations_with_availability = None
    if _hour_complete(date_str, hour_str):
        try:
            df = merge_live_from_hour(date_str, hour_str)
            stations_with_availability = int((df["available_points"] >= 1).sum())
            _log(
                f"Merged latest.parquet ({len(df)} rows, "
                f"{stations_with_availability} with availability)"
            )
        except Exception as exc:
            _log(f"Merge warning: {exc}")
    elif failed:
        _log(
            f"Hour hour-{hour_str} incomplete "
            f"({ok + skipped}/{len(SUPPORTED_EV_CITIES)} supported cities); "
            "latest.parquet not updated"
        )

    update_live(
        date_str=date_str,
        hour_str=hour_str,
        run_summary=summary,
        stations_with_availability=stations_with_availability,
    )
    _log(f"Done: ok={ok} failed={failed} skipped={skipped} api_calls={api_calls}")
    return summary
