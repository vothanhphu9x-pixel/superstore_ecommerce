import hashlib
import json
import os
from pathlib import Path
        
import boto3
import pandas as pd
import snowflake.connector
from dotenv import load_dotenv


load_dotenv(Path(__file__).with_name(".env"))

MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY")
BUCKET = os.getenv("MINIO_BUCKET")
LOCAL_DIR = os.getenv("MINIO_LOCAL_DIR", "/tmp/minio_downloads")

SNOWFLAKE_USER = os.getenv("SNOWFLAKE_USER")
SNOWFLAKE_PASSWORD = os.getenv("SNOWFLAKE_PASSWORD")
SNOWFLAKE_ACCOUNT = os.getenv("SNOWFLAKE_ACCOUNT")
SNOWFLAKE_WAREHOUSE = os.getenv("SNOWFLAKE_WAREHOUSE")
SNOWFLAKE_DB = os.getenv("SNOWFLAKE_DB")
SNOWFLAKE_SCHEMA = os.getenv("SNOWFLAKE_SCHEMA")
SNOWFLAKE_LOADER_ROLE = os.getenv("SNOWFLAKE_LOADER_ROLE")

# 44 bảng CDC + 4 bảng CSV batch.
TABLES = [
    "sale_order", "sale_order_line",
    "account_move", "account_move_line", "account_account", "account_journal",
    "account_payment", "account_partial_reconcile",
    "purchase_order", "purchase_order_line",
    "stock_move", "stock_picking", "delivery_carrier", "stock_location",
    "stock_valuation_layer", "stock_quant",
    "mrp_production", "mrp_workorder", "stock_scrap",
    "mrp_workcenter_productivity", "mrp_workcenter",
    "mrp_workcenter_productivity_loss", "mrp_bom",
    "crm_lead", "crm_stage", "crm_lost_reason",
    "utm_campaign", "utm_source", "utm_medium",
    "res_partner", "res_partner_category", "res_partner_res_partner_category_rel",
    "res_country", "res_country_state", "product_template", "product_product",
    "product_category", "uom_uom", "hr_employee", "hr_contract",
    "hr_department", "hr_job", "res_users", "stock_warehouse",
    "email_campaigns", "ad_performance_daily", "ab_test",
    "marketing_campaigns_master",
]


def _required(value, name):
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def download_from_minio():
    """Tải toàn bộ Parquet theo paginator; bỏ qua marker và object không phải dữ liệu."""
    os.makedirs(LOCAL_DIR, exist_ok=True)
    s3 = boto3.client(
        "s3",
        endpoint_url=_required(MINIO_ENDPOINT, "MINIO_ENDPOINT"),
        aws_access_key_id=_required(MINIO_ACCESS_KEY, "MINIO_ACCESS_KEY"),
        aws_secret_access_key=_required(MINIO_SECRET_KEY, "MINIO_SECRET_KEY"),
    )
    bucket = _required(BUCKET, "MINIO_BUCKET")
    paginator = s3.get_paginator("list_objects_v2")

    local_files = {}
    for table in TABLES:
        table_dir = os.path.join(LOCAL_DIR, table)
        os.makedirs(table_dir, exist_ok=True)
        local_files[table] = []

        for page in paginator.paginate(Bucket=bucket, Prefix=f"{table}/"):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                if not key.lower().endswith(".parquet"):
                    continue

                # Hash full object key để hai partition không ghi đè cùng basename local.
                key_hash = hashlib.md5(key.encode("utf-8")).hexdigest()[:12]
                local_file = os.path.join(
                    table_dir,
                    f"{key_hash}_{os.path.basename(key)}",
                )
                s3.download_file(bucket, key, local_file)

                # Security remediation: raw objects cũ có thể được tạo trước khi Debezium
                # exclude credential fields. Redact rồi overwrite đúng object để MinIO
                # không tiếp tục giữ password hash/TOTP seed trong lịch sử.
                if table == "res_users":
                    frame = pd.read_parquet(local_file, engine="fastparquet")
                    sensitive_columns = [
                        column
                        for column in ("password", "totp_secret")
                        if column in frame.columns
                    ]
                    if sensitive_columns:
                        frame = frame.drop(columns=sensitive_columns)
                        frame.to_parquet(local_file, engine="fastparquet", index=False)
                        s3.upload_file(local_file, bucket, key)
                        print(f"🔒 Redacted credential fields from s3://{bucket}/{key}")

                local_files[table].append(local_file)

    manifest_path = os.path.join(LOCAL_DIR, "_download_manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as manifest_file:
        json.dump(local_files, manifest_file)
    return manifest_path


def load_to_snowflake(**kwargs):
    manifest_path = kwargs["ti"].xcom_pull(task_ids="download_minio")
    if not manifest_path or not os.path.isfile(manifest_path):
        raise RuntimeError("Không tìm thấy manifest file sau bước download MinIO.")
    with open(manifest_path, encoding="utf-8") as manifest_file:
        local_files = json.load(manifest_file)
    if not local_files or not any(local_files.values()):
        raise RuntimeError("MinIO không có file Parquet để nạp; dừng DAG thay vì báo thành công giả.")

    connect_args = {
        "user": _required(SNOWFLAKE_USER, "SNOWFLAKE_USER"),
        "password": _required(SNOWFLAKE_PASSWORD, "SNOWFLAKE_PASSWORD"),
        "account": _required(SNOWFLAKE_ACCOUNT, "SNOWFLAKE_ACCOUNT"),
        "warehouse": _required(SNOWFLAKE_WAREHOUSE, "SNOWFLAKE_WAREHOUSE"),
        "database": _required(SNOWFLAKE_DB, "SNOWFLAKE_DB"),
        "schema": _required(SNOWFLAKE_SCHEMA, "SNOWFLAKE_SCHEMA"),
    }
    connect_args["role"] = _required(SNOWFLAKE_LOADER_ROLE,"SNOWFLAKE_LOADER_ROLE",)

    conn = snowflake.connector.connect(**connect_args)
    cur = conn.cursor()

    try:
        for table in TABLES:
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS {SNOWFLAKE_DB}.{SNOWFLAKE_SCHEMA}.{table} (
                    raw_data VARIANT
                )
            """)

        # One-time/idempotent remediation cho dữ liệu res_users đã land trước khi connector
        # bật column.exclude.list. Đồng thời chuẩn hóa lại record_hash trên payload đã redact
        # để replay object MinIO cũ không tạo thêm duplicate.
        res_users_table = f"{SNOWFLAKE_DB}.{SNOWFLAKE_SCHEMA}.res_users"
        cur.execute(f"""
            UPDATE {res_users_table}
            SET raw_data = OBJECT_INSERT(
                OBJECT_DELETE(raw_data, 'password', 'totp_secret'),
                'record_hash',
                MD5(TO_JSON(OBJECT_DELETE(
                    raw_data,
                    'password',
                    'totp_secret',
                    'record_hash',
                    'ingested_at'
                ))),
                TRUE
            )
            WHERE raw_data:password IS NOT NULL
               OR raw_data:totp_secret IS NOT NULL
        """)

        for table, files in local_files.items():
            if not files:
                continue

            fully_qualified_table = f"{SNOWFLAKE_DB}.{SNOWFLAKE_SCHEMA}.{table}"
            temp_table = f"{fully_qualified_table}_TEMP"

            # Xóa stage của riêng bảng trước khi PUT để lần retry không COPY file cũ sót lại.
            cur.execute(f"REMOVE @~/{table}/")
            for local_file in files:
                cur.execute(
                    f"PUT file://{local_file} @~/{table}/ "
                    "AUTO_COMPRESS=FALSE OVERWRITE=TRUE"
                )

            cur.execute(f"CREATE OR REPLACE TEMP TABLE {temp_table} LIKE {fully_qualified_table}")
            cur.execute(f"""
                COPY INTO {temp_table} (raw_data)
                FROM @~/{table}/
                FILE_FORMAT = (TYPE = PARQUET)
                ON_ERROR = 'ABORT_STATEMENT'
            """)

            copy_results = cur.fetchall()
            failed = []
            for row in copy_results:
                status = str(row[1]).upper()
                errors_seen = int(row[5] or 0) if len(row) > 5 else 0
                if status not in ("LOADED", "LOAD_SKIPPED") or errors_seen > 0:
                    failed.append(row)
            if failed:
                raise RuntimeError(f"COPY INTO {table} không hoàn tất: {failed[:3]}")

            # record_hash theo từng record. Với CSV, metadata source_batch_id nằm trong
            # raw_data nên A → B → A vẫn là phiên bản mới; file giống hệt liên tiếp đã
            # được csv_loader chặn bằng file hash.
            sanitized_raw_data = (
                "OBJECT_DELETE(s.raw_data, 'password', 'totp_secret')"
                if table == "res_users"
                else "s.raw_data"
            )
            cur.execute(f"""
                INSERT INTO {fully_qualified_table} (raw_data)
                WITH sanitized AS (
                    SELECT {sanitized_raw_data} AS raw_data
                    FROM {temp_table} s
                ),
                prepared AS (
                    SELECT
                        s.raw_data,
                        MD5(TO_JSON(s.raw_data)) AS record_hash,
                        ROW_NUMBER() OVER (
                            PARTITION BY MD5(TO_JSON(s.raw_data))
                            ORDER BY MD5(TO_JSON(s.raw_data))
                        ) AS row_num
                    FROM sanitized s
                )
                SELECT
                    OBJECT_INSERT(
                        OBJECT_INSERT(
                            p.raw_data,
                            'ingested_at',
                            CURRENT_TIMESTAMP()::STRING,
                            TRUE
                        ),
                        'record_hash',
                        p.record_hash,
                        TRUE
                    )
                FROM prepared p
                WHERE p.row_num = 1
                  AND NOT EXISTS (
                      SELECT 1
                      FROM {fully_qualified_table} target
                      WHERE target.raw_data:record_hash::STRING = p.record_hash
                  )
            """)

            cur.execute(f"REMOVE @~/{table}/")
            conn.commit()
            print(f"✅ Loaded {table} safely.")
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()
        for files in local_files.values():
            for local_file in files:
                if os.path.exists(local_file):
                    os.remove(local_file)
        if os.path.exists(manifest_path):
            os.remove(manifest_path)


if __name__ == "__main__":
    raise SystemExit("Run this module through the Airflow DAG.")
