from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.core.config import settings
from app.db.connection import connect
from app.db.migrations import migrate
from app.services.seed import seed_demo


@pytest.fixture()
def tmp_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db = tmp_path / "test.db"
    monkeypatch.setattr(settings, "db_path", db)
    monkeypatch.setattr(settings, "model_dir", tmp_path / "models")
    settings.ensure_dirs()
    os.environ["STOCKPILOT_DB_PATH"] = str(db)
    conn = connect(db)
    migrate(conn)
    yield conn
    conn.close()
