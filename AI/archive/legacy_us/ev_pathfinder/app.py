"""Flask web application for the EV-Pathfinder Orchestrator."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, render_template, request

from .battery import parse_user_battery
from .orchestrator import EVPathfinderOrchestrator

app = Flask(
    __name__,
    template_folder=str(Path(__file__).parent / "templates"),
    static_folder=str(Path(__file__).parent / "static"),
)

orchestrator: EVPathfinderOrchestrator | None = None


def _get_orchestrator() -> EVPathfinderOrchestrator:
    global orchestrator
    if orchestrator is None:
        orchestrator = EVPathfinderOrchestrator()
    return orchestrator


# ── Pages ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


# ── REST API ─────────────────────────────────────────────────────────────────

@app.route("/api/stations", methods=["GET"])
def api_stations():
    orch = _get_orchestrator()
    geojson = orch.registry.to_geojson()
    return jsonify(geojson)


@app.route("/api/predict", methods=["POST"])
def api_predict():
    data = request.get_json(force=True)
    user_lat = data.get("user_lat")
    user_lon = data.get("user_lon")
    mode = data.get("mode", "single")          # "single" or "find_best"
    station_mac = data.get("station_mac", "")
    selected_time_str = data.get("selected_time")  # ISO-8601 string or None

    if user_lat is None or user_lon is None:
        return jsonify({"success": False, "message": "user_lat and user_lon are required."}), 400

    try:
        ev_battery = parse_user_battery(data, required=True)
    except ValueError as exc:
        return jsonify({"success": False, "message": str(exc)}), 400

    try:
        user_lat = float(user_lat)
        user_lon = float(user_lon)
    except (TypeError, ValueError):
        return jsonify({"success": False, "message": "Invalid coordinate values."}), 400

    selected_time = None
    if selected_time_str:
        try:
            selected_time = datetime.fromisoformat(selected_time_str)
        except (ValueError, TypeError):
            return jsonify({"success": False, "message": "Invalid selected_time format. Use ISO-8601."}), 400

    orch = _get_orchestrator()

    if mode == "find_best":
        result = orch.find_best_station(user_lat, user_lon, selected_time, ev_battery=ev_battery)
    else:
        if not station_mac:
            return jsonify({"success": False, "message": "station_mac is required in single mode."}), 400
        result = orch.evaluate_single(
            user_lat, user_lon, station_mac, selected_time, ev_battery=ev_battery,
        )

    return jsonify({
        "success": result.success,
        "message": result.message,
        "best": result.best,
        "all_results": result.all_results,
        "user_location": result.user_location,
        "range_estimate": result.range_estimate,
        "stations_excluded_by_range": result.stations_excluded_by_range,
    })


@app.route("/api/health", methods=["GET"])
def api_health():
    orch = _get_orchestrator()
    return jsonify({
        "status": "ok",
        "stations_loaded": len(orch.registry.all_stations),
        "model_a_loaded": orch.model_a.loaded,
        "model_b_loaded": orch.model_b.loaded,
    })


# ── Entry point ──────────────────────────────────────────────────────────────

def main():
    print("\n============================================")
    print("  EV-Pathfinder Orchestrator - Palo Alto")
    print("============================================\n")
    _get_orchestrator()  # warm up on startup
    app.run(host="0.0.0.0", port=5000, debug=True)


if __name__ == "__main__":
    main()
