"""Inject WGS84/UTM location into a netgenerate grid so lat/lon POIs align."""
from __future__ import annotations

import math
import re
import sys
from pathlib import Path

SIM_DIR = Path(__file__).resolve().parent
NET = SIM_DIR / "taipei.net.xml"

CENTER_LAT = 25.0330
CENTER_LON = 121.5654
UTM_ZONE = 51


def _geo_bounds_from_grid(
    center_lat: float,
    center_lon: float,
    width_m: float,
    height_m: float,
) -> tuple[float, float, float, float]:
    m_per_deg_lat = 111_320.0
    m_per_deg_lon = 111_320.0 * math.cos(math.radians(center_lat))
    half_w = width_m / 2.0
    half_h = height_m / 2.0
    return (
        center_lon - half_w / m_per_deg_lon,
        center_lat - half_h / m_per_deg_lat,
        center_lon + half_w / m_per_deg_lon,
        center_lat + half_h / m_per_deg_lat,
    )


def georef_net(net_path: Path) -> None:
    text = net_path.read_text(encoding="utf-8")
    conv_match = re.search(r'convBoundary="([^"]+)"', text)
    if not conv_match:
        raise ValueError(f"No convBoundary in {net_path}")

    parts = [float(v) for v in conv_match.group(1).split(",")]
    width_m = parts[2] - parts[0]
    height_m = parts[3] - parts[1]
    lon_min, lat_min, lon_max, lat_max = _geo_bounds_from_grid(
        CENTER_LAT, CENTER_LON, width_m, height_m
    )
    conv = conv_match.group(1)
    proj = f"+proj=utm +zone={UTM_ZONE} +ellps=WGS84 +datum=WGS84 +units=m +no_defs"
    location = (
        f'<location netOffset="0.00,0.00" '
        f'convBoundary="{conv}" '
        f'origBoundary="{lon_min:.6f},{lat_min:.6f},{lon_max:.6f},{lat_max:.6f}" '
        f'projParameter="{proj}"/>'
    )
    text = re.sub(r"<location[^>]*/>", location, text, count=1)
    net_path.write_text(text, encoding="utf-8")
    print(f"Georeferenced {net_path.name} (~{width_m/1000:.1f} x {height_m/1000:.1f} km)")


if __name__ == "__main__":
    georef_net(Path(sys.argv[1]) if len(sys.argv) > 1 else NET)
