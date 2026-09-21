import hashlib
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import boto3
import pandas as pd
from botocore.exceptions import ClientError
from dotenv import load_dotenv

load_dotenv(Path(__file__).with_name(".env"))

# -------- Config --------
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY")
BUCKET = os.getenv("MINIO_BUCKET")
DATA_SOURCE_DIR = os.getenv("DATA_SOURCE_DIR", "/Users/macos/Desktop/Superstore_ecommerce/odoo_dev/CRM_Marketing_source")

# CSV sự kiện/metadata nguồn ngoài Odoo — nạp thẳng vào MinIO,
# KHÔNG qua Debezium/Kafka. Chỉ ingest bốn raw source production;
# funnel tháng được dbt tổng hợp từ Ads, CRM, Sales và Customer Acquisition.
# Nguồn: odoo_dev/CRM_Marketing_source/*.csv (mount read-only qua docker-compose.yml)
# Mapping = superstore_pipeline_lineage.drawio, lane CRM & MARKETING
CSV_FILES = {
    "email_campaigns.csv": "email_campaigns",
    "ad_performance_daily.csv": "ad_performance_daily",
    "ab_test_results.csv": "ab_test",
    "marketing_campaigns_master.csv": "marketing_campaigns_master",
}

CSV_KEYS = {
    "email_campaigns": ["email_id"],
    "ad_performance_daily": ["date", "campaign_id", "channel"],
    "ab_test": ["variant_id"],
    "marketing_campaigns_master": ["campaign_id"],
}


def _file_hash(path):
    """MD5 nội dung file CSV — dùng để nhận biết dữ liệu có đổi so với lần nạp trước không."""
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _last_loaded_hash(s3, table_name):
    """Đọc marker hash của lần upload gần nhất, None nếu chưa từng nạp."""
    try:
        obj = s3.get_object(Bucket=BUCKET, Key=f"{table_name}/_last_hash.txt")
        return obj["Body"].read().decode()
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") in ("NoSuchKey", "404"):
            return None
        raise


def _mark_loaded(s3, table_name, file_hash):
    s3.put_object(Bucket=BUCKET, Key=f"{table_name}/_last_hash.txt", Body=file_hash.encode())


def _validate_csv(df, filename, table_name):
    keys = CSV_KEYS[table_name]
    missing = [column for column in keys if column not in df.columns]
    if missing:
        raise ValueError(f"{filename} thiếu cột khóa bắt buộc: {', '.join(missing)}")
    if df.empty:
        raise ValueError(f"{filename} không có dữ liệu; không ghi đè snapshot nguồn bằng file rỗng.")
    if df[keys].isnull().any(axis=None):
        raise ValueError(f"{filename} có NULL trong khóa nguồn: {', '.join(keys)}")
    if df.duplicated(keys).any():
        raise ValueError(f"{filename} trùng grain nguồn: {', '.join(keys)}")


def load_csv_to_minio():
    """Đọc từng CSV ở DATA_SOURCE_DIR, convert Parquet, upload vào MinIO raw/<table>/date=.../

    Bỏ qua nếu nội dung CSV không đổi so với lần nạp gần nhất (so hash),
    tránh upload lặp lại y hệt dữ liệu tĩnh mỗi lần DAG chạy.
    """
    s3 = boto3.client(
        "s3",
        endpoint_url=MINIO_ENDPOINT,
        aws_access_key_id=MINIO_ACCESS_KEY,
        aws_secret_access_key=MINIO_SECRET_KEY,
    )

    if BUCKET not in [b["Name"] for b in s3.list_buckets()["Buckets"]]:
        s3.create_bucket(Bucket=BUCKET)

    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y-%m-%d")

    for filename, table_name in CSV_FILES.items():
        local_path = os.path.join(DATA_SOURCE_DIR, filename)
        if not os.path.exists(local_path):
            raise FileNotFoundError(f"Không tìm thấy source bắt buộc: {local_path}")

        file_hash = _file_hash(local_path)
        if file_hash == _last_loaded_hash(s3, table_name):
            print(f"⏭️  Bỏ qua {filename} — nội dung không đổi so với lần nạp trước.")
            continue

        df = pd.read_csv(local_path)
        _validate_csv(df, filename, table_name)

        # Metadata thuộc lần nạp toàn file. Nhờ batch id/hash, chuỗi A → B → A vẫn
        # được nhận diện là một phiên bản nguồn mới, còn file giống hệt liên tiếp
        # vẫn được marker phía trên bỏ qua.
        loaded_at = datetime.now(timezone.utc)
        source_batch_id = f"{loaded_at.strftime('%Y%m%dT%H%M%S%fZ')}_{file_hash[:12]}"
        df["_source_batch_id"] = source_batch_id
        df["_source_file_hash"] = file_hash
        df["_source_loaded_at"] = loaded_at.isoformat()

        timestamp = loaded_at.strftime("%H%M%S%f")
        with tempfile.NamedTemporaryFile(
            prefix=f"{table_name}_", suffix=".parquet", delete=False
        ) as temp_file:
            parquet_path = temp_file.name

        try:
            df.to_parquet(parquet_path, engine="fastparquet", index=False)
            s3_key = f"{table_name}/date={date_str}/{table_name}_{timestamp}.parquet"
            s3.upload_file(parquet_path, BUCKET, s3_key)
        finally:
            if os.path.exists(parquet_path):
                os.remove(parquet_path)

        # Chỉ đánh dấu sau khi upload Parquet thành công.
        _mark_loaded(s3, table_name, file_hash)

        print(f"✅ Uploaded {len(df)} dòng từ {filename} → s3://{BUCKET}/{s3_key}")


if __name__ == "__main__":
    load_csv_to_minio()
