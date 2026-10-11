from __future__ import annotations

import ipaddress

from fastapi import Request

from core.config import get_settings


def _valid_ip(value: str | None) -> str | None:
    if not value:
        return None

    candidate = value.strip()

    try:
        return str(ipaddress.ip_address(candidate))
    except ValueError:
        return None


def get_client_ip(request: Request) -> str:
    peer_ip = _valid_ip(
        request.client.host if request.client else None
    )

    if not get_settings().trust_proxy_headers:
        return peer_ip or "unknown"

    if peer_ip:
        peer_address = ipaddress.ip_address(peer_ip)

        if not (
            peer_address.is_private
            or peer_address.is_loopback
            or peer_address.is_link_local
        ):
            return peer_ip

    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        first_ip = _valid_ip(forwarded_for.split(",", maxsplit=1)[0])
        if first_ip:
            return first_ip

    real_ip = _valid_ip(request.headers.get("x-real-ip"))
    return real_ip or peer_ip or "unknown"