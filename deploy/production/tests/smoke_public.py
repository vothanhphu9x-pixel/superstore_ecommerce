"""Smoke-test the public website login and CFO dashboard path after deploy."""

from __future__ import annotations

import http.cookiejar
import json
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPCookieProcessor, Request, build_opener


def _required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ValueError(f"Required environment value is missing: {name}")
    return value


def _frontend_origin() -> str:
    raw = _required_env("FRONTEND_ORIGIN").rstrip("/")
    parsed = urlsplit(raw)
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or parsed.path
        or parsed.query
        or parsed.fragment
        or parsed.username
        or parsed.password
    ):
        raise ValueError("FRONTEND_ORIGIN must be an HTTPS origin without a path")
    return f"{parsed.scheme}://{parsed.netloc}"


def _json_request(
    opener,
    url: str,
    *,
    method: str = "GET",
    body=None,
    origin=None,
    expected_status: int | tuple[int, ...] = 200,
    case_id: str,
):
    headers = {"Accept": "application/json"}
    data = None

    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"

    if origin:
        headers["Origin"] = origin

    request = Request(url, data=data, headers=headers, method=method)
    expected = (
        expected_status
        if isinstance(expected_status, tuple)
        else (expected_status,)
    )

    try:
        response = opener.open(request, timeout=30)
    except HTTPError as error:
        response = error

    with response:
        if response.status not in expected:
            raise RuntimeError(
                f"{case_id}: {urlsplit(url).path}: expected HTTP {expected}, "
                f"received {response.status}"
            )
        raw_body = response.read()
        payload = json.loads(raw_body.decode("utf-8")) if raw_body else {}
        return payload, response


def _passed(case_id: str) -> None:
    print(f"{case_id} PASS")


def main() -> int:
    opener = None
    origin = None
    logged_in = False
    try:
        origin = _frontend_origin()
        email = _required_env("MONITOR_EMAIL")
        password = _required_env("MONITOR_PASSWORD")

        cookies = http.cookiejar.CookieJar()
        opener = build_opener(HTTPCookieProcessor(cookies))

        health, _ = _json_request(
            opener,
            f"{origin}/api/health",
            case_id="DEPLOY-01",
        )
        if health.get("status") != "ok" or health.get("api") != "up":
            raise RuntimeError("DEPLOY-01: frontend health probe failed")
        _passed("DEPLOY-01")

        _json_request(
            opener,
            f"{origin}/api/internal/staff/me",
            expected_status=401,
            case_id="DEPLOY-02",
        )
        _passed("DEPLOY-02")

        profile, login_response = _json_request(
            opener,
            f"{origin}/api/internal/staff/login",
            method="POST",
            body={"email": email, "password": password},
            origin=origin,
            case_id="DEPLOY-03",
        )
        logged_in = True
        if profile.get("role") != "cfo":
            raise RuntimeError("DEPLOY-03: monitoring account role is not cfo")

        set_cookies = login_response.headers.get_all("Set-Cookie") or []
        staff_cookie = next(
            (value for value in set_cookies if "superstore_staff=" in value),
            "",
        )
        cookie_attributes = staff_cookie.casefold()
        if not all(
            required in cookie_attributes
            for required in ("httponly", "secure", "samesite=lax", "path=/")
        ):
            raise RuntimeError("Login did not set the expected secure staff cookie")

        if not any(cookie.name == "superstore_staff" for cookie in cookies):
            raise RuntimeError("Login did not persist the staff session cookie")

        current_user, _ = _json_request(
            opener,
            f"{origin}/api/internal/staff/me",
            case_id="DEPLOY-03",
        )
        if current_user.get("role") != "cfo":
            raise RuntimeError("DEPLOY-03: staff session role is not cfo")
        _passed("DEPLOY-03")

        index, _ = _json_request(
            opener,
            f"{origin}/api/internal/dashboard",
            case_id="DEPLOY-06",
        )
        if "kpi" not in index.get("metrics", []):
            raise RuntimeError("DEPLOY-05: CFO dashboard index omits KPI")
        if "by-category" in index.get("metrics", []):
            raise RuntimeError("DEPLOY-06: CFO dashboard exposes by-category")

        query = urlencode({"month_from": 20230101, "month_to": 20271201})
        kpi, _ = _json_request(
            opener,
            f"{origin}/api/internal/dashboard/kpi?{query}",
            case_id="DEPLOY-05",
        )
        values = kpi.get("data")
        if not isinstance(values, dict):
            raise RuntimeError("DEPLOY-05: KPI response data is not an object")

        required_fields = {
            "REVENUE",
            "GROSS_PROFIT",
            "ORDERS",
            "AVG_ORDER_VALUE",
            "MARGIN_PCT",
        }
        if not required_fields.issubset(values):
            raise RuntimeError("DEPLOY-05: KPI response is missing required fields")
        _passed("DEPLOY-05")

        _json_request(
            opener,
            f"{origin}/api/internal/dashboard/by-category?{query}",
            expected_status=403,
            case_id="DEPLOY-06",
        )
        _passed("DEPLOY-06")

        _json_request(
            opener,
            f"{origin}/api/internal/staff/logout",
            method="POST",
            origin=origin,
            expected_status=(200, 204),
            case_id="DEPLOY-07",
        )
        if any(cookie.name == "superstore_staff" for cookie in cookies):
            raise RuntimeError("DEPLOY-07: logout did not clear the staff cookie")
        logged_in = False

        _json_request(
            opener,
            f"{origin}/api/internal/staff/me",
            expected_status=401,
            case_id="DEPLOY-07",
        )
        _passed("DEPLOY-07")

        print(
            "Production deploy smoke passed: health, anonymous denial, "
            "CFO login/cookie, KPI, RBAC denial and logout."
        )
        return 0

    except (HTTPError, URLError, TimeoutError, ValueError, RuntimeError) as exc:
        status = getattr(exc, "code", None)
        if status is not None:
            print(f"Production smoke test failed: HTTP {status}.", file=sys.stderr)
        else:
            print(f"Production smoke test failed: {exc}.", file=sys.stderr)
        return 1
    finally:
        if logged_in and opener is not None and origin is not None:
            try:
                _json_request(
                    opener,
                    f"{origin}/api/internal/staff/logout",
                    method="POST",
                    origin=origin,
                    expected_status=(200, 204),
                    case_id="DEPLOY-07 cleanup",
                )
            except (HTTPError, URLError, TimeoutError, RuntimeError):
                print(
                    "Warning: production smoke could not confirm logout.",
                    file=sys.stderr,
                )


if __name__ == "__main__":
    raise SystemExit(main())
