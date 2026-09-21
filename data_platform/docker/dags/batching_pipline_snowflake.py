import os
from datetime import timedelta

import pendulum
import requests
from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator

# goi code python
from minio_consumer.consumer import load_minio
from Data_warehouse.Minio_snowflake import download_from_minio, load_to_snowflake
from csv_loader.loader import load_csv_to_minio

DBT_BIN = "/home/airflow/dbt-venv/bin/dbt"

# DAG
default_args = {
    "owner": "airflow",
    "retries": 1,
    "retry_delay": timedelta(minutes=1),
}


def check_debezium_health():
    connectors_url = os.getenv(
        "DEBEZIUM_CONNECTOR_URL",
        "http://connect:8083/connectors",
    )
    connector_name = os.getenv("DEBEZIUM_CONNECTOR_NAME", "odoo-connector")
    response = requests.get(
        f"{connectors_url.rstrip('/')}/{connector_name}/status",
        timeout=15,
    )
    response.raise_for_status()
    status = response.json()
    connector_running = status.get("connector", {}).get("state") == "RUNNING"
    tasks = status.get("tasks", [])
    tasks_running = tasks and all(task.get("state") == "RUNNING" for task in tasks)
    if not connector_running or not tasks_running:
        raise RuntimeError(f"Debezium connector is not healthy: {status}")

with DAG(
    dag_id="batching_pipeline_snowflake",
    default_args=default_args,
    schedule="0 9 * * *",  # 09:00 Asia/Ho_Chi_Minh mỗi ngày
    start_date=pendulum.datetime(2026, 6, 10, tz="Asia/Ho_Chi_Minh"),
    catchup=False,
    max_active_runs=1,
    dagrun_timeout=timedelta(hours=2),
) as dag:

    # Đồng bộ connector config mỗi run. Nếu table.include.list có bảng mới,
    # Debezium.py gửi incremental snapshot signal để backfill dữ liệu lịch sử.
    task_configure_debezium = BashOperator(
        task_id="configure_debezium",
        bash_command="python /opt/airflow/Debezium_producer/Debezium.py",
        env={
            "DEBEZIUM_CONNECTOR_URL": "http://connect:8083/connectors",
            "KAFKA_BOOTSTRAP_SERVERS": "kafka:9092,kafka_2:9093",
        },
        append_env=True,
        execution_timeout=timedelta(minutes=3),
    )

    task_check_debezium = PythonOperator(
        task_id="check_debezium_health",
        python_callable=check_debezium_health,
        execution_timeout=timedelta(minutes=2),
    )

    # 1. Load 4 CSV raw marketing ngoài Odoo (campaign/ads/email/A-B) vào MinIO.
    # Funnel monthly và customer acquisition được dbt tạo từ Odoo + raw source,
    # không ingest các file synthetic legacy.
    # Tự skip nếu nội dung CSV không đổi so với lần chạy trước (hash-check trong loader.py).
    task_load_csv = PythonOperator(
        task_id='load_csv_to_minio',
        python_callable=load_csv_to_minio,
    )

    # 2. load into minio
    task_load_minio = PythonOperator(
        task_id='load_minio',
        python_callable=load_minio,
        execution_timeout=timedelta(minutes=10),
    )
    
    # 3. Download files from Minio
    task_dowload_minio = PythonOperator(
        task_id="download_minio",
        python_callable=download_from_minio,
    )

    # 4. Load files to Snowflake
    task_load_snowflake = PythonOperator(
        task_id="load_snowflake",
        python_callable=load_to_snowflake,
        provide_context=True,
    )

    # 4.1 dbt deps (chạy 1 lần/run, dùng chung cho mọi task dbt phía sau —
    # tránh 10 lần gọi mạng tới package hub lặp lại vô ích mỗi ngày)
    task_dbt_deps = BashOperator(
        task_id="dbt_deps",
        bash_command=f'cd /opt/airflow/superstore_db && {DBT_BIN} deps --profiles-dir .dbt'
    )

    # 5. staging dbt
    task_staging_dbt = BashOperator(
        task_id="dbt_staging",
        bash_command=f'cd /opt/airflow/superstore_db && {DBT_BIN} run --select staging --profiles-dir .dbt'
    )

    # 5.1. test staging dbt
    task_test_staging_dbt = BashOperator(
        task_id="dbt_staging_test",
        bash_command=(
            f'cd /opt/airflow/superstore_db && {DBT_BIN} test '
            '--select staging --indirect-selection cautious --profiles-dir .dbt'
        )
    )

    # 6. snapshot dbt
    task_snapshot_dbt = BashOperator(
        task_id="dbt_snapshot",
        bash_command=f'cd /opt/airflow/superstore_db && {DBT_BIN} snapshot --profiles-dir .dbt'
    )

    # 6.1. test snapshot dbt
    # resource_type:snapshot (KHÔNG phải --select snapshot, thư mục thật là
    # snapshots/ số nhiều — bare "snapshot" không khớp node nào, test cũ chạy 0 test)
    task_test_snapshot_dbt = BashOperator(
        task_id="dbt_snapshot_test",
        bash_command=(
            f'cd /opt/airflow/superstore_db && {DBT_BIN} test '
            '--select resource_type:snapshot --indirect-selection cautious --profiles-dir .dbt'
        )
    )

    # 7. silver dbt
    task_silver_dbt = BashOperator(
        task_id="dbt_silver",
        bash_command=f'cd /opt/airflow/superstore_db && {DBT_BIN} run --select silver --profiles-dir .dbt'
    )

    # 7.1. test silver dbt
    task_test_silver_dbt = BashOperator(
        task_id="dbt_silver_test",
        bash_command=(
            f'cd /opt/airflow/superstore_db && {DBT_BIN} test '
            '--select silver --indirect-selection cautious --profiles-dir .dbt'
        )
    )

    # 8. gold dbt
    # Mart CHỈ đọc từ Gold (naming_convention §1) — thiếu bước này thì mart luôn
    # đọc gold cũ/rỗng, không lỗi rõ ràng nhưng số liệu sai/stale mỗi ngày.
    task_gold_dbt = BashOperator(
        task_id="dbt_gold",
        bash_command=f'cd /opt/airflow/superstore_db && {DBT_BIN} run --select gold --profiles-dir .dbt'
    )

    # 8.1. test gold dbt
    task_test_gold_dbt = BashOperator(
        task_id="dbt_gold_test",
        bash_command=(
            f'cd /opt/airflow/superstore_db && {DBT_BIN} test '
            '--select gold --indirect-selection cautious --profiles-dir .dbt'
        )
    )

    # 9. mart dbt
    task_mart_dbt = BashOperator(
        task_id="dbt_mart",
        bash_command=f'cd /opt/airflow/superstore_db && {DBT_BIN} run --select mart --profiles-dir .dbt'
    )

    # 9.1. test mart dbt
    task_test_mart_dbt = BashOperator(
        task_id="dbt_mart_test",
        bash_command=(
            f'cd /opt/airflow/superstore_db && {DBT_BIN} test '
            '--select mart --indirect-selection cautious --profiles-dir .dbt'
        )
    )

    # Singular tests kiểm tra hợp đồng xuyên nhiều layer. Chỉ chạy sau khi
    # Staging, Snapshot, Silver, Gold và Mart đã được tạo đầy đủ.
    task_test_pipeline_contract = BashOperator(
        task_id="dbt_pipeline_contract_test",
        bash_command=(
            f'cd /opt/airflow/superstore_db && {DBT_BIN} test '
            '--select test_type:singular --profiles-dir .dbt'
        )
    )

# flow
task_configure_debezium >> task_check_debezium >> task_load_csv >> task_load_minio >> task_dowload_minio >> task_load_snowflake >> task_dbt_deps >> \
task_staging_dbt >> task_test_staging_dbt >> task_snapshot_dbt >> task_test_snapshot_dbt >> \
task_silver_dbt >> task_test_silver_dbt >> task_gold_dbt >> task_test_gold_dbt >> \
task_mart_dbt >> task_test_mart_dbt >> task_test_pipeline_contract
