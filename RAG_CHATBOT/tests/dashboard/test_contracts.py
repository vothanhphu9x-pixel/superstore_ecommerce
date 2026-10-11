import pytest

from analytics.contracts import (
    ContractViolation,
    METRIC_CONTRACTS,
    validate_metric_payload,
)
from analytics.dashboard_queries import DASHBOARD_QUERIES


def test_every_query_has_contract():
    assert set(DASHBOARD_QUERIES) == set(METRIC_CONTRACTS)


def test_valid_kpi_contract():
    validate_metric_payload(
        "kpi",
        {
            "REVENUE": 100,
            "GROSS_PROFIT": 25,
            "ORDERS": 3,
            "AVG_ORDER_VALUE": 33.33,
            "MARGIN_PCT": 25,
        },
    )


def test_missing_field_fails_contract():
    with pytest.raises(ContractViolation):
        validate_metric_payload(
            "kpi",
            {
                "REVENUE": 100,
            },
        )


def test_wrong_shape_fails_contract():
    with pytest.raises(ContractViolation):
        validate_metric_payload(
            "revenue-trend",
            {
                "MONTH_DATE_KEY": 20230101,
            },
        )