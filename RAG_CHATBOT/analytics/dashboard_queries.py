from decimal import Decimal
from typing import Any, Awaitable, Callable

from analytics.connector import run_query
from analytics.relations import gold_table, mart_table


DEFAULT_MONTH_FROM = 20230101
DEFAULT_MONTH_TO = 20271201


def _number(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)

    return value


async def _query(
    sql: str,
    params: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    rows = await run_query(sql, params)

    return [
        {
            key: _number(value)
            for key, value in row.items()
        }
        for row in rows
    ]


def _range(
    month_from: int | None,
    month_to: int | None,
) -> dict[str, int]:
    return {
        "month_from": month_from or DEFAULT_MONTH_FROM,
        "month_to": month_to or DEFAULT_MONTH_TO,
    }


async def kpi_summary(
    month_from: int | None = None,
    month_to: int | None = None,
) -> dict[str, Any]:
    sql = f"""
        SELECT
            ROUND(SUM(revenue_amount), 2) AS revenue,
            ROUND(SUM(gross_profit_amount), 2) AS gross_profit,
            COUNT(DISTINCT order_id) AS orders,
            ROUND(
                SUM(revenue_amount)
                / NULLIF(COUNT(DISTINCT order_id), 0),
                2
            ) AS avg_order_value,
            ROUND(
                SUM(gross_profit_amount)
                / NULLIF(SUM(revenue_amount), 0)
                * 100,
                2
            ) AS margin_pct
        FROM {gold_table("fact_sales")}
        WHERE order_state != 'cancel'
          AND FLOOR(order_date_key / 100) * 100 + 1
              BETWEEN %(month_from)s AND %(month_to)s
    """

    rows = await _query(
        sql,
        _range(month_from, month_to),
    )

    return rows[0] if rows else {
        "REVENUE": None,
        "GROSS_PROFIT": None,
        "ORDERS": 0,
        "AVG_ORDER_VALUE": None,
        "MARGIN_PCT": None,
    }


async def revenue_trend(
    month_from: int | None = None,
    month_to: int | None = None,
) -> list[dict[str, Any]]:
    sql = f"""
        SELECT
            month_date_key,
            ROUND(SUM(revenue_amount), 2) AS revenue,
            ROUND(SUM(cogs_amount), 2) AS cogs,
            ROUND(SUM(gross_profit_amount), 2) AS gross_profit
        FROM {mart_table("mart_revenue_monthly")}
        WHERE month_date_key
              BETWEEN %(month_from)s AND %(month_to)s
        GROUP BY month_date_key
        ORDER BY month_date_key
    """

    return await _query(
        sql,
        _range(month_from, month_to),
    )


async def revenue_by_category(
    month_from: int | None = None,
    month_to: int | None = None,
) -> list[dict[str, Any]]:
    sql = f"""
        SELECT
            category_l1 AS category,
            ROUND(SUM(revenue_amount), 2) AS revenue,
            ROUND(SUM(gross_profit_amount), 2) AS gross_profit
        FROM {mart_table("mart_revenue_monthly")}
        WHERE month_date_key
              BETWEEN %(month_from)s AND %(month_to)s
        GROUP BY category_l1
        ORDER BY revenue DESC
    """

    return await _query(
        sql,
        _range(month_from, month_to),
    )


async def revenue_by_region(
    month_from: int | None = None,
    month_to: int | None = None,
) -> list[dict[str, Any]]:
    sql = f"""
        SELECT
            region,
            ROUND(SUM(revenue_amount), 2) AS revenue,
            ROUND(SUM(gross_profit_amount), 2) AS gross_profit
        FROM {mart_table("mart_revenue_monthly")}
        WHERE month_date_key
              BETWEEN %(month_from)s AND %(month_to)s
        GROUP BY region
        ORDER BY revenue DESC
    """

    return await _query(
        sql,
        _range(month_from, month_to),
    )


async def top_products(
    month_from: int | None = None,
    month_to: int | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    sql = f"""
        SELECT
            product.product_id,
            MAX(product.product_name) AS product_name,
            MAX(product.category_l1) AS category,
            ROUND(SUM(sales.revenue_amount), 2) AS revenue,
            ROUND(SUM(sales.gross_profit_amount), 2) AS gross_profit,
            SUM(sales.quantity) AS quantity
        FROM {gold_table("fact_sales")} sales
        JOIN {gold_table("dim_product")} product
          ON product.product_sk = sales.product_sk
        WHERE sales.order_state != 'cancel'
          AND FLOOR(sales.order_date_key / 100) * 100 + 1
              BETWEEN %(month_from)s AND %(month_to)s
        GROUP BY product.product_id
        ORDER BY revenue DESC
        LIMIT %(limit)s
    """

    params = {
        **_range(month_from, month_to),
        "limit": limit,
    }

    return await _query(sql, params)


DashboardCallable = Callable[..., Awaitable[Any]]


DASHBOARD_QUERIES: dict[str, DashboardCallable] = {
    "kpi": kpi_summary,
    "revenue-trend": revenue_trend,
    "by-category": revenue_by_category,
    "by-region": revenue_by_region,
    "top-products": top_products,
}