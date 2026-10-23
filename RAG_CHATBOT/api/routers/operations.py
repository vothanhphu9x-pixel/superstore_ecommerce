"""Operational probes without frequent Snowflake queries."""

from __future__ import annotations

import asyncio
import os
import sqlite3

from contextlib import closing
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import JSONResponse, Response

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    generate_latest,
)
from redis.asyncio import Redis


router = APIRouter(tags=["operations"])


@router.get("/api/health/live")
def live():
    return JSONResponse(
        {
            "status": "ok",
            "release": os.getenv(
                "APP_RELEASE",
                "local",
            ),
        },
        headers={
            "Cache-Control": "no-store",
        },
    )


def _staff_store_ok() -> bool:
    path = Path(
        os.getenv(
            "STAFF_DB_PATH",
            "/app/data/internal_users.db",
        )
    )

    uri = path.resolve().as_uri() + "?mode=ro"

    try:
        with closing(
            sqlite3.connect(
                uri,
                uri=True,
                timeout=2,
            )
        ) as connection:
            connection.execute(
                """
                SELECT
                    email,
                    role,
                    active,
                    auth_version
                FROM staff_users
                LIMIT 1
                """
            ).fetchall()

        return True

    except sqlite3.Error:
        return False


@router.get("/api/health/ready")
async def ready():
    staff_ok = await asyncio.to_thread(
        _staff_store_ok
    )

    client = Redis.from_url(
        os.environ.get(
            "REDIS_URL",
            "redis://redis:6379/0",
        ),
        socket_connect_timeout=2,
        socket_timeout=2,
    )

    try:
        redis_ok = bool(
            await asyncio.wait_for(
                client.ping(),
                timeout=3,
            )
        )

    except Exception:
        redis_ok = False

    finally:
        await client.aclose()

    is_ready = staff_ok and redis_ok

    return JSONResponse(
        {
            "status": (
                "ready"
                if is_ready
                else "not_ready"
            ),
            "staff_store": staff_ok,
            "redis": redis_ok,
        },
        status_code=200 if is_ready else 503,
        headers={
            "Cache-Control": "no-store",
        },
    )


@router.get(
    "/metrics",
    include_in_schema=False,
)
def metrics():
    return Response(
        generate_latest(),
        headers={
            "Content-Type": CONTENT_TYPE_LATEST,
        },
    )