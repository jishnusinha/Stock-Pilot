"""Download or import the official UCI Online Retail workbook."""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import urllib.error
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.real_data import (
    DATASET_ATTRIBUTION,
    DATASET_DOI,
    DATASET_ID,
    DATASET_LICENSE,
    DATASET_NAME,
    EXPERIMENT_ID,
    OFFICIAL_PAGE_URL,
    OFFICIAL_ZIP_URL,
    PROCESSING_VERSION,
)
from app.real_data.paths import RAW_DIR, RAW_XLSX_NAME, RAW_XLSX_PATH, ensure_data_dirs

# Known checksum may vary if UCI re-packages; we record whatever we download.
USER_AGENT = "StockPilot/3.3 (research; local-first; +https://github.com/jishnusinha/Stock-Pilot)"


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _extract_xlsx_from_zip(zip_path: Path, dest: Path) -> Path:
    with zipfile.ZipFile(zip_path, "r") as zf:
        members = [n for n in zf.namelist() if n.lower().endswith(".xlsx") and not n.startswith("__")]
        if not members:
            raise FileNotFoundError("ZIP archive contains no .xlsx file")
        # Prefer the canonical filename if present
        preferred = next((m for m in members if Path(m).name.lower() == RAW_XLSX_NAME.lower()), members[0])
        with zf.open(preferred) as src, dest.open("wb") as out:
            shutil.copyfileobj(src, out)
    return dest


def download_official(*, force: bool = False, timeout: int = 120) -> dict[str, Any]:
    """Fetch the official UCI ZIP and extract Online Retail.xlsx into raw/."""
    ensure_data_dirs()
    if RAW_XLSX_PATH.exists() and not force:
        digest = sha256_file(RAW_XLSX_PATH)
        return {
            "status": "already_present",
            "path": str(RAW_XLSX_PATH),
            "sha256": digest,
            "bytes": RAW_XLSX_PATH.stat().st_size,
            "source_url": OFFICIAL_ZIP_URL,
            "page_url": OFFICIAL_PAGE_URL,
            "downloaded_at": None,
            "message": "Raw XLSX already present; use --force to re-download.",
        }

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(OFFICIAL_ZIP_URL, headers={"User-Agent": USER_AGENT})
    downloaded_at = datetime.now(timezone.utc).isoformat()
    try:
        with tempfile.TemporaryDirectory(prefix="uci_retail_") as tmp:
            tmp_zip = Path(tmp) / "online_retail.zip"
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                with tmp_zip.open("wb") as out:
                    shutil.copyfileobj(resp, out)
            if not zipfile.is_zipfile(tmp_zip):
                raise ValueError("Downloaded file is not a valid ZIP archive")
            _extract_xlsx_from_zip(tmp_zip, RAW_XLSX_PATH)
    except urllib.error.URLError as exc:
        raise RuntimeError(
            f"Official UCI download failed ({exc}). "
            f"Place the official '{RAW_XLSX_NAME}' at: {RAW_XLSX_PATH} "
            f"(from {OFFICIAL_PAGE_URL}) then re-run."
        ) from exc

    if not RAW_XLSX_PATH.exists():
        raise FileNotFoundError(f"Expected XLSX missing after download: {RAW_XLSX_PATH}")

    digest = sha256_file(RAW_XLSX_PATH)
    return {
        "status": "downloaded",
        "path": str(RAW_XLSX_PATH),
        "sha256": digest,
        "bytes": RAW_XLSX_PATH.stat().st_size,
        "source_url": OFFICIAL_ZIP_URL,
        "page_url": OFFICIAL_PAGE_URL,
        "downloaded_at": downloaded_at,
        "dataset_name": DATASET_NAME,
        "dataset_id": DATASET_ID,
        "doi": DATASET_DOI,
        "license": DATASET_LICENSE,
        "attribution": DATASET_ATTRIBUTION,
        "experiment_id": EXPERIMENT_ID,
        "processing_version": PROCESSING_VERSION,
    }


def import_local_xlsx(source: Path, *, force: bool = False) -> dict[str, Any]:
    """Copy a user-provided official XLSX into the raw directory."""
    ensure_data_dirs()
    source = Path(source)
    if not source.exists():
        raise FileNotFoundError(f"Source XLSX not found: {source}")
    if source.suffix.lower() != ".xlsx":
        raise ValueError("Source must be an .xlsx file")
    if RAW_XLSX_PATH.exists() and not force:
        digest = sha256_file(RAW_XLSX_PATH)
        return {
            "status": "already_present",
            "path": str(RAW_XLSX_PATH),
            "sha256": digest,
            "bytes": RAW_XLSX_PATH.stat().st_size,
            "imported_from": str(source),
        }
    shutil.copy2(source, RAW_XLSX_PATH)
    digest = sha256_file(RAW_XLSX_PATH)
    return {
        "status": "imported",
        "path": str(RAW_XLSX_PATH),
        "sha256": digest,
        "bytes": RAW_XLSX_PATH.stat().st_size,
        "imported_from": str(source),
        "downloaded_at": datetime.now(timezone.utc).isoformat(),
        "page_url": OFFICIAL_PAGE_URL,
        "source_url": "user_provided_official_xlsx",
        "doi": DATASET_DOI,
        "license": DATASET_LICENSE,
        "attribution": DATASET_ATTRIBUTION,
        "experiment_id": EXPERIMENT_ID,
    }


def require_raw_xlsx() -> Path:
    if not RAW_XLSX_PATH.exists():
        raise FileNotFoundError(
            f"Missing raw workbook at {RAW_XLSX_PATH}. "
            f"Run: python -m app.cli real-data-download "
            f"or place the official file from {OFFICIAL_PAGE_URL}."
        )
    return RAW_XLSX_PATH


def write_download_sidecar(info: dict[str, Any]) -> Path:
    ensure_data_dirs()
    path = RAW_DIR / "download_info.json"
    path.write_text(json.dumps(info, indent=2), encoding="utf-8")
    return path
