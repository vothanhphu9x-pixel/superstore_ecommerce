import hashlib
import json
import logging
from typing import Any

from redis.asyncio import Redis

from core.config import get_settings


logger = logging.getLogger("core.cache")

_client: Redis | None = None
_warned = False


def _warn_once(message: str, error: Exception) -> None:
    global _warned

    if not _warned:
        logger.warning("%s: %s. API tiếp tục không dùng cache.", message, error)
        _warned = True
    else:
        logger.debug("%s: %s", message, error)


def get_client() -> Redis | None:
    global _client

    settings = get_settings()

    if not settings.cache_enabled:
        return None

    if _client is None:
        _client = Redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )

    return _client


def make_key(namespace: str, payload: Any) -> str:
    settings = get_settings()

    serialized = json.dumps(
        payload,
        sort_keys=True,
        ensure_ascii=False,
        default=str,
    )
    digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:16]

    return f"{settings.cache_key_prefix}:{namespace}:{digest}"


async def cache_get(key: str) -> Any | None:
    client = get_client()

    if client is None:
        return None

    try:
        value = await client.get(key)
        return json.loads(value) if value is not None else None
    except Exception as error:
        _warn_once("Không đọc được Redis cache", error)
        return None


async def cache_set(
    key: str,
    value: Any,
    ttl: int | None = None,
) -> bool:
    client = get_client()

    if client is None:
        return False

    settings = get_settings()

    try:
        await client.setex(
            key,
            ttl or settings.cache_ttl_seconds,
            json.dumps(value, ensure_ascii=False, default=str),
        )
        return True
    except Exception as error:
        _warn_once("Không ghi được Redis cache", error)
        return False


async def cache_health() -> dict[str, str]:
    settings = get_settings()

    if not settings.cache_enabled:
        return {"status": "disabled"}

    client = get_client()

    if client is None:
        return {"status": "unavailable"}

    try:
        await client.ping()
        return {"status": "healthy"}
    except Exception as error:
        _warn_once("Redis health check thất bại", error)
        return {
            "status": "unavailable",
            "detail": "API vẫn chạy không cache.",
        }