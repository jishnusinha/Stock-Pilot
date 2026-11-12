"""FastAPI dependencies."""

from __future__ import annotations

from collections.abc import Generator

from app.db.connection import connect


def get_db() -> Generator:
    conn = connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
