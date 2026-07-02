"""Filesystem layout under DATA_ROOT."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from . import config
from .config import TIMEZONE


def _root() -> Path:
    return config.DATA_ROOT

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
        "state",
    ):
        (_root() / sub).mkdir(parents=True, exist_ok=True)


def manifest_db() -> Path:
    return _root() / "manifest.db"


def checkpoint_json() -> Path:
    return _root() / "state" / "checkpoint.json"


def log_file(when: datetime | None = None) -> Path:
    tz = ZoneInfo(TIMEZONE)
    dt = (when or datetime.now(tz)).astimezone(tz)
    return _root() / "logs" / f"extraction_{dt:%Y-%m-%d}.log"


def static_raw_path(endpoint: str, city: str, date_str: str) -> Path:
    return _root() / "static" / "raw" / endpoint / city / f"{date_str}.json"


def static_processed_master() -> Path:
    return _root() / "static" / "processed" / "stations_master.parquet"


def live_raw_path(date_str: str, hour_str: str, city: str) -> Path:
    return _root() / "live" / "raw" / date_str / f"hour-{hour_str}" / f"{city}.json"


def live_hour_dir(date_str: str, hour_str: str) -> Path:
    return _root() / "live" / "raw" / date_str / f"hour-{hour_str}"


def live_processed_latest() -> Path:
    return _root() / "live" / "processed" / "latest.parquet"


def live_daily_parquet(date_str: str) -> Path:
    return _root() / "live" / "processed" / "daily" / f"{date_str}.parquet"


def now_local() -> datetime:
    return datetime.now(ZoneInfo(TIMEZONE))


def date_hour_strings(when: datetime | None = None) -> tuple[str, str]:
    dt = (when or now_local()).astimezone(ZoneInfo(TIMEZONE))
    return dt.strftime("%Y-%m-%d"), dt.strftime("%H")
