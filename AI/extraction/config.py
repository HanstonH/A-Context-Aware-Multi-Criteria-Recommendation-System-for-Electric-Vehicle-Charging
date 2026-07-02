"""Paths and defaults for TDX data extraction to Synology Drive."""
from __future__ import annotations

import os
from pathlib import Path

# Synology Drive sync folder (override with EV_DATA_ROOT).
_DEFAULT_DATA_ROOT = Path(
    r"C:\Users\hanst\SynologyDrive\ev-data"
)

DATA_ROOT = Path(os.getenv("EV_DATA_ROOT", str(_DEFAULT_DATA_ROOT))).resolve()

# Pause between TDX API calls (seconds).
REQUEST_INTERVAL_SEC = float(os.getenv("EV_EXTRACT_INTERVAL_SEC", "2.5"))

# IANA timezone for hourly live archive folders.
TIMEZONE = os.getenv("EV_EXTRACT_TIMEZONE", "Asia/Taipei")
