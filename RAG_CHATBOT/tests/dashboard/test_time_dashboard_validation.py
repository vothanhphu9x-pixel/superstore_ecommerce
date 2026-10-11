import pytest
from fastapi import HTTPException

from api.services.dashboard import validate_month_key


@pytest.mark.parametrize(
    "value",
    [
        20230101,
        20231201,
        20260201,
    ],
)
def test_valid_month_key(value):
    assert validate_month_key(value, "month") == value


@pytest.mark.parametrize(
    "value",
    [
        20230115,
        20231301,
        20230230,
        18000101,
    ],
)
def test_invalid_month_key(value):
    with pytest.raises(HTTPException) as error:
        validate_month_key(value, "month")

    assert error.value.status_code == 422