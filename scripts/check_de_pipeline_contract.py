#!/usr/bin/env python3
"""Static contract checks for the DE pipeline; does not require external services."""

import ast
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data_platform"


def literal_assignment(path, name):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return ast.literal_eval(node.value)
    raise AssertionError(f"Missing literal {name} in {path}")


def main():
    debezium_tables = set(literal_assignment(
        DATA / "Debezium_producer" / "Debezium.py", "table_list"
    ))
    consumer_tables = set(literal_assignment(
        DATA / "minio_consumer" / "consumer.py", "SOURCE_TABLES"
    ))
    warehouse_tables = set(literal_assignment(
        DATA / "Data_warehouse" / "Minio_snowflake.py", "TABLES"
    ))
    csv_tables = set(literal_assignment(
        DATA / "csv_loader" / "loader.py", "CSV_FILES"
    ).values())

    assert debezium_tables == consumer_tables, "Debezium and Kafka consumer table lists differ"

    raw_cdc_tables = {name.removeprefix("public.") for name in debezium_tables}
    assert warehouse_tables == raw_cdc_tables | csv_tables, (
        "Snowflake loader table list differs from CDC + CSV sources"
    )

    source_yml = (
        DATA / "superstore_db" / "models" / "staging" / "source.yml"
    ).read_text(encoding="utf-8")
    dbt_sources = set(re.findall(r"^\s{6}- name: ([a-z0-9_]+)$", source_yml, re.MULTILINE))
    assert dbt_sources == warehouse_tables, "dbt source.yml differs from Snowflake raw tables"

    staging_dir = DATA / "superstore_db" / "models" / "staging"
    staging_models = {
        path.stem.removeprefix("stg_")
        for path in staging_dir.glob("stg_*.sql")
    }
    assert staging_models == warehouse_tables, "Every raw table must have exactly one stg_* model"

    compose_path = DATA / "docker-compose.yml"
    compose = compose_path.read_text(encoding="utf-8")
    assert ":latest" not in compose, "Docker images must not use floating :latest tags"
    assert compose.count("KAFKA_BOOTSTRAP_SERVERS=kafka:9092,kafka_2:9093") == 2, (
        "Airflow webserver and scheduler must each use the internal Kafka endpoints exactly once"
    )
    assert compose.count("MINIO_ENDPOINT_URL=http://minio:9000") == 2, (
        "Airflow webserver and scheduler must use the internal MinIO endpoint"
    )
    assert compose.count("MINIO_ENDPOINT=http://minio:9000") == 2, (
        "Airflow CSV/Snowflake tasks must use the internal MinIO endpoint"
    )

    root_env_example = (DATA / ".env.example").read_text(encoding="utf-8")
    required_runtime_keys = {
        "KAFKA_BOOTSTRAP_SERVERS",
        "KAFKA_CONSUMER_GROUP_ID",
        "MINIO_ENDPOINT_URL",
        "MINIO_ENDPOINT",
        "MINIO_ACCESS_KEY",
        "MINIO_SECRET_KEY",
        "MINIO_BUCKET_NAME",
        "MINIO_BUCKET",
        "DEBEZIUM_CONNECTOR_URL",
        "POSTGRES_HOST",
        "POSTGRES_PASSWORD",
        "SNOWFLAKE_ACCOUNT",
        "SNOWFLAKE_USER",
        "SNOWFLAKE_PASSWORD",
        "SNOWFLAKE_LOADER_ROLE",
        "SNOWFLAKE_DBT_ROLE",
        "DBT_SCHEMA",
        "DATA_SOURCE_DIR",
    }
    example_keys = set(re.findall(r"^([A-Z][A-Z0-9_]*)=", root_env_example, re.MULTILINE))
    missing_keys = required_runtime_keys - example_keys
    assert not missing_keys, f"data_platform/.env.example misses runtime keys: {sorted(missing_keys)}"

    debezium_code = (
        DATA / "Debezium_producer" / "Debezium.py"
    ).read_text(encoding="utf-8")
    assert '"column.exclude.list"' in debezium_code
    assert "public.res_users.password" in debezium_code
    assert "public.res_users.totp_secret" in debezium_code

    consumer_code = (
        DATA / "minio_consumer" / "consumer.py"
    ).read_text(encoding="utf-8")
    assert 'record.pop("password", None)' in consumer_code
    assert 'record.pop("totp_secret", None)' in consumer_code

    loader_code = (
        DATA / "Data_warehouse" / "Minio_snowflake.py"
    ).read_text(encoding="utf-8")
    assert "OBJECT_DELETE(raw_data, 'password', 'totp_secret')" in loader_code
    assert 'frame.drop(columns=sensitive_columns)' in loader_code

    dag_code = (
        DATA / "docker" / "dags" / "batching_pipline_snowflake.py"
    ).read_text(encoding="utf-8")
    assert "task_configure_debezium >> task_check_debezium" in dag_code, (
        "DAG must reconcile Debezium config before checking connector health"
    )

    contract_snapshot = (
        DATA / "superstore_db" / "snapshots" / "snap_hr_contract.sql"
    ).read_text(encoding="utf-8")
    for tracked_column in ("employee_id", "wage", "date_start", "date_end", "state", "is_deleted"):
        assert f"'{tracked_column}'" in contract_snapshot, (
            f"snap_hr_contract must track {tracked_column} for complete SCD2 history"
        )

    forbidden_paths = {
        "stg_mrp_production.sql": "raw_data:qty_produced",
        "stg_mrp_workcenter_productivity.sql": "raw_data:production_id",
        "stg_product_template.sql": "raw_data:standard_price",
        "stg_stock_quant.sql": "raw_data:available_quantity",
    }
    for filename, expression in forbidden_paths.items():
        text = (staging_dir / filename).read_text(encoding="utf-8")
        assert expression not in text, f"Non-stored Odoo field found: {expression}"

    print(
        "DE pipeline static contract: OK "
        "(source parity, runtime config, security, DAG order, SCD2 and Odoo fields)."
    )


if __name__ == "__main__":
    main()
