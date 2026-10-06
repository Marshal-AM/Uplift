from pathlib import Path

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

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


def connection():
    return _pool.connection()


def fetch_one(query: str, *params):
    with _pool.connection() as conn:
        return conn.execute(query, params).fetchone()


def execute(query: str, *params) -> None:
    with _pool.connection() as conn:
        conn.execute(query, params)
