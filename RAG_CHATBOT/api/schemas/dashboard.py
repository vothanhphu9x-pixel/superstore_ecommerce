from typing import Any

from pydantic import BaseModel


class DashboardMetricResponse(BaseModel):
    metric: str
    month_from: int
    month_to: int
    row_count: int
    data: dict[str, Any] | list[dict[str, Any]]
    cached: bool


class DashboardIndexResponse(BaseModel):
    metrics: list[str]
    default_range: dict[str, int]
    contracts: dict[str, dict[str, Any]]
