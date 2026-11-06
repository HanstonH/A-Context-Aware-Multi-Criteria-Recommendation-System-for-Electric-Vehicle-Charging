"""HTTP-level tests for the FastAPI service (app.py) using FastAPI's TestClient."""
import pytest
from fastapi.testclient import TestClient

import app as app_module


@pytest.fixture
def client():
    return TestClient(app_module.app)


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_recommend_returns_ranked_list(client, fake_google):
    resp = client.post("/recommend", json={"lat": 25.0330, "lng": 121.5654, "battery_percent": 40})
    assert resp.status_code == 200
    recs = resp.json()["recommendations"]
    assert 1 <= len(recs) <= 10
    scores = [r["topsis_score"] for r in recs]
    assert scores == sorted(scores, reverse=True)
    assert {"StationID", "station_name", "lat", "lon", "distance", "nearby_pois"} <= recs[0].keys()


@pytest.mark.parametrize("battery", [-1, 101])
def test_recommend_validates_battery_range(client, battery):
    resp = client.post("/recommend", json={"lat": 25.0, "lng": 121.5, "battery_percent": battery})
    assert resp.status_code == 422


def test_recommend_requires_coordinates(client):
    resp = client.post("/recommend", json={"battery_percent": 50})
    assert resp.status_code == 422


def test_recommend_rejects_unknown_city(client):
    resp = client.post("/recommend", json={"lat": 25.0, "lng": 121.5, "battery_percent": 50, "city": "Tokyo"})
    assert resp.status_code == 400
    assert "Unknown city" in resp.json()["detail"]


def test_recommend_returns_500_when_no_station_is_reachable(client, fake_google):
    resp = client.post("/recommend", json={"lat": 25.0330, "lng": 121.5654, "battery_percent": 0})
    assert resp.status_code == 500
    assert "No station reachable" in resp.json()["detail"]


def test_stations_for_city(client):
    resp = client.get("/stations/Taipei")
    assert resp.status_code == 200
    stations = resp.json()["stations"]
    assert len(stations) > 100
    assert {"StationID", "lat", "lon", "available_points", "cost"} <= stations[0].keys()


def test_stations_unknown_city(client):
    assert client.get("/stations/Atlantis").status_code == 400


def test_pois_success(client, monkeypatch):
    class FakePOI:
        def call_API(self, lat, lng):
            return {"places": [{"id": "p1", "location": {"latitude": lat, "longitude": lng}}]}
    monkeypatch.setattr(app_module, "Get_POI", FakePOI)
    resp = client.get("/pois", params={"lat": 25.03, "lng": 121.56})
    assert resp.status_code == 200
    assert resp.json()["pois"][0]["id"] == "p1"


def test_pois_upstream_failure_is_502(client, monkeypatch):
    class FailingPOI:
        def call_API(self, lat, lng):
            return None
    monkeypatch.setattr(app_module, "Get_POI", FailingPOI)
    assert client.get("/pois", params={"lat": 25.03, "lng": 121.56}).status_code == 502


def test_pois_validates_coordinates(client):
    assert client.get("/pois", params={"lat": 200, "lng": 121.56}).status_code == 422


def test_route_success(client, monkeypatch):
    monkeypatch.setattr(app_module, "get_route_points", lambda a, b: [[25.0, 121.5], [25.1, 121.6]])
    resp = client.get("/route", params={"from_lat": 25.0, "from_lng": 121.5, "to_lat": 25.1, "to_lng": 121.6})
    assert resp.status_code == 200
    assert resp.json() == {"route": [[25.0, 121.5], [25.1, 121.6]]}


def test_route_not_found(client, monkeypatch):
    monkeypatch.setattr(app_module, "get_route_points", lambda a, b: None)
    resp = client.get("/route", params={"from_lat": 25.0, "from_lng": 121.5, "to_lat": 25.1, "to_lng": 121.6})
    assert resp.status_code == 404


def test_route_missing_params(client):
    assert client.get("/route", params={"from_lat": 25.0}).status_code == 422
