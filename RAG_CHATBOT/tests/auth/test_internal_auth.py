import pytest
from fastapi import HTTPException

from core.config import get_settings
from core.internal_auth import (
    authenticate_staff,
    change_staff_role,
    create_session_token,
    create_staff_user,
    decode_session_token,
    hash_password,
    role_can_view_groups,
    verify_password,
)


@pytest.fixture
def auth_environment(tmp_path, monkeypatch):
    monkeypatch.setenv(
        "STAFF_DB_PATH",
        str(tmp_path / "staff.db"),
    )
    monkeypatch.setenv(
        "STAFF_JWT_SECRET",
        "a" * 64,
    )
    monkeypatch.setenv(
        "INTERNAL_EMAIL_DOMAINS",
        "company.com",
    )

    get_settings.cache_clear()

    yield

    get_settings.cache_clear()


def test_password_hash_round_trip():
    first_hash = hash_password("StrongPassword123!")
    second_hash = hash_password("StrongPassword123!")

    assert first_hash != second_hash
    assert verify_password("StrongPassword123!", first_hash)
    assert not verify_password("wrong-password", first_hash)


def test_staff_authentication(auth_environment):
    create_staff_user(
        email="admin@company.com",
        name="Admin",
        role="admin",
        password="StrongPassword123!",
    )

    user = authenticate_staff(
        "admin@company.com",
        "StrongPassword123!",
    )

    assert user is not None
    assert user["role"] == "admin"

    assert (
        authenticate_staff(
            "admin@company.com",
            "wrong-password",
        )
        is None
    )


def test_rejects_unapproved_domain(auth_environment):
    assert (
        authenticate_staff(
            "someone@external.com",
            "StrongPassword123!",
        )
        is None
    )


def test_role_change_invalidates_existing_token(
    auth_environment,
):
    user = create_staff_user(
        email="finance@company.com",
        name="Finance User",
        role="cfo",
        password="StrongPassword123!",
    )

    token = create_session_token(user)

    assert decode_session_token(token)["role"] == "cfo"

    change_staff_role("finance@company.com", "sales")

    with pytest.raises(HTTPException) as exception:
        decode_session_token(token)

    assert exception.value.status_code == 401


def test_role_metric_permissions():
    assert role_can_view_groups(
        "admin",
        frozenset({"sales"}),
    )

    assert role_can_view_groups(
        "cfo",
        frozenset({"cfo"}),
    )

    assert not role_can_view_groups(
        "cfo",
        frozenset({"ceo"}),
    )

    assert not role_can_view_groups(
        "cfo",
        frozenset({"sales"}),
    )
