"""Read client IP without trusting arbitrary forwarded headers."""

import hmac
import ipaddress
import os

from fastapi import Request


def get_client_ip(request: Request) -> str:
    expected_api_key = os.environ.get("API_KEY", "").strip()
    supplied_api_key = request.headers.get("x-api-key", "")

    authenticated_proxy = (
        bool(expected_api_key)
        and hmac.compare_digest(
            expected_api_key.encode(),
            supplied_api_key.encode(),
        )
    )

    if authenticated_proxy:
        forwarded_ip = request.headers.get(
            "x-superstore-client-ip",
            "",
        )

        try:
            return str(ipaddress.ip_address(forwarded_ip))
        except ValueError:
            pass

    if request.client is not None:
        return request.client.host

    return "unknown"