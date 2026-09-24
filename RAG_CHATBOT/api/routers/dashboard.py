import logging
import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from analytics.contracts import (
    ContractViolation,
    METRIC_CONTRACTS,
    validate_metric_payload,
)
from analytics.dashboard_queries import (
    DASHBOARD_QUERIES,
    DEFAULT_MONTH_FROM,
    DEFAULT_MONTH_TO,
)
from api.schemas.dashboard import (
    DashboardIndexResponse,
    DashboardMetricResponse,
)
from api.services.dashboard import validate_month_key
from core.auth import verify_api_key
from core.cache import cache_get, cache_set, make_key
from core.config import get_settings


logger = logging.getLogger("api.dashboard")

router = APIRouter(
    prefix="/dashboard",
    dependencies=[Depends(verify_api_key)],
)


@router.get(
    "",
    response_model=DashboardIndexResponse,
)
async def dashboard_index() -> dict[str, Any]:
    contracts = {
        metric: {
            "shape": contract.shape,
            "required_fields": list(contract.required_fields),
            "accepts_limit": contract.accepts_limit,
        }
        for metric, contract in METRIC_CONTRACTS.items()
    }

    return {
        "metrics": sorted(DASHBOARD_QUERIES),
        "default_range": {
            "month_from": DEFAULT_MONTH_FROM,
            "month_to": DEFAULT_MONTH_TO,
        },
        "contracts": contracts,
    }


@router.get(
    "/{metric}",
    response_model=DashboardMetricResponse,
)
async def dashboard_metric(
    metric: str,
    month_from: int = Query(DEFAULT_MONTH_FROM),
    month_to: int = Query(DEFAULT_MONTH_TO),
    limit: int = Query(10, ge=1, le=100),
) -> dict[str, Any]:
    query_function = DASHBOARD_QUERIES.get(metric)
    contract = METRIC_CONTRACTS.get(metric)

    if query_function is None or contract is None:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown dashboard metric: {metric}",
        )

    validate_month_key(month_from, "month_from")
    validate_month_key(month_to, "month_to")

    if month_from > month_to:
        raise HTTPException(
            status_code=422,
            detail="month_from phải nhỏ hơn hoặc bằng month_to.",
        )

    query_params: dict[str, Any] = {
        "month_from": month_from,
        "month_to": month_to,
    }

    if contract.accepts_limit:
        query_params["limit"] = limit

    cache_key = make_key(
        f"dashboard:{metric}",
        query_params,
    )

    cached_payload = await cache_get(cache_key)

    if cached_payload is not None:
        try:
            validate_metric_payload(
                metric,
                cached_payload["data"],
            )
        except (KeyError, ContractViolation):
            logger.warning(
                "Bỏ cache không hợp lệ của metric %s",
                metric,
            )
        else:
            return {
                **cached_payload,
                "cached": True,
            }

    started = time.perf_counter()

    try:
        data = await query_function(**query_params)
        validate_metric_payload(metric, data)
    except ContractViolation as error:
        logger.error(
            "Dashboard contract failed for %s: %s",
            metric,
            error,
            exc_info=True,
        )
        raise HTTPException(
            status_code=502,
            detail=f"Data contract failed for metric '{metric}'.",
        )
    except Exception:
        logger.exception(
            "Snowflake query failed for metric %s",
            metric,
        )
        raise HTTPException(
            status_code=502,
            detail=f"Unable to load metric '{metric}'.",
        )

    payload = {
        "metric": metric,
        "month_from": month_from,
        "month_to": month_to,
        "row_count": len(data) if isinstance(data, list) else 1,
        "data": data,
    }

    await cache_set(
        cache_key,
        payload,
        get_settings().cache_ttl_seconds,
    )

    logger.info(
        "Metric %s returned %d row(s) in %.3fs",
        metric,
        payload["row_count"],
        time.perf_counter() - started,
    )

    return {
        **payload,
        "cached": False,
    }