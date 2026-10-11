from __future__ import annotations

import hashlib
import threading
import time

from core.cache import get_client
from core.config import get_settings


_fallback_counts: dict[tuple[str, str, int], int] = {}
_fallback_lock = threading.Lock()


def _identity_hash(identity: str) -> str:
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]


def _allow_fallback(
    bucket: str,
    identity: str,
    limit: int,
    window_seconds: int,
) -> bool:
    current_window = int(time.time() // window_seconds)
    key = (bucket, _identity_hash(identity), current_window)

    with _fallback_lock:
        expired_windows = [
            stored_key
            for stored_key in _fallback_counts
            if stored_key[2] < current_window - 1
        ]

        for expired_key in expired_windows:
            _fallback_counts.pop(expired_key, None)

        count = _fallback_counts.get(key, 0) + 1
        _fallback_counts[key] = count

    return count <= limit


async def allow_request(
    *,
    bucket: str,
    identity: str,
    limit: int | None = None,
    window_seconds: int = 60,
) -> bool:
    configured_limit = (
        limit
        if limit is not None
        else get_settings().auth_rate_limit_per_minute
    )

    identity_digest = _identity_hash(identity)
    current_window = int(time.time() // window_seconds)
    redis_key = (
        f"rate-limit:{bucket}:{identity_digest}:{current_window}"
    )

    try:
        redis_client = await get_client()

        count = await redis_client.incr(redis_key)
        if count == 1:
            await redis_client.expire(redis_key, window_seconds + 5)

        return int(count) <= configured_limit
    except Exception:
        return _allow_fallback(
            bucket,
            identity,
            configured_limit,
            window_seconds,
        )