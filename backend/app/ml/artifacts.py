"""Model artifact persistence (joblib + JSON metadata)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib

from app.core.config import settings


def artifact_path(agent_name: str, version: str) -> Path:
    settings.ensure_dirs()
    safe = agent_name.replace("/", "_")
    return settings.model_dir / safe / f"{version}.joblib"


def metadata_path(agent_name: str, version: str) -> Path:
    settings.ensure_dirs()
    safe = agent_name.replace("/", "_")
    return settings.model_dir / safe / f"{version}.meta.json"


def save_artifact(
    agent_name: str,
    version: str,
    payload: Any,
    metadata: dict | None = None,
) -> tuple[Path, Path]:
    ap = artifact_path(agent_name, version)
    mp = metadata_path(agent_name, version)
    ap.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(payload, ap, compress=3)
    meta = dict(metadata or {})
    meta.setdefault("agent_name", agent_name)
    meta.setdefault("version", version)
    meta["saved_at"] = datetime.now(timezone.utc).isoformat()
    try:
        import sklearn

        meta.setdefault("sklearn_version", sklearn.__version__)
    except Exception:
        pass
    meta.setdefault("integrity", _file_checksum_placeholder())
    mp.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    # Write checksum after bytes exist
    meta["integrity"] = _sha256(ap)
    mp.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return ap, mp


def _file_checksum_placeholder() -> str:
    return "pending"


def _sha256(path: Path) -> str:
    import hashlib

    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def load_artifact(agent_name: str, version: str) -> tuple[Any, dict]:
    ap = artifact_path(agent_name, version)
    mp = metadata_path(agent_name, version)
    if not ap.exists():
        raise FileNotFoundError(f"Missing artifact: {ap}")
    obj = joblib.load(ap)
    meta = {}
    if mp.exists():
        meta = json.loads(mp.read_text(encoding="utf-8"))
        expected = meta.get("integrity")
        if expected and expected != "pending":
            actual = _sha256(ap)
            if actual != expected:
                raise ValueError(
                    f"Artifact integrity mismatch for {agent_name}@{version}"
                )
        if meta.get("feature_columns") and meta.get("schema_version"):
            # Consumers validate dims at predict time; record presence here
            meta.setdefault("schema_validated_on_load", True)
    return obj, meta


def latest_version(agent_name: str) -> str | None:
    d = settings.model_dir / agent_name.replace("/", "_")
    if not d.exists():
        return None
    versions = sorted(p.stem for p in d.glob("*.joblib"))
    return versions[-1] if versions else None


def list_agent_artifacts() -> list[dict]:
    settings.ensure_dirs()
    out = []
    for agent_dir in settings.model_dir.iterdir():
        if not agent_dir.is_dir():
            continue
        for job in agent_dir.glob("*.joblib"):
            meta_file = job.with_name(job.stem + ".meta.json")
            meta = {}
            if meta_file.exists():
                meta = json.loads(meta_file.read_text(encoding="utf-8"))
            out.append(
                {
                    "agent_name": meta.get("agent_name", agent_dir.name),
                    "version": job.stem,
                    "artifact_file": str(job),
                    "metadata": meta,
                }
            )
    return out


def load_metadata(agent_name: str, version: str) -> dict:
    mp = metadata_path(agent_name, version)
    if not mp.exists():
        return {}
    return json.loads(mp.read_text(encoding="utf-8"))
