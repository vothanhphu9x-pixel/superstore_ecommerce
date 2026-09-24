import re

from core.config import get_settings


_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")


def _identifier(value: str) -> str:
    if not _IDENTIFIER_PATTERN.fullmatch(value):
        raise ValueError(f"Invalid Snowflake identifier: {value!r}")

    return value


def gold_table(table: str) -> str:
    settings = get_settings()

    database = _identifier(settings.snowflake_database)
    schema = _identifier(settings.snowflake_gold_schema)
    table_name = _identifier(table)

    return f"{database}.{schema}.{table_name}"


def mart_table(table: str) -> str:
    settings = get_settings()

    database = _identifier(settings.snowflake_database)
    schema = _identifier(settings.snowflake_mart_schema)
    table_name = _identifier(table)

    return f"{database}.{schema}.{table_name}"
