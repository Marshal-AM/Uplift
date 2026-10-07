import json
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from uplift_core import trace

from .config import settings

MIGRATIONS = Path(__file__).resolve().parents[2] / "migrations"
_pool: ConnectionPool | None = None


def open_pool() -> None:
    global _pool
    _pool = ConnectionPool(settings().database_url, kwargs={"row_factory": dict_row}, min_size=1, max_size=10)
    _pool.wait()
    with _pool.connection() as conn:
        for sql in sorted(MIGRATIONS.glob("*.sql")):
            conn.execute(sql.read_text())


def close_pool() -> None:
    if _pool:
        _pool.close()


def try_lease(name: str) -> psycopg.Connection | None:
    """A session-level advisory lock on its own connection: held until that connection closes (including when the
    process dies), so a crashed holder never blocks the next one."""
    conn = psycopg.connect(settings().database_url, autocommit=True)
    if conn.execute("select pg_try_advisory_lock(hashtext(%s))", (name,)).fetchone()[0]:
        return conn
    conn.close()
    return None


def lease_alive(conn: psycopg.Connection) -> bool:
    try:
        conn.execute("select 1")
        return True
    except psycopg.Error:
        return False


def one(query: str, *params) -> dict | None:
    with _pool.connection() as conn:
        return conn.execute(query, params).fetchone()


def all_(query: str, *params) -> list[dict]:
    with _pool.connection() as conn:
        return conn.execute(query, params).fetchall()


def execute(query: str, *params) -> None:
    with _pool.connection() as conn:
        conn.execute(query, params)


# --- run journal -------------------------------------------------------------------------------

def get_run(task_id: str) -> dict | None:
    return one("select * from runs where task_id = %s", task_id)


PHASES = {  # run journal phase → what the merchant would call it
    "start": "Starting", "intake": "Reading the brief", "auth_wait": "Waiting for store connection",
    "input_wait": "Waiting for the merchant's answer", "plan": "Planning", "quote_wait": "Waiting for plan approval",
    "pay": "Requesting payment", "execute": "Agents at work", "verify": "Chainlink verification",
    "funds_wait": "Waiting for the escrow lock", "merge": "Merging the team's changes", "propose": "Preparing approval",
    "approval": "Preparing approval", "approval_wait": "Waiting for the merchant's approval",
    "publish": "Chainlink is publishing", "report": "After-report", "deliver": "Delivering",
    "done": "Completed", "closed": "Closed", "failed": "Failed",
}
_phase: dict[str, str] = {}  # last phase traced per Task


def save_run(task_id: str, coworker: str, phase: str, state: dict[str, Any]) -> None:
    if _phase.get(task_id) != phase:
        _phase[task_id] = phase
        trace.emit("Uplift Worker", PHASES.get(phase, phase), f"journaled · phase `{phase}`", task=task_id,
                   agent=coworker, kind="phase", status="fail" if phase == "failed" else "ok", meta={"phase": phase})
    execute(
        """insert into runs (task_id, coworker, phase, state) values (%s, %s, %s, %s)
           on conflict (task_id) do update set phase = excluded.phase, state = excluded.state, updated_at = now()""",
        task_id, coworker, phase, json.dumps(state),
    )


def cursor(coworker: str) -> str | None:
    row = one("select event_id from cursors where coworker = %s", coworker)
    return row["event_id"] if row else None


def set_cursor(coworker: str, event_id: str) -> None:
    execute("insert into cursors values (%s, %s) on conflict (coworker) do update set event_id = excluded.event_id",
            coworker, event_id)


# --- live trace ---------------------------------------------------------------------------------

TRACE_COLUMNS = ("at", "task_id", "agent", "service", "step", "detail", "status", "ms", "span", "kind", "meta")


def insert_trace(events: list[dict]) -> None:
    rows = [(e["at"], e["task"], e.get("agent"), e["service"], e["step"], e.get("detail") or "", e.get("status") or "ok",
             e.get("ms"), e.get("span"), e.get("kind"), json.dumps(e["meta"]) if e.get("meta") else None)
            for e in events if e.get("task") and e.get("service") and e.get("step")]
    if not rows:
        return
    with _pool.connection() as conn, conn.cursor() as cur:
        cur.executemany("insert into trace_events (at, task_id, agent, service, step, detail, status, ms, span, kind, "
                        "meta) values (to_timestamp(%s), %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)", rows)
