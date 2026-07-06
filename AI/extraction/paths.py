"""Filesystem layout under DATA_ROOT."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from . import config
from .config import LIVE_INTERVAL_MINUTES, TIMEZONE


def _root() -> Path:
    return config.DATA_ROOT


def _state_root() -> Path:
    """Local non-synced state (SQLite/checkpoint). Synology Drive corrupts SQLite."""
    return Path(__file__).resolve().parents[1] / ".extraction_state"


STATIC_ENDPOINTS = ("stations", "charging_rates", "parking_rates")


def ensure_layout() -> None:
    """Create expected top-level folders if missing."""
    for sub in (
        "static/raw/stations",
        "static/raw/charging_rates",
        "static/raw/parking_rates",
        "static/processed",
        "live/raw",
        "live/processed/daily",
        "logs",
    ):
        (_root() / sub).mkdir(parents=True, exist_ok=True)
    _state_root().mkdir(parents=True, exist_ok=True)


def manifest_db() -> Path:
    return _state_root() / "manifest.db"


def checkpoint_json() -> Path:
    return _state_root() / "checkpoint.json"


def log_file(when: datetime | None = None) -> Path:
    tz = ZoneInfo(TIMEZONE)
    dt = (when or datetime.now(tz)).astimezone(tz)
    return _root() / "logs" / f"extraction_{dt:%Y-%m-%d}.log"


def static_raw_path(endpoint: str, city: str, date_str: str) -> Path:
    return _root() / "static" / "raw" / endpoint / city / f"{date_str}.json"


def static_processed_master() -> Path:
    return _root() / "static" / "processed" / "stations_master.parquet"


def live_raw_path(date_str: str, slot_str: str, city: str) -> Path:
    return _root() / "live" / "raw" / date_str / f"hour-{slot_str}" / f"{city}.json"


def live_slot_dir(date_str: str, slot_str: str) -> Path:
    return _root() / "live" / "raw" / date_str / f"hour-{slot_str}"


def live_hour_dir(date_str: str, slot_str: str) -> Path:
    """Alias for live_slot_dir (legacy name)."""
    return live_slot_dir(date_str, slot_str)


def snapshot_at_from_slot(date_str: str, slot_str: str) -> str:
    """ISO timestamp for a slot folder name (supports legacy hour-only names)."""
    if "-" in slot_str:
        hour, minute = slot_str.split("-", 1)
        return f"{date_str}T{hour}:{minute}:00+08:00"
    return f"{date_str}T{slot_str}:00:00+08:00"


def date_slot_strings(when: datetime | None = None) -> tuple[str, str]:
    """Return (YYYY-MM-DD, HH-MM) floored to LIVE_INTERVAL_MINUTES."""
    dt = (when or now_local()).astimezone(ZoneInfo(TIMEZONE))
    interval = max(1, LIVE_INTERVAL_MINUTES)
    floored_minute = (dt.minute // interval) * interval
    slot_dt = dt.replace(minute=floored_minute, second=0, microsecond=0)
    return slot_dt.strftime("%Y-%m-%d"), slot_dt.strftime("%H-%M")


def date_hour_strings(when: datetime | None = None) -> tuple[str, str]:
    """Deprecated alias; use date_slot_strings."""
    return date_slot_strings(when)


def live_processed_latest() -> Path:
    return _root() / "live" / "processed" / "latest.parquet"


def live_daily_parquet(date_str: str) -> Path:
    return _root() / "live" / "processed" / "daily" / f"{date_str}.parquet"


def now_local() -> datetime:
    return datetime.now(ZoneInfo(TIMEZONE))
