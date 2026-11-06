"""Run history and audit log in SQLite on the VM's disk (mount /data as a volume to keep it)."""
from __future__ import annotations

import json
import os
import sqlite3
import secrets
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

_lock = threading.Lock()


@contextmanager
def _db():
    """Open, commit, close. (`with sqlite3.connect()` commits but never closes the handle.)"""
    path = Path(os.environ.get("DATA_DIR", "data")) / "recon.db"
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.execute("create table if not exists runs (id text primary key, created text, parent text, status text, body text)")
    con.execute("create table if not exists audit (id integer primary key autoincrement, run_id text, ts text, "
                "action text, detail text)")
    try:
        with con:
            yield con
    finally:
        con.close()


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")  # same format as SQLite datetime()


def save_run(result: dict, parent: str | None) -> str:
    run_id = secrets.token_urlsafe(12)  # unguessable: runs hold uploaded financial rows and there is no listing
    keep = f"-{float(os.environ.get('RETENTION_HOURS', '24'))} hours"
    with _lock, _db() as con:
        # Uploaded rows are kept only as long as a review session needs them.
        con.execute("delete from audit where run_id in (select id from runs where created < datetime('now', ?))", (keep,))
        con.execute("delete from runs where created < datetime('now', ?)", (keep,))
        con.execute("insert into runs values (?,?,?,?,?)", (run_id, _now(), parent, result.get("status"), json.dumps(result)))
        con.execute("insert into audit (run_id, ts, action, detail) values (?,?,?,?)",
                    (run_id, _now(), "run", json.dumps({"status": result.get("status"), "parent": parent})))
    return run_id


def get_run(run_id: str) -> dict | None:
    with _db() as con:
        row = con.execute("select body from runs where id=?", (run_id,)).fetchone()
    return json.loads(row[0]) if row else None


def record(run_id: str, action: str, detail: dict) -> None:
    with _lock, _db() as con:
        con.execute("insert into audit (run_id, ts, action, detail) values (?,?,?,?)",
                    (run_id, _now(), action, json.dumps(detail)))


def audit(run_id: str) -> list[dict]:
    with _db() as con:
        rows = con.execute("select ts, action, detail from audit where run_id=? order by id", (run_id,)).fetchall()
    return [{"ts": r[0], "action": r[1], "detail": json.loads(r[2])} for r in rows]


def update_run(run_id: str, result: dict) -> None:
    with _lock, _db() as con:
        con.execute("update runs set body=? where id=?", (json.dumps(result), run_id))
