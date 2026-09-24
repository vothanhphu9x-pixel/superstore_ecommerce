import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from api.routers.dashboard import router as dashboard_router
from api.routers.health import router as health_router
from core.config import get_settings
from core.logging import configure_logging


configure_logging()

logger = logging.getLogger("api")
settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info(
        "Starting %s in %s mode.",
        settings.app_name,
        settings.app_env,
    )

    if not settings.api_key or settings.api_key.startswith("CHANGE_ME"):
        logger.error(
            "API_KEY chưa được cấu hình; internal endpoints sẽ trả 503."
        )

    yield

    logger.info("Stopping %s.", settings.app_name)


app = FastAPI(
    title="Superstore API",
    description="Read-only analytics API for Superstore ERP.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=settings.cors_origins != ["*"],
    allow_methods=["GET"],
    allow_headers=["Content-Type", "X-API-Key"],
)


@app.middleware("http")
async def response_time_middleware(
    request: Request,
    call_next,
):
    started = time.perf_counter()

    response = await call_next(request)

    elapsed = time.perf_counter() - started
    response.headers["X-Response-Time"] = f"{elapsed:.3f}s"

    logger.info(
        "%s %s -> %s in %.3fs",
        request.method,
        request.url.path,
        response.status_code,
        elapsed,
    )

    return response


app.include_router(health_router)
app.include_router(
    dashboard_router,
    prefix="/api",
    tags=["dashboard"],
)


@app.get("/")
async def root() -> dict[str, str]:
    return {
        "name": settings.app_name,
        "docs": "/docs",
        "liveness": "/health/live",
        "readiness": "/health/ready",
    }