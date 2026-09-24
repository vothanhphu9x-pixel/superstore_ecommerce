import asyncio
import logging
from contextlib import contextmanager
from typing import Any, Iterator

import snowflake.connector

from core.config import get_settings


logger = logging.getLogger("analytics.connector")


class QueryResultTooLarge(RuntimeError):
    pass


def _connection_parameters() -> dict[str, Any]:
    settings = get_settings()

    required = {
        "SNOWFLAKE_ACCOUNT": settings.snowflake_account,
        "SNOWFLAKE_USER": settings.snowflake_user,
        "SNOWFLAKE_PASSWORD": settings.snowflake_password,
    }

    missing = [
        name
        for name, value in required.items()
        if not value or value.startswith("CHANGE_ME")
    ]

    if missing:
        raise RuntimeError(
            "Missing Snowflake configuration: " + ", ".join(missing)
        )

    return {
        "account": settings.snowflake_account,
        "user": settings.snowflake_user,
        "password": settings.snowflake_password,
        "database": settings.snowflake_database,
        "schema": settings.snowflake_gold_schema,
        "warehouse": settings.snowflake_warehouse,
        "role": settings.snowflake_role,
        "login_timeout": settings.snowflake_query_timeout,
        "network_timeout": settings.snowflake_query_timeout,
        "application": "superstore_api",
        "session_parameters": {
            "STATEMENT_TIMEOUT_IN_SECONDS": settings.snowflake_query_timeout,
            "QUERY_TAG": "superstore_api_readonly",
        },
    }


@contextmanager
def _connection() -> Iterator[Any]:
    connection = snowflake.connector.connect(
        **_connection_parameters()
    )

    try:
        yield connection
    finally:
        connection.close()


def _run_query_sync(
    sql: str,
    params: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    settings = get_settings()

    logger.info("Running Snowflake query: %s", " ".join(sql.split())[:250])

    with _connection() as connection:
        cursor = connection.cursor(snowflake.connector.DictCursor)

        try:
            cursor.execute(sql, params or {})

            rows = cursor.fetchmany(settings.snowflake_max_rows + 1)

            if len(rows) > settings.snowflake_max_rows:
                raise QueryResultTooLarge(
                    "Snowflake result exceeds "
                    f"SNOWFLAKE_MAX_ROWS={settings.snowflake_max_rows}"
                )

            return rows
        finally:
            cursor.close()


async def run_query(
    sql: str,
    params: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    return await asyncio.to_thread(
        _run_query_sync,
        sql,
        params,
    )


async def snowflake_health() -> dict[str, str]:
    rows = await run_query("SELECT 1 AS STATUS")

    if not rows or rows[0].get("STATUS") != 1:
        raise RuntimeError("Snowflake readiness query returned unexpected data.")

    return {"status": "healthy"}