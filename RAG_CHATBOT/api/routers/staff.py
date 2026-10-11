from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from analytics.contracts import METRIC_CONTRACTS
from api.schemas.staff import (
    StaffLoginRequest,
    StaffLogoutResponse,
    StaffProfile,
)
from core.auth import verify_api_key
from core.client_ip import get_client_ip
from core.config import get_settings
from core.internal_auth import (
    COOKIE_NAME,
    authenticate_staff,
    create_session_token,
    require_staff,
    role_can_view_groups,
)
from core.rate_limit import allow_request


router = APIRouter(
    prefix="/staff",
    tags=["staff"],
    dependencies=[Depends(verify_api_key)],
)


def _profile(user: dict) -> StaffProfile:
    permitted_metrics = [
        metric_key
        for metric_key, contract in METRIC_CONTRACTS.items()
        if role_can_view_groups(user["role"], contract.groups)
    ]

    return StaffProfile(
        email=user["email"],
        name=user["name"],
        role=user["role"],
        metrics=permitted_metrics,
    )


@router.post("/login", response_model=StaffProfile)
async def login(
    payload: StaffLoginRequest,
    request: Request,
    response: Response,
) -> StaffProfile:
    client_ip = get_client_ip(request)

    permitted = await allow_request(
        bucket="staff-login",
        identity=client_ip,
    )

    if not permitted:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Please try again later.",
            headers={"Retry-After": "60"},
        )

    user = await asyncio.to_thread(
        authenticate_staff,
        str(payload.email),
        payload.password,
    )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email or password is incorrect",
        )

    token = create_session_token(user)
    settings = get_settings()

    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        secure=settings.staff_cookie_secure,
        samesite="lax",
        max_age=settings.staff_session_ttl_hours * 60 * 60,
        path="/",
    )

    return _profile(user)


@router.post("/logout", response_model=StaffLogoutResponse)
def logout(response: Response) -> StaffLogoutResponse:
    response.delete_cookie(
        key=COOKIE_NAME,
        path="/",
        httponly=True,
        secure=get_settings().staff_cookie_secure,
        samesite="lax",
    )

    return StaffLogoutResponse(detail="Logged out")


@router.get("/me", response_model=StaffProfile)
def current_staff(
    staff: dict = Depends(require_staff),
) -> StaffProfile:
    return _profile(staff)