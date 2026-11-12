"""Regenerate EV routes if the current file is too short or outdated."""

from __future__ import annotations



import re

import subprocess

import sys

from pathlib import Path



from sim_config import (

    TRIP_END_S,

    TRIP_FRINGE_FACTOR,

    TRIP_MIN_DISTANCE_M,

    TRIP_PERIOD_S,

)



_SIM = Path(__file__).resolve().parent

_MIN_VEHICLES = 150





def vehicle_count(rou: Path) -> int:

    if not rou.is_file():

        return 0

    return len(re.findall(r'<vehicle id="', rou.read_text(encoding="utf-8")))





def trip_end_in_rou(rou: Path) -> int | None:

    text = rou.read_text(encoding="utf-8")

    for pattern in (

        r'<end value="(\d+(?:\.\d+)?)"',

        r"<end value='(\d+(?:\.\d+)?)'",

    ):

        match = re.search(pattern, text)

        if match:

            return int(float(match.group(1)))

    return None





def trip_fringe_in_rou(rou: Path) -> float | None:

    match = re.search(

        r'fringe-factor value="(\d+(?:\.\d+)?)"',

        rou.read_text(encoding="utf-8"),

    )

    return float(match.group(1)) if match else None





def needs_rebuild(rou: Path) -> bool:

    n = vehicle_count(rou)

    if n < _MIN_VEHICLES:

        print(f"taipei.rou.xml has only {n} vehicles (need >= {_MIN_VEHICLES})")

        return True

    end = trip_end_in_rou(rou)

    if end is None or end < TRIP_END_S:

        print(f"taipei.rou.xml trip end={end}s (need {TRIP_END_S}s)")

        return True

    fringe = trip_fringe_in_rou(rou)

    if fringe is None or abs(fringe - TRIP_FRINGE_FACTOR) > 0.01:

        print(

            f"taipei.rou.xml fringe-factor={fringe} "

            f"(need {TRIP_FRINGE_FACTOR} for downtown-biased trips)"

        )

        return True

    return False





def build_routes() -> None:

    print(

        f"Rebuilding routes for {TRIP_END_S}s / period {TRIP_PERIOD_S}s "

        f"(~{TRIP_END_S // TRIP_PERIOD_S} EVs, fringe={TRIP_FRINGE_FACTOR}, "

        f"min-dist={TRIP_MIN_DISTANCE_M}m, ~3-8 min)..."

    )

    import os



    sumo_home = os.environ.get(

        "SUMO_HOME",

        r"C:\Users\USER\Downloads\sumo-win64extra-1.26.0\sumo-1.26.0",

    )

    rt = Path(sumo_home) / "tools" / "randomTrips.py"

    if not (_SIM / "taipei.net.xml").is_file():

        raise SystemExit("Run build_taiwan_map.bat first (missing taipei.net.xml)")

    trips = _SIM / "trips.trips.xml"

    if trips.is_file():

        trips.unlink()

    subprocess.run(

        [

            sys.executable,

            str(rt),

            "-n",

            "taipei.net.xml",

            "-r",

            "taipei_more.rou.xml",

            "-e",

            str(TRIP_END_S),

            "-p",

            str(TRIP_PERIOD_S),

            "--vehicle-class",

            "passenger",

            "--prefix",

            "EV",

            "--fringe-factor",

            str(TRIP_FRINGE_FACTOR),

            "--min-distance",

            str(TRIP_MIN_DISTANCE_M),

            "--min-success-rate",

            "0.5",

            "--validate",

        ],

        cwd=_SIM,

        check=True,

    )

    subprocess.run([sys.executable, "patch_taiwan_routes.py"], cwd=_SIM, check=True)





def main() -> None:

    rou = _SIM / "taipei.rou.xml"

    if not needs_rebuild(rou):

        print(

            f"taipei.rou.xml OK ({vehicle_count(rou)} vehicles, {TRIP_END_S}s, "

            f"fringe={TRIP_FRINGE_FACTOR})"

        )

        return

    build_routes()

    print(f"Done — {vehicle_count(rou)} vehicles in taipei.rou.xml")





if __name__ == "__main__":

    main()

