import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from analytics.connector import snowflake_health
from core.cache import cache_health


logger = logging.getLogger("api.health")

router = APIRouter()


@router.get("/health/live")
async def liveness() -> dict[str, str]:
    return {"status": "healthy"}


@router.get("/health/ready")
async def readiness():
    services: dict[str, dict] = {}

    try:
        services["snowflake"] = await snowflake_health()
        snowflake_ready = True
    except Exception:
        logger.exception("Snowflake readiness check failed.")
        services["snowflake"] = {
            "status": "unavailable",
            "detail": "Snowflake connection or query failed.",
        }
        snowflake_ready = False

    services["redis"] = await cache_health()

    payload = {
        "status": (
            "ready"
            if snowflake_ready
            else "not_ready"
        ),
        "services": services,
    }

    if not snowflake_ready:
        return JSONResponse(
            status_code=503,
            content=payload,
        )

    return payload


@router.get("/health")
async def health():
    return await readiness()