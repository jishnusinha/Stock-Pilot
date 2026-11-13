"""Read-only REAL_RETAIL_UCI evaluation API — never trains on GET."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from app.real_data import service as rd

router = APIRouter(prefix="/real-data", tags=["real-data"])


def _unavailable(exc: Exception) -> HTTPException:
    return HTTPException(status_code=404, detail=str(exc))


@router.get("/status")
def real_data_status() -> Any:
    return rd.get_status()


@router.get("/summary")
def real_data_summary() -> Any:
    return rd.get_summary()


@router.get("/metrics")
def real_data_metrics() -> Any:
    try:
        return rd.get_metrics()
    except rd.RealDataUnavailable as exc:
        raise _unavailable(exc) from exc


@router.get("/baselines")
def real_data_baselines() -> Any:
    try:
        return {"experiment_id": "REAL_RETAIL_UCI", "rows": rd.get_baselines()}
    except rd.RealDataUnavailable as exc:
        raise _unavailable(exc) from exc


@router.get("/predictions")
def real_data_predictions(
    stock_code: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    limit: int = Query(2000, ge=1, le=20000),
) -> Any:
    try:
        return rd.get_predictions(
            stock_code=stock_code,
            date_from=date_from,
            date_to=date_to,
            limit=limit,
        )
    except rd.RealDataUnavailable as exc:
        raise _unavailable(exc) from exc


@router.get("/products")
def real_data_products(limit: int = Query(200, ge=1, le=500)) -> Any:
    try:
        return rd.get_products(limit=limit)
    except rd.RealDataUnavailable as exc:
        raise _unavailable(exc) from exc


@router.get("/metadata")
def real_data_metadata() -> Any:
    return rd.get_metadata()


@router.get("/predictions/export.csv")
def real_data_predictions_export(
    stock_code: str | None = Query(None),
    limit: int = Query(20000, ge=1, le=100000),
) -> Response:
    try:
        data, filename = rd.predictions_csv_bytes(stock_code=stock_code, limit=limit)
    except rd.RealDataUnavailable as exc:
        raise _unavailable(exc) from exc
    return Response(
        content=data,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/samples/{kind}.csv")
def real_data_sample(kind: str) -> Response:
    try:
        data, filename = rd.safe_sample_csv(kind)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except rd.RealDataUnavailable as exc:
        raise _unavailable(exc) from exc
    return Response(
        content=data,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
