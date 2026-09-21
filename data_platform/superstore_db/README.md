# Superstore dbt Project

Project biến dữ liệu Bronze trong Snowflake thành bốn lớp phân tích:

```text
BRONZE_LAYER
  → ANALYTIC_LAYER_STAGING_LAYER
  → DBT_SNAPSHOTS + ANALYTIC_LAYER_SILVER_LAYER
  → ANALYTIC_LAYER_GOLD_LAYER
  → ANALYTIC_LAYER_MART_LAYER
```

## Nguồn dữ liệu

- 44 bảng Odoo được đồng bộ bằng Debezium CDC.
- 4 file marketing production được nạp batch: campaign master, Ads daily, email campaign và A/B test.
- Customer acquisition và marketing funnel được tính từ Gold facts; không ingest hai file synthetic legacy.

## Quy tắc chính

- Staging là append-only typed event log, lọc incremental bằng `ingested_at`.
- Snapshot SCD2 áp dụng cho partner, product template và employment contract.
- Silver SCD2 merge theo version key và cập nhật lại version cũ khi `dbt_valid_to` bị đóng.
- Fact resolve SCD2 key bằng `silver_updated_at` trong khoảng nửa mở `[dbt_valid_from, dbt_valid_to)`.
- Mart chỉ được tham chiếu Gold; aggregate lịch sử được rebuild để phản ánh correction/backfill.
- Không dùng `gold_refreshed_at` làm business/version timestamp.
- Mọi processing time do pipeline tạo dùng `pipeline_now()`; ngày chạy dùng
  `pipeline_today()`. Cả hai cố định theo `Asia/Ho_Chi_Minh`, không phụ thuộc timezone
  của account/session Snowflake.
- Snapshot override `snowflake__snapshot_get_time()` bằng cùng chuẩn trên, nên
  `dbt_valid_from/dbt_valid_to` và `silver_updated_at` có thể temporal join trực tiếp.

## Kiểm tra cấu hình không cần Snowflake

Chạy từ repository root:

```bash
make de-contract
make dbt-parse
```

## Chạy transformation thật

Điền đúng Snowflake credentials trong file môi trường local, sau đó chạy theo thứ tự:

```bash
dbt deps --profiles-dir .dbt
dbt run --select staging --profiles-dir .dbt
dbt test --select staging --indirect-selection cautious --profiles-dir .dbt
dbt snapshot --profiles-dir .dbt
dbt test --select resource_type:snapshot --indirect-selection cautious --profiles-dir .dbt
dbt run --select silver --profiles-dir .dbt
dbt test --select silver --indirect-selection cautious --profiles-dir .dbt
dbt run --select gold --profiles-dir .dbt
dbt test --select gold --indirect-selection cautious --profiles-dir .dbt
dbt run --select mart --profiles-dir .dbt
dbt test --select mart --indirect-selection cautious --profiles-dir .dbt
dbt test --select test_type:singular --profiles-dir .dbt
```

Airflow đã tự động hóa đúng chuỗi trên. Hướng dẫn vận hành đầy đủ nằm tại `docs/data_platform/operation.md`.
