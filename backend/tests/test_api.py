"""Offline tests: no Gemini calls, OSRM replaced by the straight-line estimate.

Run from the repo root:  backend/.venv/Scripts/python -m pytest backend/tests -q
"""

import pytest

from backend import algorithm, assistant, config, routing
from backend.server import _hits, app

TAIPEI_MAIN = {"lat": 25.0478, "lng": 121.5170}


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def fake_road(origin, dests):
        from backend.geo import haversine_km

        m = [haversine_km(origin[0], origin[1], a, b) * 1300 for a, b in dests]
        return m, [x / 10 for x in m], "estimate"

    monkeypatch.setattr(routing, "road_distances", fake_road)
    monkeypatch.setattr(algorithm, "road_distances", fake_road)
    _hits.clear()


@pytest.fixture
def client():
    return app.test_client()


def test_health(client):
    body = client.get("/api/health").get_json()
    assert body["ok"] and body["stations"] == 3008 and body["wait_model"] == "placeholder"


def test_range_matches_algorithm_formula():
    r = algorithm.estimate_range(80)
    assert r["max_range_km"] == pytest.approx(0.85 * (48000 - 0.1) / 180, abs=0.1)


def test_recommend_ranks_reachable_stations(client):
    body = client.post("/api/recommend", json={**TAIPEI_MAIN, "battery_pct": 80}).get_json()
    assert body["ok"] and 1 <= len(body["results"]) <= 5
    scores = [r["total_score"] for r in body["results"]]
    assert scores == sorted(scores, reverse=True)
    assert all(r["reachable"] and r["wait"]["placeholder"] for r in body["results"])
    assert [r["rank"] for r in body["results"]] == list(range(1, len(scores) + 1))


def test_placeholder_wait_does_not_change_order():
    rec = algorithm.recommend(TAIPEI_MAIN["lat"], TAIPEI_MAIN["lng"], 80, limit=25)
    assert {r["normalized"]["wait"] for r in rec["all_results"]} == {1.0}


def test_city_out_of_range(client):
    body = client.post(
        "/api/recommend", json={**TAIPEI_MAIN, "battery_pct": 5, "city": "高雄"}
    ).get_json()
    assert body["ok"] is False and body["city"] == "Kaohsiung"


@pytest.mark.parametrize(
    "payload",
    [{}, {"lat": "x", "lng": 121, "battery_pct": 50}, {**TAIPEI_MAIN, "battery_pct": 150}],
)
def test_recommend_rejects_bad_input(client, payload):
    assert client.post("/api/recommend", json=payload).status_code == 400


def test_station_details(client):
    body = client.get("/api/stations/TPE1733").get_json()
    assert body["ok"] and body["station"]["city"] == "Taipei"
    assert client.get("/api/stations/nope").status_code == 404


def test_chat_without_gemini_key_is_503(client, monkeypatch):
    monkeypatch.setattr(config, "GEMINI_API_KEY", "")
    monkeypatch.setattr(assistant, "_client", None)
    resp = client.post("/api/chat", json={**TAIPEI_MAIN, "battery_pct": 50, "message": "hi"})
    assert resp.status_code == 503


def test_explain_falls_back_to_rules(client, monkeypatch):
    monkeypatch.setattr(config, "GEMINI_API_KEY", "")
    monkeypatch.setattr(assistant, "_client", None)
    body = client.post(
        "/api/explain", json={**TAIPEI_MAIN, "battery_pct": 50, "station_id": "TPE1733"}
    ).get_json()
    assert body["ok"] and body["source"] == "rules" and "TPE1733" not in body["explanation"]


def test_tools_read_database():
    ctx = assistant.ChatContext(lat=TAIPEI_MAIN["lat"], lng=TAIPEI_MAIN["lng"], battery_pct=50)
    tools = {f.__name__: f for f in assistant.make_tools(ctx)}
    assert tools["find_stations"](city="Kaohsiung")["total_matches"] == 522
    assert tools["nearby_stations"](radius_km=2)["stations"]
    assert tools["recommend_stations"]()["results"]
    assert tools["station_details"]("TPE1733")["city"] == "Taipei"
    assert tools["battery_range"](battery_pct=50)["max_range_km"] > 100
    assert ctx.last_list[0]["id"] == "TPE1733"


def test_api_key_and_rate_limit(client, monkeypatch):
    monkeypatch.setattr(config, "APP_API_KEY", "secret")
    payload = {**TAIPEI_MAIN, "battery_pct": 50}
    assert client.post("/api/recommend", json=payload).status_code == 401
    ok = client.post("/api/recommend", json=payload, headers={"X-API-Key": "secret"})
    assert ok.status_code == 200
    monkeypatch.setattr(config, "GEMINI_API_KEY", "")
    statuses = [
        client.post("/api/chat", json={**payload, "message": "hi"}, headers={"X-API-Key": "secret"}).status_code
        for _ in range(config.RATE_LIMIT_AI_PER_MIN + 1)
    ]
    assert statuses[-1] == 429
