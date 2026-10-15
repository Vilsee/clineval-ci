"""SQLite run history: append-only, hash-chained, plus baseline pointer and waivers."""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import time

GENESIS = "0" * 64


def _h(prev: str, payload: str) -> str:
    return hashlib.sha256((prev + payload).encode()).hexdigest()


class Store:
    def __init__(self, path: str):
        self.path = str(path)
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        with self._conn() as c:
            c.execute("""CREATE TABLE IF NOT EXISTS runs(
                id INTEGER PRIMARY KEY AUTOINCREMENT, created_at REAL, agent TEXT,
                suite_name TEXT, suite_hash TEXT, trials INTEGER, payload TEXT,
                prev_hash TEXT, hash TEXT)""")
            c.execute("CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT)")
            c.execute("""CREATE TABLE IF NOT EXISTS waivers(
                id INTEGER PRIMARY KEY AUTOINCREMENT, case_id TEXT, reason TEXT,
                approver TEXT, expires_at TEXT, created_at REAL)""")

    def _conn(self):
        return sqlite3.connect(self.path)

    # ---- runs -------------------------------------------------------------
    def save_run(self, run: dict, suite_name: str, suite_hash: str) -> int:
        payload = json.dumps(run)
        with self._conn() as c:
            row = c.execute("SELECT hash FROM runs ORDER BY id DESC LIMIT 1").fetchone()
            prev = row[0] if row else GENESIS
            cur = c.execute(
                "INSERT INTO runs(created_at, agent, suite_name, suite_hash, trials, payload, prev_hash, hash) VALUES (?,?,?,?,?,?,?,?)",
                (time.time(), run["resolved_agent"], suite_name, suite_hash, run["trials"], payload, prev, _h(prev, payload)))
            return cur.lastrowid

    def list_runs(self) -> list[dict]:
        with self._conn() as c:
            rows = c.execute("SELECT id, created_at, agent, suite_hash, trials, payload FROM runs ORDER BY id DESC LIMIT 100").fetchall()
        out = []
        for rid, ts, agent, sh, trials, payload in rows:
            out.append({"id": rid, "created_at": ts, "agent": agent, "suite_hash": sh, "trials": trials,
                        **json.loads(payload)["summary"]})
        return out

    def get_run(self, rid: int) -> dict | None:
        with self._conn() as c:
            row = c.execute("SELECT payload FROM runs WHERE id=?", (rid,)).fetchone()
        return json.loads(row[0]) if row else None

    # ---- baseline pointer -------------------------------------------------
    def set_baseline(self, rid: int) -> None:
        with self._conn() as c:
            c.execute("INSERT INTO meta(key, value) VALUES('baseline', ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (str(rid),))

    def get_baseline_id(self) -> int | None:
        with self._conn() as c:
            row = c.execute("SELECT value FROM meta WHERE key='baseline'").fetchone()
        return int(row[0]) if row else None

    # ---- tamper-evident audit chain ----------------------------------------
    def verify_chain(self) -> dict:
        with self._conn() as c:
            rows = c.execute("SELECT id, agent, created_at, payload, prev_hash, hash FROM runs ORDER BY id").fetchall()
        prev, entries = GENESIS, []
        for rid, agent, ts, payload, p, h in rows:
            ok = (p == prev) and (_h(prev, payload) == h)
            entries.append({"id": rid, "agent": agent, "created_at": ts, "hash": h[:12], "prev": p[:12], "ok": ok})
            if not ok:
                return {"valid": False, "checked": len(entries), "broken_at": rid, "entries": entries}
            prev = h
        return {"valid": True, "checked": len(entries), "broken_at": None, "entries": entries}

    # ---- waivers ----------------------------------------------------------
    def add_waiver(self, case_id: str, reason: str, approver: str, expires_at: str) -> int:
        with self._conn() as c:
            return c.execute("INSERT INTO waivers(case_id, reason, approver, expires_at, created_at) VALUES (?,?,?,?,?)",
                             (case_id, reason, approver, expires_at, time.time())).lastrowid

    def list_waivers(self) -> list[dict]:
        with self._conn() as c:
            rows = c.execute("SELECT id, case_id, reason, approver, expires_at FROM waivers ORDER BY id DESC").fetchall()
        return [dict(zip(("id", "case_id", "reason", "approver", "expires_at"), r)) for r in rows]

    def delete_waiver(self, wid: int) -> bool:
        with self._conn() as c:
            return c.execute("DELETE FROM waivers WHERE id=?", (wid,)).rowcount > 0
