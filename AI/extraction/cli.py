"""CLI for TDX EV data extraction to Synology Drive."""
from __future__ import annotations

import argparse
import json
import sys

from .checkpoint import show_status
from .config import DATA_ROOT
from .live_extract import run_live_extract
from .merge import merge_static_master
from .paths import ensure_layout
from .static_extract import run_static_extract


def _cmd_static(args: argparse.Namespace) -> int:
    summary = run_static_extract(force=args.force, date_str=args.date)
    return 1 if summary["cities_failed"] else 0


def _cmd_live(args: argparse.Namespace) -> int:
    summary = run_live_extract(force=args.force)
    return 1 if summary["cities_failed"] else 0


def _cmd_merge_static(args: argparse.Namespace) -> int:
    master = merge_static_master(args.date)
    print(f"Wrote {len(master)} stations to stations_master.parquet")
    return 0


def _cmd_status(_args: argparse.Namespace) -> int:
    data = show_status()
    print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0


def _cmd_init(_args: argparse.Namespace) -> int:
    ensure_layout()
    print(f"Data root ready: {DATA_ROOT}")
    return 0


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(
        description="Extract TDX EV station data to local Synology Drive folder."
    )
    parser.add_argument(
        "--data-root",
        help="Override EV_DATA_ROOT (default: Synology ev-data folder)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="Create folder layout on NAS sync path")
    p_init.set_defaults(func=_cmd_init)

    p_static = sub.add_parser(
        "static", help="Fetch stations + charging + parking rates (all cities)"
    )
    p_static.add_argument(
        "--force", action="store_true", help="Re-fetch even if today's file exists"
    )
    p_static.add_argument(
        "--date",
        help="Archive date folder YYYY-MM-DD (default: today in Asia/Taipei)",
    )
    p_static.set_defaults(func=_cmd_static)

    p_live = sub.add_parser(
        "live", help="Fetch live connector status for current hour (all cities)"
    )
    p_live.add_argument(
        "--force", action="store_true", help="Re-fetch cities even if JSON exists"
    )
    p_live.set_defaults(func=_cmd_live)

    p_merge = sub.add_parser(
        "merge-static", help="Rebuild stations_master.parquet from raw JSON"
    )
    p_merge.add_argument("--date", help="Use JSON from this date (default: per-city latest)")
    p_merge.set_defaults(func=_cmd_merge_static)

    p_status = sub.add_parser("status", help="Show checkpoint.json + manifest summary")
    p_status.set_defaults(func=_cmd_status)

    args = parser.parse_args(argv)
    if args.data_root:
        import os
        from pathlib import Path

        from . import config

        resolved = Path(args.data_root).resolve()
        os.environ["EV_DATA_ROOT"] = str(resolved)
        config.DATA_ROOT = resolved

    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
