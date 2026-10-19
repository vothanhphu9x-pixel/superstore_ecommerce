from __future__ import annotations

import base64
import hashlib
import hmac
import os
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
import token
from typing import Any
from contextlib import closing

import jwt
from fastapi import Cookie, HTTPException, status

from core.config import get_settings


COOKIE_NAME = "superstore_staff"
JWT_ALGORITHM = "HS256"

SCRYPT_N = 16_384
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_DKLEN = 32
SCRYPT_SALT_BYTES = 16

STAFF_ROLES = {
    "admin",
    "analyst",
    "ceo",
    "cfo",
    "sales",
    "marketing",
    "warehouse",
    "plant",
}

ROLE_DASHBOARD_GROUPS: dict[str, set[str]] = {
    "admin": {"*"},
    "analyst": {"*"},
    "ceo": {"ceo", "sales", "cfo"},
    "cfo": {"cfo", "ceo"},
    "sales": {"sales"},
    "marketing": {"marketing"},
    "warehouse": {"warehouse"},
    "plant": {"plant"},
}


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _utc_iso() -> str:
    return _utc_now().isoformat()


def _database_path() -> Path:
    configured = Path(get_settings().staff_db_path)

    if configured.is_absolute():
        return configured

    project_root = Path(__file__).resolve().parent.parent
    return project_root / configured


def _connect() -> sqlite3.Connection:
    database_path = _database_path()
    database_path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(
        database_path,
        timeout=5,
    )
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA busy_timeout = 5000")

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS staff_users (
            email TEXT PRIMARY KEY COLLATE NOCASE,
            name TEXT NOT NULL,
            role TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 1
                CHECK (active IN (0, 1)),
            auth_version INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    connection.commit()

    return connection


def normalize_email(email: str) -> str:
    return email.strip().lower()


def allowed_email_domains() -> set[str]:
    return {
        domain.strip().lower()
        for domain in get_settings().internal_email_domains.split(",")
        if domain.strip()
    }


def email_domain_is_allowed(email: str) -> bool:
    normalized = normalize_email(email)

    if "@" not in normalized:
        return False

    domain = normalized.rsplit("@", maxsplit=1)[1]
    return domain in allowed_email_domains()


def hash_password(password: str) -> str:
    salt = os.urandom(SCRYPT_SALT_BYTES)
    password_bytes = password.encode("utf-8")

    derived_key = hashlib.scrypt(
        password_bytes,
        salt=salt,
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        dklen=SCRYPT_DKLEN,
    )

    salt_base64 = base64.b64encode(salt).decode("ascii")
    key_base64 = base64.b64encode(derived_key).decode("ascii")

    return (
        f"scrypt${SCRYPT_N},{SCRYPT_R},{SCRYPT_P}"
        f"${salt_base64}${key_base64}"
    )


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, params, salt_base64, key_base64 = stored_hash.split("$")
        if algorithm != "scrypt":
            return False

        n_value, r_value, p_value = (
            int(value) for value in params.split(",")
        )

        salt = base64.b64decode(salt_base64)
        expected_key = base64.b64decode(key_base64)

        actual_key = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=n_value,
            r=r_value,
            p=p_value,
            dklen=len(expected_key),
        )

        return hmac.compare_digest(actual_key, expected_key)
    except (ValueError, TypeError):
        return False


DUMMY_PASSWORD_HASH = hash_password("not-a-real-password")


def _row_to_user(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None

    return {
        "email": row["email"],
        "name": row["name"],
        "role": row["role"],
        "password_hash": row["password_hash"],
        "active": bool(row["active"]),
        "auth_version": int(row["auth_version"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def get_staff_user(email: str) -> dict[str, Any] | None:
    normalized_email = normalize_email(email)

    with closing(_connect()) as connection, connection:
        row = connection.execute(
            """
            SELECT
                email,
                name,
                role,
                password_hash,
                active,
                auth_version,
                created_at,
                updated_at
            FROM staff_users
            WHERE email = ?
            """,
            (normalized_email,),
        ).fetchone()

    return _row_to_user(row)


def list_staff_users() -> list[dict[str, Any]]:
    with closing(_connect()) as connection, connection:
        rows = connection.execute(
            """
            SELECT
                email,
                name,
                role,
                password_hash,
                active,
                auth_version,
                created_at,
                updated_at
            FROM staff_users
            ORDER BY email
            """
        ).fetchall()

    return [
        user
        for row in rows
        if (user := _row_to_user(row)) is not None
    ]


def create_staff_user(
    *,
    email: str,
    name: str,
    role: str,
    password: str,
    replace: bool = False,
) -> dict[str, Any]:
    normalized_email = normalize_email(email)
    normalized_role = role.strip().lower()
    normalized_name = name.strip()

    if normalized_role not in STAFF_ROLES:
        raise ValueError(f"Unsupported staff role: {normalized_role}")

    if not normalized_name:
        raise ValueError("Staff name cannot be empty")

    if not email_domain_is_allowed(normalized_email):
        raise ValueError("Email domain is not allowed")

    password_hash = hash_password(password)
    timestamp = _utc_iso()

    with closing(_connect()) as connection, connection:
        existing = connection.execute(
            "SELECT email FROM staff_users WHERE email = ?",
            (normalized_email,),
        ).fetchone()

        if existing and not replace:
            raise ValueError("Staff user already exists")

        if existing:
            connection.execute(
                """
                UPDATE staff_users
                SET
                    name = ?,
                    role = ?,
                    password_hash = ?,
                    active = 1,
                    auth_version = auth_version + 1,
                    updated_at = ?
                WHERE email = ?
                """,
                (
                    normalized_name,
                    normalized_role,
                    password_hash,
                    timestamp,
                    normalized_email,
                ),
            )
        else:
            connection.execute(
                """
                INSERT INTO staff_users (
                    email,
                    name,
                    role,
                    password_hash,
                    active,
                    auth_version,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, 1, 1, ?, ?)
                """,
                (
                    normalized_email,
                    normalized_name,
                    normalized_role,
                    password_hash,
                    timestamp,
                    timestamp,
                ),
            )

        connection.commit()

    user = get_staff_user(normalized_email)
    if user is None:
        raise RuntimeError("Staff user could not be created")

    return user


def change_staff_password(email: str, password: str) -> None:
    with closing(_connect()) as connection, connection:
        cursor = connection.execute(
            """
            UPDATE staff_users
            SET
                password_hash = ?,
                auth_version = auth_version + 1,
                updated_at = ?
            WHERE email = ?
            """,
            (
                hash_password(password),
                _utc_iso(),
                normalize_email(email),
            ),
        )
        connection.commit()

    if cursor.rowcount == 0:
        raise ValueError("Staff user was not found")


def change_staff_role(email: str, role: str) -> None:
    normalized_role = role.strip().lower()

    if normalized_role not in STAFF_ROLES:
        raise ValueError(f"Unsupported staff role: {normalized_role}")

    with closing(_connect()) as connection, connection:
        cursor = connection.execute(
            """
            UPDATE staff_users
            SET
                role = ?,
                auth_version = auth_version + 1,
                updated_at = ?
            WHERE email = ?
            """,
            (
                normalized_role,
                _utc_iso(),
                normalize_email(email),
            ),
        )
        connection.commit()

    if cursor.rowcount == 0:
        raise ValueError("Staff user was not found")


def set_staff_active(email: str, active: bool) -> None:
    with closing(_connect()) as connection, connection:
        cursor = connection.execute(
            """
            UPDATE staff_users
            SET
                active = ?,
                auth_version = auth_version + 1,
                updated_at = ?
            WHERE email = ?
            """,
            (
                int(active),
                _utc_iso(),
                normalize_email(email),
            ),
        )
        connection.commit()

    if cursor.rowcount == 0:
        raise ValueError("Staff user was not found")


def authenticate_staff(
    email: str,
    password: str,
) -> dict[str, Any] | None:
    normalized_email = normalize_email(email)
    user = get_staff_user(normalized_email)

    candidate_hash = (
        user["password_hash"]
        if user is not None
        else DUMMY_PASSWORD_HASH
    )

    password_is_valid = verify_password(password, candidate_hash)

    if not email_domain_is_allowed(normalized_email):
        return None

    if user is None or not user["active"]:
        return None

    if not password_is_valid:
        return None

    return user


def _jwt_secret() -> str:
    secret = get_settings().staff_jwt_secret

    if len(secret) < 32:
        raise RuntimeError(
            "STAFF_JWT_SECRET must contain at least 32 characters"
        )

    return secret


def create_session_token(user: dict[str, Any]) -> str:
    issued_at = _utc_now()
    expires_at = issued_at + timedelta(
        hours=get_settings().staff_session_ttl_hours
    )

    payload = {
        "sub": user["email"],
        "name": user["name"],
        "role": user["role"],
        "ver": user["auth_version"],
        "typ": "staff",
        "iat": issued_at,
        "exp": expires_at,
    }

    return jwt.encode(
        payload,
        _jwt_secret(),
        algorithm=JWT_ALGORITHM,
    )


def decode_session_token(token: str) -> dict[str, Any]:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Staff session is invalid or expired",
    )

    try:
        payload = jwt.decode(
            token,
            _jwt_secret(),
            algorithms=[JWT_ALGORITHM],
            options={
                "require": [
                    "sub",
                    "iat",
                    "exp",
                    "typ",
                    "ver",
                ]
            },
        )
    except jwt.PyJWTError as exc:
        raise credentials_error from exc

    if payload.get("typ") != "staff":
        raise credentials_error

    email = payload.get("sub")
    token_version = payload.get("ver")

    if not isinstance(email, str) or not isinstance(token_version, int):
        raise credentials_error

    user = get_staff_user(email)

    if user is None or not user["active"]:
        raise credentials_error

    if user["auth_version"] != token_version:
        raise credentials_error

    return user


def require_staff(
    session_token: str | None = Cookie(
        default=None,
        alias=COOKIE_NAME,
    ),
) -> dict[str, Any]:
    if not session_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Staff authentication is required",
        )

    return decode_session_token(session_token)


def role_can_view_groups(
    role: str,
    metric_groups: set[str] | frozenset[str],
) -> bool:
    role_groups = ROLE_DASHBOARD_GROUPS.get(role, set())

    return "*" in role_groups or bool(role_groups.intersection(metric_groups))
