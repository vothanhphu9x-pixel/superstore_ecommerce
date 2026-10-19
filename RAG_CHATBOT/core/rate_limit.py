"""Atomic Redis rate limiting for authentication requests."""

from __future__ import annotations

import hashlib
import os
import time

from fastapi import HTTPException
from redis.asyncio import Redis


LUA_INCREMENT = """
local count = redis.call('INCR', KEYS[1])

if count == 1 then
    redis.call('EXPIRE', KEYS[1], ARGV[1])
end

return count
"""


async def allow_request(
    *,
    redis_client: Redis,
    bucket: str,
    identity: str,
    limit: int | None = None,
    window_seconds: int = 60,
) -> bool:
    maximum = (
        limit
        if limit is not None
        else int(
            os.environ.get(
                "AUTH_RATE_LIMIT_PER_MINUTE",
                "10",
            )
        )
    )

    identity_digest = hashlib.sha256(
        identity.encode()
    ).hexdigest()

    current_window = int(
        time.time() // window_seconds
    )

    key = (
        f"superstore:rate-limit:"
        f"{bucket}:"
        f"{identity_digest}:"
        f"{current_window}"
    )

    try:
        count = await redis_client.eval(
            LUA_INCREMENT,
            1,
            key,
            window_seconds + 5,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="Login is temporarily unavailable",
            headers={
                "Retry-After": "30",
            },
        ) from exc

    return int(count) <= maximum
