"""Accounts: register, log in, token check. Each test uses its own users database."""

import pytest

from backend import auth, config
from backend.server import _hits, app

USER = {"email": "Driver@Example.com", "password": "correct-horse-1", "name": "Driver"}


@pytest.fixture(autouse=True)
def users_db(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "USERS_DB_PATH", tmp_path / "users.db")
    monkeypatch.setattr(config, "SECRET_KEY", "")  # exercise the generated key file
    _hits.clear()


@pytest.fixture
def client():
    return app.test_client()


def register(client, **overrides):
    return client.post("/api/auth/register", json={**USER, **overrides})


def test_register_then_login_then_me(client):
    reg = register(client)
    assert reg.status_code == 201
    body = reg.get_json()
    assert body["user"]["email"] == "driver@example.com" and body["user"]["name"] == "Driver"
    assert "password_hash" not in body["user"] and body["token"]

    login = client.post("/api/auth/login", json={"email": " DRIVER@example.com ", "password": USER["password"]})
    assert login.status_code == 200
    token = login.get_json()["token"]

    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200 and me.get_json()["user"]["email"] == "driver@example.com"


def test_password_is_hashed_not_stored(client):
    register(client)
    import sqlite3

    row = sqlite3.connect(config.USERS_DB_PATH).execute("SELECT password_hash FROM users").fetchone()
    assert USER["password"] not in row[0] and row[0].startswith(("scrypt:", "pbkdf2:"))


def test_duplicate_email_is_rejected(client):
    register(client)
    dup = register(client, email="driver@EXAMPLE.com")
    assert dup.status_code == 409


@pytest.mark.parametrize(
    "overrides", [{"email": "not-an-email"}, {"password": "short"}, {"password": "x" * 129}, {"email": ""}]
)
def test_register_validation(client, overrides):
    assert register(client, **overrides).status_code == 400


def test_unknown_email_and_wrong_password_look_the_same(client):
    register(client)
    wrong_pw = client.post("/api/auth/login", json={"email": USER["email"], "password": "wrong-password"})
    unknown = client.post("/api/auth/login", json={"email": "nobody@example.com", "password": "whatever-123"})
    assert wrong_pw.status_code == unknown.status_code == 401
    assert wrong_pw.get_json()["error"] == unknown.get_json()["error"]


def test_bad_or_missing_token(client):
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/auth/me", headers={"Authorization": "Bearer forged.token"}).status_code == 401


def test_token_expires(client, monkeypatch):
    token = register(client).get_json()["token"]
    monkeypatch.setattr(config, "AUTH_TOKEN_DAYS", -1)
    assert auth.user_from_token(token) is None


def test_generated_secret_key_is_reused(client):
    token = register(client).get_json()["token"]
    key_file = config.USERS_DB_PATH.parent / ".auth_secret_key"
    assert key_file.is_file()
    # A second call (another worker, or after a restart) reads the same key back.
    assert auth.user_from_token(token)["email"] == "driver@example.com"


def test_login_is_rate_limited(client):
    statuses = [
        client.post("/api/auth/login", json={"email": "a@b.co", "password": "wrong-password"}).status_code
        for _ in range(config.RATE_LIMIT_AUTH_PER_MIN + 1)
    ]
    assert statuses[-1] == 429 and set(statuses[:-1]) == {401}
