import json
import os
import tempfile
import time
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import boto3
import pandas as pd
from confluent_kafka import Consumer, KafkaError, TopicPartition
from dotenv import load_dotenv


load_dotenv(Path(__file__).with_name(".env"))

# Danh sách bảng nguồn phải khớp table_list trong Debezium_producer/Debezium.py.
SOURCE_TABLES = [
    "public.sale_order", "public.sale_order_line",
    "public.account_move", "public.account_move_line", "public.account_account",
    "public.account_journal", "public.account_payment", "public.account_partial_reconcile",
    "public.purchase_order", "public.purchase_order_line",
    "public.stock_picking", "public.delivery_carrier", "public.stock_move",
    "public.stock_location", "public.stock_valuation_layer", "public.stock_quant",
    "public.mrp_production", "public.mrp_workorder", "public.mrp_workcenter",
    "public.mrp_workcenter_productivity", "public.mrp_workcenter_productivity_loss",
    "public.stock_scrap", "public.mrp_bom",
    "public.crm_lead", "public.crm_stage", "public.crm_lost_reason",
    "public.utm_campaign", "public.utm_source", "public.utm_medium",
    "public.res_partner", "public.res_partner_category",
    "public.res_partner_res_partner_category_rel", "public.res_country",
    "public.res_country_state", "public.product_template", "public.product_product",
    "public.product_category", "public.uom_uom", "public.hr_employee",
    "public.hr_contract", "public.hr_department", "public.hr_job",
    "public.res_users", "public.stock_warehouse",
]


def _required_env(name):
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def load_minio():
    topic_prefix = os.getenv("KAFKA_TOPIC_PREFIX", "superstore_server")
    topics = [f"{topic_prefix}.{table}" for table in SOURCE_TABLES]

    consumer = Consumer({
        "bootstrap.servers": _required_env("KAFKA_BOOTSTRAP_SERVERS"),
        "group.id": _required_env("KAFKA_CONSUMER_GROUP_ID"),
        "auto.offset.reset": "earliest",
        # Chỉ commit sau khi file đã được ghi bền vững vào MinIO.
        "enable.auto.commit": False,
        "enable.auto.offset.store": False,
    })
    consumer.subscribe(topics)

    s3 = boto3.client(
        "s3",
        endpoint_url=_required_env("MINIO_ENDPOINT_URL"),
        aws_access_key_id=_required_env("MINIO_ACCESS_KEY"),
        aws_secret_access_key=_required_env("MINIO_SECRET_KEY"),
    )
    bucket = _required_env("MINIO_BUCKET_NAME")
    if bucket not in [item["Name"] for item in s3.list_buckets()["Buckets"]]:
        s3.create_bucket(Bucket=bucket)

    batch_size = int(os.getenv("BATCH_SIZE", "2000"))
    flush_interval = int(os.getenv("FLUSH_INTERVAL", "10"))
    inactivity_timeout = int(os.getenv("INACTIVITY_TIMEOUT", "20"))
    max_run_seconds = int(os.getenv("MAX_RUN_SECONDS", "300"))

    buffer = {topic: [] for topic in topics}
    pending_offsets = {topic: {} for topic in topics}
    last_flush_time = defaultdict(time.time)
    started_at = time.time()
    last_msg_time = started_at

    def write_to_minio(table_name, records):
        if not records:
            return

        now = datetime.now(timezone.utc)
        object_id = f"{now.strftime('%Y%m%dT%H%M%S%fZ')}_{uuid.uuid4().hex}"
        s3_key = (
            f"{table_name}/date={now.strftime('%Y-%m-%d')}/"
            f"{table_name}_{object_id}.parquet"
        )
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                prefix=f"{table_name}_", suffix=".parquet", delete=False
            ) as temp_file:
                temp_path = temp_file.name

            pd.DataFrame(records).to_parquet(
                temp_path, engine="fastparquet", index=False
            )
            s3.upload_file(temp_path, bucket, s3_key)
        finally:
            if temp_path and os.path.exists(temp_path):
                os.remove(temp_path)

        print(f"✅ Uploaded {len(records)} records to s3://{bucket}/{s3_key}")

    def flush_topic(topic):
        records = buffer[topic]
        offsets = pending_offsets[topic]
        if not records and not offsets:
            return

        if records:
            write_to_minio(topic.split(".")[-1], records)

        if offsets:
            consumer.commit(
                offsets=[
                    TopicPartition(topic, partition, offset + 1)
                    for partition, offset in offsets.items()
                ],
                asynchronous=False,
            )

        buffer[topic] = []
        pending_offsets[topic] = {}
        last_flush_time[topic] = time.time()

    print(
        "✅ Listening to Kafka; offsets commit only after MinIO upload. "
        f"Stop after {inactivity_timeout}s idle or {max_run_seconds}s runtime."
    )

    try:
        while True:
            msg = consumer.poll(timeout=1.0)

            if msg is not None:
                if msg.error():
                    if msg.error().code() in (
                        KafkaError._PARTITION_EOF,
                        KafkaError.UNKNOWN_TOPIC_OR_PART,
                    ):
                        continue
                    raise RuntimeError(f"Kafka error: {msg.error()}")

                last_msg_time = time.time()
                topic_name = msg.topic()

                if msg.value() is not None:
                    value = json.loads(msg.value().decode("utf-8"))
                    payload = value.get("payload", value)
                    op_type = payload.get("op")
                    source = payload.get("source", {})

                    if op_type == "d":
                        record = payload.get("before") or {}
                        if record:
                            record["cdc_status"] = "DELETED"
                            record["is_deleted"] = True
                    else:
                        record = payload.get("after") or {}
                        if record:
                            record["cdc_status"] = "ACTIVE"
                            record["is_deleted"] = False

                    if record:
                        # Defense in depth: connector đã exclude hai cột này, nhưng vẫn
                        # redact tại consumer để bảo vệ khi replay topic/config cũ.
                        if topic_name.endswith(".public.res_users"):
                            record.pop("password", None)
                            record.pop("totp_secret", None)
                        record["_cdc_ts_ms"] = source.get("ts_ms")
                        record["_cdc_lsn"] = source.get("lsn")
                        record["_kafka_topic"] = topic_name
                        record["_kafka_partition"] = msg.partition()
                        record["_kafka_offset"] = msg.offset()
                        buffer[topic_name].append(record)

                # Chỉ đánh dấu offset sau khi message đã parse/transform thành công.
                # Nếu JSON/payload lỗi, exception phải giữ offset chưa commit để retry/DLQ,
                # không được vô tình bỏ qua message lỗi trong final flush.
                pending_offsets[topic_name][msg.partition()] = max(
                    msg.offset(),
                    pending_offsets[topic_name].get(msg.partition(), -1),
                )

            current_time = time.time()
            for topic in topics:
                elapsed = current_time - last_flush_time[topic]
                should_flush = (
                    len(buffer[topic]) >= batch_size
                    or (pending_offsets[topic] and elapsed >= flush_interval)
                )
                if should_flush:
                    flush_topic(topic)

            if current_time - last_msg_time >= inactivity_timeout:
                print(f"💤 No new data for {inactivity_timeout}s; stopping this batch.")
                break

            if current_time - started_at >= max_run_seconds:
                print(f"⏱️ Reached MAX_RUN_SECONDS={max_run_seconds}; stopping this batch.")
                break
    finally:
        try:
            for topic in topics:
                flush_topic(topic)
        finally:
            consumer.close()
            print("✅ Consumer closed after final durable flush.")


if __name__ == "__main__":
    load_minio()
