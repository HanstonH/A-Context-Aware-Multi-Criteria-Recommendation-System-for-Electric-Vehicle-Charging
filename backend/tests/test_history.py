"""Search history: saved per user, newest first, deduplicated, capped, login required."""

import sqlite3

import pytest

from backend import config
from backend.server import _hits, app


@pytest.fixture(autouse=True)
def users_db(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "USERS_DB_PATH", tmp_path / "users.db")
    monkeypatch.setattr(config, "SECRET_KEY", "test-key")
    _hits.clear()


@pytest.fixture
def client():
    return app.test_client()


def login(client, email="driver@example.com"):
    resp = client.post("/api/auth/register", json={"email": email, "password": "correct-horse-1"})
    return {"Authorization": f"Bearer {resp.get_json()['token']}"}


def add(client, headers, **entry):
    return client.post("/api/history", json=entry, headers=headers)


def items(client, headers, **params):
    return client.get("/api/history", query_string=params, headers=headers).get_json()["history"]


def test_needs_login(client):
    assert client.get("/api/history").status_code == 401
    assert client.post("/api/history", json={"kind": "text", "query": "x"}).status_code == 401
    assert client.delete("/api/history").status_code == 401
    bad = {"Authorization": "Bearer not-a-token"}
    assert client.get("/api/history", headers=bad).status_code == 401


def test_add_and_list_newest_first(client):
    h = login(client)
    first = add(client, h, kind="text", query="  台北   車站 ")
    assert first.status_code == 201
    assert first.get_json()["entry"]["query"] == "台北 車站"  # spaces tidied
    add(client, h, kind="station", station_id="TPE1733", query="府前廣場站")
    add(client, h, kind="range", lat=25.03, lng=121.56, battery_pct=40)

    got = items(client, h)
    assert [e["kind"] for e in got] == ["range", "station", "text"]
    assert got[0]["battery_pct"] == 40 and got[1]["station_id"] == "TPE1733"
    assert len(items(client, h, limit=1)) == 1


def test_repeat_moves_to_top_instead_of_copying(client):
    h = login(client)
    add(client, h, kind="text", query="Taipei 101")
    add(client, h, kind="text", query="Songshan")
    add(client, h, kind="text", query="taipei 101")  # same search, different case
    add(client, h, kind="station", station_id="A")
    add(client, h, kind="station", station_id="A")
    add(client, h, kind="range", lat=25, lng=121, battery_pct=30)
    add(client, h, kind="range", lat=25.1, lng=121.1, battery_pct=20)  # only the latest range kept

    got = items(client, h)
    assert [(e["kind"], e["query"] or e["station_id"] or e["battery_pct"]) for e in got] == [
        ("range", 20),
        ("station", "A"),
        ("text", "taipei 101"),
        ("text", "Songshan"),
    ]


def test_only_newest_entries_are_kept(client, monkeypatch):
    monkeypatch.setattr(config, "HISTORY_MAX", 3)
    h = login(client)
    for i in range(5):
        add(client, h, kind="text", query=f"q{i}")
    assert [e["query"] for e in items(client, h)] == ["q4", "q3", "q2"]


@pytest.mark.parametrize(
    "entry",
    [
        {},
        {"kind": "nope", "query": "x"},
        {"kind": "text"},
        {"kind": "text", "query": "   "},
        {"kind": "station"},
        {"kind": "range", "lat": 25, "lng": 121},
        {"kind": "text", "query": "x", "lat": 25},  # lat without lng
        {"kind": "text", "query": "x", "lat": 95, "lng": 121},
        {"kind": "range", "lat": 25, "lng": 121, "battery_pct": "full"},
    ],
)
def test_bad_entries_are_rejected(client, entry):
    h = login(client)
    assert add(client, h, **entry).status_code == 400
    assert items(client, h) == []


def test_users_only_see_and_delete_their_own(client):
    a, b = login(client, "a@example.com"), login(client, "b@example.com")
    entry_id = add(client, a, kind="text", query="mine").get_json()["entry"]["id"]

    assert items(client, b) == []
    assert client.delete(f"/api/history/{entry_id}", headers=b).status_code == 404
    assert client.delete("/api/history", headers=b).get_json()["deleted"] == 0
    assert len(items(client, a)) == 1

    assert client.delete(f"/api/history/{entry_id}", headers=a).status_code == 200
    assert items(client, a) == []


def test_clear_all(client):
    h = login(client)
    add(client, h, kind="text", query="one")
    add(client, h, kind="destination", query="two")
    assert client.delete("/api/history", headers=h).get_json()["deleted"] == 2
    assert items(client, h) == []


def test_history_is_deleted_with_the_user(client):
    h = login(client)
    add(client, h, kind="text", query="x")
    conn = sqlite3.connect(config.USERS_DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    with conn:
        conn.execute("DELETE FROM users")
    assert conn.execute("SELECT count(*) FROM search_history").fetchone()[0] == 0
    conn.close()
