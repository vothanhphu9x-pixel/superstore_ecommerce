import json
import os
import time
import uuid
from pathlib import Path

import requests
from confluent_kafka import Producer
from confluent_kafka.admin import AdminClient, NewTopic
from dotenv import load_dotenv


load_dotenv(Path(__file__).with_name(".env"))

# Danh sách 44 bảng Odoo core được đồng bộ bằng CDC.
table_list = [
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


def _wait_until_running(connectors_url, connector_name, timeout_seconds=60):
    deadline = time.time() + timeout_seconds
    status_url = f"{connectors_url.rstrip('/')}/{connector_name}/status"
    while time.time() < deadline:
        response = requests.get(status_url, timeout=15)
        if response.ok:
            status = response.json()
            connector_running = status.get("connector", {}).get("state") == "RUNNING"
            tasks = status.get("tasks", [])
            tasks_running = tasks and all(task.get("state") == "RUNNING" for task in tasks)
            if connector_running and tasks_running:
                return
        time.sleep(2)
    raise RuntimeError(f"Connector {connector_name} did not reach RUNNING state in time.")


def _ensure_signal_topic(topic_name):
    """Debezium yêu cầu signaling topic có đúng một partition để giữ thứ tự signal."""
    bootstrap_servers = _required_env("KAFKA_BOOTSTRAP_SERVERS")
    admin = AdminClient({"bootstrap.servers": bootstrap_servers})
    metadata = admin.list_topics(timeout=15)

    if topic_name in metadata.topics:
        partition_count = len(metadata.topics[topic_name].partitions)
        if partition_count != 1:
            raise RuntimeError(
                f"Kafka signal topic {topic_name} has {partition_count} partitions; "
                "Debezium requires exactly 1. Recreate this topic with one partition."
            )
        return

    replication_factor = int(os.getenv("DEBEZIUM_SIGNAL_REPLICATION_FACTOR", "2"))
    futures = admin.create_topics([
        NewTopic(
            topic_name,
            num_partitions=1,
            replication_factor=replication_factor,
            config={"cleanup.policy": "delete"},
        )
    ])
    futures[topic_name].result(timeout=30)
    print(f"Created Debezium signal topic {topic_name} with one partition.")


def _request_incremental_snapshot(topic_prefix, tables):
    """Backfill only tables newly added to an existing connector."""
    if not tables:
        return

    producer = Producer({
        "bootstrap.servers": _required_env("KAFKA_BOOTSTRAP_SERVERS"),
        "enable.idempotence": True,
        "acks": "all",
    })
    signal_topic = os.getenv("DEBEZIUM_SIGNAL_TOPIC", f"{topic_prefix}-signal")
    signal = {
        "id": f"backfill-{uuid.uuid4()}",
        "type": "execute-snapshot",
        "data": {
            "type": "incremental",
            "data-collections": sorted(tables),
        },
    }
    producer.produce(
        signal_topic,
        key=topic_prefix,
        value=json.dumps(signal),
    )
    remaining = producer.flush(30)
    if remaining:
        raise RuntimeError(f"Could not deliver Debezium snapshot signal for {sorted(tables)}")
    print(f"Incremental snapshot requested for new tables: {', '.join(sorted(tables))}")


def build_connector_config():
    topic_prefix = os.getenv("KAFKA_TOPIC_PREFIX", "superstore_server")
    return {
        "name": os.getenv("DEBEZIUM_CONNECTOR_NAME", "odoo-connector"),
        "config": {
            "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
            "database.hostname": _required_env("POSTGRES_HOST"),
            "database.port": _required_env("POSTGRES_PORT"),
            "database.user": _required_env("POSTGRES_USER"),
            "database.password": _required_env("POSTGRES_PASSWORD"),
            "database.dbname": _required_env("POSTGRES_DB"),
            "topic.prefix": topic_prefix,
            "table.include.list": ",".join(table_list),
            # Không đưa credential hash/TOTP seed vào Kafka, MinIO hoặc Snowflake Bronze.
            "column.exclude.list": (
                "public.res_users.password,"
                "public.res_users.totp_secret"
            ),
            "plugin.name": "pgoutput",
            "slot.name": os.getenv("DEBEZIUM_SLOT_NAME", "superstore_slot"),
            "publication.autocreate.mode": "filtered",
            "tombstones.on.delete": "false",
            "decimal.handling.mode": "double",
            "topic.creation.default.replication.factor": "2",
            "topic.creation.default.partitions": "4",
            "snapshot.mode": "initial",
            # Kafka signal + read-only watermark cho phép snapshot bảng mới mà
            # không INSERT trực tiếp vào database nghiệp vụ Odoo.
            "signal.enabled.channels": "kafka",
            "signal.kafka.topic": os.getenv(
                "DEBEZIUM_SIGNAL_TOPIC", f"{topic_prefix}-signal"
            ),
            "signal.kafka.bootstrap.servers": _required_env("KAFKA_BOOTSTRAP_SERVERS"),
            "read.only": "true",
            "heartbeat.interval.ms": "10000",
        },
    }


def configure_connector():
    connector_config = build_connector_config()
    connectors_url = _required_env("DEBEZIUM_CONNECTOR_URL")
    connector_name = connector_config["name"]
    headers = {"Content-Type": "application/json"}
    _ensure_signal_topic(connector_config["config"]["signal.kafka.topic"])

    response = requests.post(
        connectors_url,
        headers=headers,
        json=connector_config,
        timeout=30,
    )
    if response.status_code == 201:
        _wait_until_running(connectors_url, connector_name)
        print("Connector created successfully; initial snapshot includes all configured tables.")
        return

    if response.status_code != 409:
        response.raise_for_status()

    config_url = f"{connectors_url.rstrip('/')}/{connector_name}/config"
    current_response = requests.get(config_url, timeout=30)
    current_response.raise_for_status()
    current_config = current_response.json()
    old_tables = set(filter(None, current_config.get("table.include.list", "").split(",")))

    update_response = requests.put(
        config_url,
        headers=headers,
        json=connector_config["config"],
        timeout=30,
    )
    update_response.raise_for_status()
    print("Connector already existed and its configuration was updated.")
    _wait_until_running(connectors_url, connector_name)

    new_tables = set(table_list) - old_tables
    if new_tables:
        _request_incremental_snapshot(
            connector_config["config"]["topic.prefix"],
            new_tables,
        )


if __name__ == "__main__":
    configure_connector()
