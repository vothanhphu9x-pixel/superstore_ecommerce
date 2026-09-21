# Data Pipeline Discovery Result

## Status definitions

- **Verified** — đã chạy kiểm tra và có evidence.
- **Failed** — đã chạy nhưng kết quả không đạt.
- **Blocked** — chưa thể chạy vì thiếu dịch vụ, quyền hoặc kết nối.
- **Not Run** — chưa thực hiện trong lần validation này.
- **Not Applicable** — không thuộc phạm vi production hiện tại.

## Identification

- Validation date: 2026-09-21
- Environment: Local macOS / Docker Compose / Snowflake
- Scope: Odoo PostgreSQL → Debezium → Kafka → MinIO → Snowflake → dbt → Airflow
- Result status: Complete — all validation gates passed

> Các container/service hiện đang được tắt có chủ đích. Trạng thái **Verified** ghi nhận
> lần validation thành công gần nhất, không khẳng định service đang online tại thời điểm đọc.

## Source baseline

| Component | Current count |
|---|---:|
| Odoo CDC tables | 44 |
| External CSV production tables | 4 |
| Bronze sources | 48 |
| Staging models | 48 |
| Snapshots | 3 |
| Silver models | 19 |
| Gold dimensions | 11 |
| Gold facts | 17 |
| Mart models | 10 |

Snapshot là nhánh hỗ trợ SCD2 trong Layer 2, không phải một lớp phân tích độc lập.

## Validation results

| Gate | Expected | Result | Evidence |
|---|---|---|---|
| Static pipeline contract | Model/source counts và tài liệu khớp code | Verified | `python3 scripts/check_de_pipeline_contract.py` |
| Docker Compose | Config hợp lệ | Verified | `docker compose -f data_platform/docker-compose.yml config --quiet` |
| PostgreSQL CDC | `wal_level=logical` | Verified | `SHOW wal_level;` trả về `logical` trong lần chạy gần nhất |
| Debezium connector | Connector và tasks `RUNNING` | Verified | Connector status trả về `RUNNING` cho connector và tasks |
| Kafka topics | Topic của 44 bảng CDC tồn tại | Verified | Kafka topic listing của lần chạy thành công |
| MinIO | Có Parquet theo table/date partition | Verified | MinIO object listing và bước download thành công |
| Snowflake Bronze | 48 raw tables tồn tại và có dữ liệu | Verified | `INFORMATION_SCHEMA` và bước Bronze load thành công |
| dbt parse | Parse thành công | Verified | `dbt parse --profiles-dir .dbt` |
| dbt staging test | PASS | Verified | `dbt test --select staging --profiles-dir .dbt` |
| dbt snapshot test | PASS | Verified | `dbt test --select resource_type:snapshot --profiles-dir .dbt` |
| dbt silver test | PASS | Verified | `dbt test --select silver --profiles-dir .dbt` |
| dbt gold test | PASS | Verified | `dbt test --select gold --profiles-dir .dbt` |
| dbt mart test | PASS | Verified | `dbt test --select mart --profiles-dir .dbt` |
| Airflow DAG | DagRun `SUCCESS` | Verified | Airflow Grid và task logs của DagRun thành công gần nhất |

Khi bật lại stack, chỉ cần re-run các gate runtime nếu code, cấu hình hoặc môi trường đã thay đổi.

## Verified implementation decisions

- `hr_job` và `res_country` đã có dedicated staging model.
- Kafka consumer tắt auto-commit và chỉ commit offset sau khi upload MinIO thành công.
- CSV production chỉ gồm bốn nguồn; hai CSV legacy không được ingest.
- Static contract xác nhận đủ 44 CDC, 4 CSV, 48 Staging, 3 Snapshot, 19 Silver, 11 Dimension, 17 Fact và 10 Mart.

## Known limitation

- MinIO-to-Snowflake vẫn quét toàn bộ Parquet lịch sử; Snowflake chống nạp trùng bằng `record_hash` theo từng record.

## Completion criteria

STEP 4 đã hoàn tất:

- [x] Tất cả runtime gate đã được xác minh trong lần chạy thành công gần nhất.
- [x] dbt test của Staging, Snapshot, Silver, Gold và Mart đều PASS.
- [x] Airflow DagRun end-to-end có trạng thái `SUCCESS`.
- [x] Evidence đã được ghi trong bảng validation.
