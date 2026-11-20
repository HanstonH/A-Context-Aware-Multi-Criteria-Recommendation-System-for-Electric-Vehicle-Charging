"""User accounts: register, log in, and check a login token.

Accounts live in their own SQLite file (``config.USERS_DB_PATH``), separate from the
read-only station database, because this one is written to. In production put it on
a persistent volume, or every redeploy deletes all accounts.

Passwords are stored as salted hashes (werkzeug: scrypt). Login returns a signed
token (itsdangerous) that the client sends back as ``Authorization: Bearer <token>``.
Tokens are stateless: they expire after ``config.AUTH_TOKEN_DAYS`` and are signed
with ``config.SECRET_KEY`` (or a key generated once and stored next to the database).
"""

from __future__ import annotations

import os
import re
import secrets
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from werkzeug.security import check_password_hash, generate_password_hash

from . import config

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PASSWORD_MIN = 8
PASSWORD_MAX = 128
NAME_MAX = 80

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    name TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Each user's recent searches (history.py). Deleted with the user.
CREATE TABLE IF NOT EXISTS search_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    kind TEXT NOT NULL,
    query TEXT,
    station_id TEXT,
    lat REAL,
    lng REAL,
    battery_pct REAL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_search_history_user ON search_history(user_id, id);
"""

# Compared against when the email doesn't exist, so a login for an unknown email
# takes as long as one with a wrong password (no timing hint about which emails exist).
_DUMMY_HASH = generate_password_hash(secrets.token_hex(16))

_lock = threading.Lock()
_ready: set[Path] = set()


class AuthError(ValueError):
    """Bad input or failed login; the message is safe to show to the user."""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def _connect() -> sqlite3.Connection:
    path = Path(config.USERS_DB_PATH)
    with _lock:
        if path not in _ready:
            path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(path, timeout=10)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.executescript(_SCHEMA)
            conn.close()
            _ready.add(path)
    conn = sqlite3.connect(path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")  # so a user's history goes with the user
    return conn


@contextmanager
def _db():
    """Connection that commits on success, rolls back on error, and always closes."""
    conn = _connect()
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def _secret_key() -> str:
    """SECRET_KEY if set; otherwise a key created once beside the users database.

    Stored on the same volume, so tokens stay valid across restarts and are shared by
    every gunicorn worker. O_EXCL makes concurrent first starts agree on one key.
    """
    if config.SECRET_KEY:
        return config.SECRET_KEY
    key_file = Path(config.USERS_DB_PATH).parent / ".auth_secret_key"
    key_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(key_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        return key_file.read_text().strip()
    with os.fdopen(fd, "w") as f:
        key = secrets.token_urlsafe(48)
        f.write(key)
    return key


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(_secret_key(), salt="mapexplore-auth")


def _public(row: sqlite3.Row) -> dict:
    return {"id": row["id"], "email": row["email"], "name": row["name"], "created_at": row["created_at"]}


def _clean_email(email: object) -> str:
    value = str(email or "").strip().lower()
    if not value or len(value) > 254 or not EMAIL_RE.match(value):
        raise AuthError("Enter a valid email address.")
    return value


def issue_token(user_id: int) -> str:
    return _serializer().dumps({"uid": user_id})


def register(email: object, password: object, name: object = None) -> dict:
    email = _clean_email(email)
    password = str(password or "")
    if not PASSWORD_MIN <= len(password) <= PASSWORD_MAX:
        raise AuthError(f"Password must be {PASSWORD_MIN}-{PASSWORD_MAX} characters.")
    clean_name = str(name).strip()[:NAME_MAX] if name else None
    with _db() as conn:
        try:
            cur = conn.execute(
                "INSERT INTO users (email, password_hash, name) VALUES (?, ?, ?)",
                (email, generate_password_hash(password), clean_name or None),
            )
        except sqlite3.IntegrityError:
            raise AuthError("This email is already registered.", 409) from None
        row = conn.execute("SELECT * FROM users WHERE id = ?", (cur.lastrowid,)).fetchone()
    return {"user": _public(row), "token": issue_token(row["id"])}


def login(email: object, password: object) -> dict:
    password = str(password or "")
    try:
        email = _clean_email(email)
    except AuthError:
        email = ""
    with _db() as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone() if email else None
    # Same message and similar timing whether the email is unknown or the password is wrong.
    ok = check_password_hash(row["password_hash"] if row else _DUMMY_HASH, password)
    if not row or not ok or not password:
        raise AuthError("Incorrect email or password.", 401)
    return {"user": _public(row), "token": issue_token(row["id"])}


def user_from_token(token: str) -> dict | None:
    """The user for a valid, unexpired token; None otherwise (or if the user is gone)."""
    if not token:
        return None
    try:
        data = _serializer().loads(token, max_age=config.AUTH_TOKEN_DAYS * 86400)
    except (BadSignature, SignatureExpired):
        return None
    uid = data.get("uid") if isinstance(data, dict) else None
    if not isinstance(uid, int):
        return None
    with _db() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()
    return _public(row) if row else None
