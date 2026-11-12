"""Application configuration — paths, demo date, seed, threads."""

from __future__ import annotations

import os
from pathlib import Path

# Cap native BLAS threads before heavy numeric imports elsewhere
_THREADS = int(os.environ.get("STOCKPILOT_THREADS", "2"))
os.environ.setdefault("OMP_NUM_THREADS", str(_THREADS))
os.environ.setdefault("OPENBLAS_NUM_THREADS", str(_THREADS))
os.environ.setdefault("MKL_NUM_THREADS", str(_THREADS))
os.environ.setdefault("NUMEXPR_NUM_THREADS", str(_THREADS))

BACKEND_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_ROOT.parent


class Settings:
    app_name: str = "StockPilot"
    app_version: str = "3.1.0"
    seed: int = int(os.environ.get("STOCKPILOT_SEED", "42"))
    threads: int = _THREADS
    demo_date: str = os.environ.get("STOCKPILOT_DEMO_DATE", "2026-11-01")
    demo_mode: bool = os.environ.get("STOCKPILOT_DEMO_MODE", "true").lower() in {
        "1",
        "true",
        "yes",
    }
    db_path: Path = Path(
        os.environ.get("STOCKPILOT_DB_PATH", str(BACKEND_ROOT / "data" / "stockpilot.db"))
    )
    model_dir: Path = Path(
        os.environ.get("STOCKPILOT_MODEL_DIR", str(BACKEND_ROOT / "artifacts" / "models"))
    )
    eval_dir: Path = BACKEND_ROOT / "artifacts" / "evaluation"
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    def ensure_dirs(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.model_dir.mkdir(parents=True, exist_ok=True)
        self.eval_dir.mkdir(parents=True, exist_ok=True)


settings = Settings()
