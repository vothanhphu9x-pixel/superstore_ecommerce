from dataclasses import dataclass
from typing import Any, Literal


class ContractViolation(RuntimeError):
    pass


@dataclass(frozen=True)
class MetricContract:
    shape: Literal["object", "list"]
    required_fields: tuple[str, ...]
    accepts_limit: bool = False


METRIC_CONTRACTS: dict[str, MetricContract] = {
    "kpi": MetricContract(
        shape="object",
        required_fields=(
            "REVENUE",
            "GROSS_PROFIT",
            "ORDERS",
            "AVG_ORDER_VALUE",
            "MARGIN_PCT",
        ),
    ),
    "revenue-trend": MetricContract(
        shape="list",
        required_fields=(
            "MONTH_DATE_KEY",
            "REVENUE",
            "COGS",
            "GROSS_PROFIT",
        ),
    ),
    "by-category": MetricContract(
        shape="list",
        required_fields=(
            "CATEGORY",
            "REVENUE",
            "GROSS_PROFIT",
        ),
    ),
    "by-region": MetricContract(
        shape="list",
        required_fields=(
            "REGION",
            "REVENUE",
            "GROSS_PROFIT",
        ),
    ),
    "top-products": MetricContract(
        shape="list",
        required_fields=(
            "PRODUCT_ID",
            "PRODUCT_NAME",
            "CATEGORY",
            "REVENUE",
            "GROSS_PROFIT",
            "QUANTITY",
        ),
        accepts_limit=True,
    ),
}


def validate_metric_payload(
    metric: str,
    payload: Any,
) -> None:
    contract = METRIC_CONTRACTS.get(metric)

    if contract is None:
        raise ContractViolation(
            f"Metric {metric!r} has no declared contract."
        )

    if contract.shape == "object":
        if not isinstance(payload, dict):
            raise ContractViolation(
                f"Metric {metric!r} must return an object."
            )
        rows = [payload]
    else:
        if not isinstance(payload, list):
            raise ContractViolation(
                f"Metric {metric!r} must return a list."
            )
        rows = payload

    required = set(contract.required_fields)

    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ContractViolation(
                f"Metric {metric!r}, row {index}, is not an object."
            )

        missing = required - set(row)

        if missing:
            raise ContractViolation(
                f"Metric {metric!r}, row {index}, "
                f"is missing fields: {sorted(missing)}"
            )
