"""Isolated filesystem paths for the REAL_RETAIL_UCI experiment."""

from __future__ import annotations

from pathlib import Path

from app.core.config import PROJECT_ROOT

DATA_ROOT = PROJECT_ROOT / "data" / "real" / "uci_online_retail"
RAW_DIR = DATA_ROOT / "raw"
PROCESSED_DIR = DATA_ROOT / "processed"
SPLITS_DIR = DATA_ROOT / "splits"
SAMPLES_DIR = DATA_ROOT / "samples"
MANIFEST_PATH = DATA_ROOT / "dataset_manifest.json"
DATA_DICTIONARY_PATH = DATA_ROOT / "data_dictionary.md"

EXPERIMENT_ROOT = PROJECT_ROOT / "experiments" / "real_data" / "uci_online_retail"
MODELS_DIR = EXPERIMENT_ROOT / "models"
REPORTS_DIR = EXPERIMENT_ROOT / "reports"

RAW_XLSX_NAME = "Online Retail.xlsx"
RAW_XLSX_PATH = RAW_DIR / RAW_XLSX_NAME


def ensure_data_dirs() -> None:
    for d in (RAW_DIR, PROCESSED_DIR, SPLITS_DIR, SAMPLES_DIR, MODELS_DIR, REPORTS_DIR):
        d.mkdir(parents=True, exist_ok=True)


def report_path(name: str) -> Path:
    return REPORTS_DIR / name


def model_path(name: str) -> Path:
    return MODELS_DIR / name
