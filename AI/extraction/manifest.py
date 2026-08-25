"""SQLite progress tracking for extraction runs (local non-synced path)."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Optional
from uuid import uuid4

from .paths import manifest_db


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Manifest:
    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or manifest_db()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _schema_sql(self) -> str:
        return """
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    phase TEXT NOT NULL,
                    status TEXT NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    last_error TEXT,
                    fetched_at TEXT,
                    output_path TEXT
                );

                CREATE TABLE IF NOT EXISTS refresh_log (
                    run_id TEXT PRIMARY KEY,
                    phase TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    ended_at TEXT,
                    cities_ok INTEGER DEFAULT 0,
                    cities_failed INTEGER DEFAULT 0,
                    cities_skipped INTEGER DEFAULT 0,
                    api_calls INTEGER DEFAULT 0,
                    notes TEXT
                );
                """

    def _reset_db(self) -> None:
        """Replace a corrupt DB with a fresh one."""
        if self.db_path.is_file():
            corrupt = self.db_path.with_name(
                f"{self.db_path.stem}_corrupt{self.db_path.suffix}"
            )
            try:
                if corrupt.is_file():
                    corrupt.unlink()
                self.db_path.replace(corrupt)
            except OSError:
                try:
                    self.db_path.unlink()
                except OSError:
                    self.db_path = self.db_path.with_name(
                        f"{self.db_path.stem}_{uuid4().hex[:8]}{self.db_path.suffix}"
                    )

    def _open_conn(self) -> sqlite3.Connection:
        try:
            conn = sqlite3.connect(self.db_path, timeout=30)
            conn.execute("PRAGMA journal_mode=DELETE")
            conn.execute("SELECT 1 FROM sqlite_master LIMIT 1")
            conn.row_factory = sqlite3.Row
            return conn
        except sqlite3.DatabaseError:
            self._reset_db()
            conn = sqlite3.connect(self.db_path, timeout=30)
            conn.execute("PRAGMA journal_mode=DELETE")
            conn.executescript(self._schema_sql())
            conn.row_factory = sqlite3.Row
            return conn

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        last_exc: Exception | None = None
        for attempt in range(2):
            conn: sqlite3.Connection | None = None
            try:
                conn = self._open_conn()
                yield conn
                conn.commit()
                return
            except sqlite3.DatabaseError as exc:
                last_exc = exc
                if attempt == 0:
                    self._reset_db()
                else:
                    raise
            finally:
                if conn is not None:
                    conn.close()
        if last_exc is not None:
            raise last_exc

    def _init_schema(self) -> None:
        with self._conn() as conn:
            conn.executescript(self._schema_sql())

    def get_task(self, task_id: str) -> Optional[dict[str, Any]]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM tasks WHERE task_id = ?", (task_id,)
            ).fetchone()
            return dict(row) if row else None

    def upsert_task(
        self,
        task_id: str,
        phase: str,
        status: str,
        *,
        output_path: str | None = None,
        last_error: str | None = None,
        increment_attempt: bool = False,
    ) -> None:
        fetched_at = _utc_now() if status == "success" else None
        with self._conn() as conn:
            existing = conn.execute(
                "SELECT attempts FROM tasks WHERE task_id = ?", (task_id,)
            ).fetchone()
            attempts = (existing["attempts"] if existing else 0) + (
                1 if increment_attempt else 0
            )
            conn.execute(
                """
                INSERT INTO tasks (task_id, phase, status, attempts, last_error, fetched_at, output_path)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(task_id) DO UPDATE SET
                    phase = excluded.phase,
                    status = excluded.status,
                    attempts = excluded.attempts,
                    last_error = excluded.last_error,
                    fetched_at = COALESCE(excluded.fetched_at, tasks.fetched_at),
                    output_path = COALESCE(excluded.output_path, tasks.output_path)
                """,
                (task_id, phase, status, attempts, last_error, fetched_at, output_path),
            )

    def reset_stale_in_progress(self, phase: str, older_than_minutes: int = 30) -> int:
        """Mark abandoned in_progress tasks as pending (crash recovery)."""
        with self._conn() as conn:
            cur = conn.execute(
                "UPDATE tasks SET status = 'pending' WHERE phase = ? AND status = 'in_progress'",
                (phase,),
            )
            return cur.rowcount

    def count_by_phase_status(self, phase: str) -> dict[str, int]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT status, COUNT(*) AS n FROM tasks WHERE phase = ? GROUP BY status",
                (phase,),
            ).fetchall()
            return {row["status"]: row["n"] for row in rows}

    def start_run(self, phase: str) -> str:
        run_id = str(uuid4())
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO refresh_log (run_id, phase, started_at)
                VALUES (?, ?, ?)
                """,
                (run_id, phase, _utc_now()),
            )
        return run_id

    def finish_run(
        self,
        run_id: str,
        *,
        cities_ok: int,
        cities_failed: int,
        cities_skipped: int,
        api_calls: int,
        notes: str | None = None,
    ) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                UPDATE refresh_log
                SET ended_at = ?, cities_ok = ?, cities_failed = ?,
                    cities_skipped = ?, api_calls = ?, notes = ?
                WHERE run_id = ?
                """,
                (
                    _utc_now(),
                    cities_ok,
                    cities_failed,
                    cities_skipped,
                    api_calls,
                    notes,
                    run_id,
                ),
            )

    def last_run(self, phase: str) -> Optional[dict[str, Any]]:
        with self._conn() as conn:
            row = conn.execute(
                """
                SELECT * FROM refresh_log
                WHERE phase = ?
                ORDER BY started_at DESC
                LIMIT 1
                """,
                (phase,),
            ).fetchone()
            return dict(row) if row else None
