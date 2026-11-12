"""Base agent contract and shared training helpers."""

from __future__ import annotations

import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import numpy as np
import sqlite3

from app.core.config import settings
from app.db import repositories as repo
from app.ml import artifacts, features, metrics, splits
from app.ml.features import FEATURE_COLUMNS, feature_matrix, load_sales_dataframe

PROVENANCE_SYNTHETIC = "SYNTHETIC_DEMO"
PROVENANCE_SIMULATED = "SIMULATED_SUPPLY"


@dataclass
class AgentResult:
    agent_name: str
    model_version: str
    provenance: str
    output: dict[str, Any] = field(default_factory=dict)
    metrics: dict[str, float | None] = field(default_factory=dict)
    duration_ms: float = 0.0
    status: str = "ok"
    error: str | None = None


@dataclass
class TrainContext:
    conn: sqlite3.Connection
    fast: bool = False
    threads: int = 2
    version: str = "1.0.0"
    provenance: str = PROVENANCE_SYNTHETIC


def default_version() -> str:
    return datetime.now(timezone.utc).strftime("v%Y%m%d.%H%M")


def n_jobs(threads: int | None = None) -> int:
    t = threads if threads is not None else settings.threads
    return max(1, min(2, int(t)))


class BaseAgent(ABC):
    name: str = "base"
    provenance: str = PROVENANCE_SYNTHETIC

    def __init__(self) -> None:
        self.model: Any = None
        self.metadata: dict[str, Any] = {}
        self.version: str | None = None

    @abstractmethod
    def fit(self, ctx: TrainContext) -> dict[str, float | None]:
        ...

    @abstractmethod
    def predict_one(self, conn: sqlite3.Connection, product_id: int, **kwargs: Any) -> dict:
        ...

    def train(self, ctx: TrainContext) -> AgentResult:
        t0 = time.perf_counter()
        ctx.version = ctx.version or default_version()
        try:
            fit_metrics = self.fit(ctx)
            artifact_file, _ = artifacts.save_artifact(
                self.name,
                ctx.version,
                self.model,
                {
                    **self.metadata,
                    "feature_columns": self.metadata.get("feature_columns"),
                    "metrics": fit_metrics,
                },
            )
            repo.upsert_model_version(
                ctx.conn,
                {
                    "agent_name": self.name,
                    "version": ctx.version,
                    "artifact_file": str(artifact_file),
                    "training_source": ctx.provenance,
                    "trained_at": repo.utc_now(),
                    "metadata": {**self.metadata, "metrics": fit_metrics},
                },
            )
            self.version = ctx.version
            ms = (time.perf_counter() - t0) * 1000
            return AgentResult(
                agent_name=self.name,
                model_version=ctx.version,
                provenance=ctx.provenance,
                output={"trained": True},
                metrics=fit_metrics,
                duration_ms=ms,
            )
        except Exception as exc:
            ms = (time.perf_counter() - t0) * 1000
            return AgentResult(
                agent_name=self.name,
                model_version=ctx.version or "unknown",
                provenance=ctx.provenance,
                status="error",
                error=str(exc),
                duration_ms=ms,
            )

    def load(self, version: str | None = None) -> None:
        ver = version or artifacts.latest_version(self.name)
        if not ver:
            raise FileNotFoundError(f"No artifact for {self.name}")
        self.model, self.metadata = artifacts.load_artifact(self.name, ver)
        self.version = ver

    def predict(self, conn: sqlite3.Connection, product_id: int, **kwargs: Any) -> AgentResult:
        t0 = time.perf_counter()
        if self.model is None:
            try:
                self.load()
            except FileNotFoundError as exc:
                return AgentResult(
                    agent_name=self.name,
                    model_version="none",
                    provenance=self.provenance,
                    status="error",
                    error=str(exc),
                    duration_ms=(time.perf_counter() - t0) * 1000,
                )
        try:
            out = self.predict_one(conn, product_id, **kwargs)
            ms = (time.perf_counter() - t0) * 1000
            return AgentResult(
                agent_name=self.name,
                model_version=self.version or "unknown",
                provenance=kwargs.get("provenance", self.provenance),
                output=out,
                duration_ms=ms,
            )
        except Exception as exc:
            return AgentResult(
                agent_name=self.name,
                model_version=self.version or "unknown",
                provenance=self.provenance,
                status="error",
                error=str(exc),
                duration_ms=(time.perf_counter() - t0) * 1000,
            )


def panel_for_training(conn: sqlite3.Connection) -> splits.TemporalSplit:
    sales = load_sales_dataframe(conn)
    feat = features.build_panel_features(sales)
    return splits.split_panel(feat)


def eval_regression(agent_name: str, y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    return metrics.pack_metrics(
        mae=metrics.mae(y_true, y_pred),
        rmse=metrics.rmse(y_true, y_pred),
        wape=metrics.wape(y_true, y_pred),
    )


def new_trace_id() -> str:
    return str(uuid.uuid4())
