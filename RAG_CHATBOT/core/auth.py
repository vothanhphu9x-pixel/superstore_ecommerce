import hmac
import logging

from fastapi import HTTPException, Security, status
from fastapi.security.api_key import APIKeyHeader

from core.config import get_settings


logger = logging.getLogger("core.auth")

_api_key_header = APIKeyHeader(
    name="X-API-Key",
    auto_error=False,
)


async def verify_api_key(
    supplied_key: str | None = Security(_api_key_header),
) -> None:
    settings = get_settings()
    expected_key = settings.api_key.strip()

    if not expected_key or expected_key.startswith("CHANGE_ME"):
        logger.error("API_KEY chưa được cấu hình.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Internal authentication is not configured.",
        )

    if (
        supplied_key is None
        or not hmac.compare_digest(supplied_key, expected_key)
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing API key.",
        )