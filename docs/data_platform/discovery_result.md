# Data Platform — Discovery Result

## Trạng thái

- **Verified:** đã chạy và có bằng chứng.
- **Failed:** đã chạy nhưng không đạt.
- **Blocked:** chưa thể chạy do bước trước, quyền, dịch vụ hoặc kết nối.
- **Not Run:** chưa có kết quả thực tế trong lượt kiểm tra ghi ở bảng.

## Thông tin lần kiểm tra

- Ngày cập nhật: **2026-11-14**; môi trường: Mac local/Docker Compose, Snowflake bên ngoài.
- Phạm vi: Odoo PostgreSQL → Debezium → Kafka → MinIO → Snowflake Bronze → dbt → Airflow.
- Kết luận: **kiểm tra tĩnh đạt**. Lần chạy Airflow gần nhất được cung cấp (**2026-11-13**) dừng ở `load_snowflake` do Snowflake báo sai username/password; chưa có bằng chứng một DagRun mới thành công.
- Lần validation **2026-09-21** từng đạt end-to-end; đây là bằng chứng lịch sử, không thay thế cho kiểm tra tài khoản Snowflake mới.

## Thành phần cần kiểm soát

```text
Odoo CDC + 4 CSV → MinIO → Bronze → Staging → Snapshot/Silver → Gold → Mart
                         Airflow điều phối và test sau từng lớp
```

Baseline ghi ở lần kiểm tra 2026-09-21: **44 CDC**, **4 CSV**, **48 Bronze source**, **48 Staging**, **3 Snapshot**, **19 Silver**, **11 Gold dimension**, **17 Gold fact**, **10 Mart**. Snapshot hỗ trợ SCD2, không phải một lớp phân tích riêng. Khi mô hình thay đổi, lấy lại số từ code thay vì xem baseline này là số liệu hiện hành.

Trong code hiện tại, `hr_job` và `res_country` có staging model; consumer commit Kafka offset sau khi upload MinIO thành công; bốn CSV production được đưa vào nguồn và hai CSV legacy không ingest.

## Checklist kết quả

| Gate | Kỳ vọng | Kết quả | Bằng chứng / lần chạy |
|---|---|---|---|
| DE-01 — Source contract | Debezium, consumer, loader, dbt source/staging và các ràng buộc tĩnh khớp | Verified | `python3 scripts/check_de_pipeline_contract.py`: OK, 2026-11-14 |
| DE-02 — Compose | Cấu hình Compose hợp lệ | Verified | `docker compose ... config --quiet` với `.env.example`, 2026-11-14; không khởi động container |
| DE-03 — PostgreSQL/CDC | `wal_level=logical`, connector và Kafka topics hoạt động | Not Run | Kết quả cũ đạt 2026-09-21; chưa kiểm tra runtime hiện tại |
| DE-04 — MinIO | Parquet từ CDC/CSV tồn tại và consumer hoàn tất upload | Not Run | Kết quả cũ đạt 2026-09-21; chưa kiểm tra runtime hiện tại |
| DE-05 — Snowflake Bronze | Loader kết nối đúng account/user và nạp được raw tables | Failed | Airflow `load_snowflake`, 2026-11-13: lỗi `250001 (08001) Incorrect username or password` |
| DE-06 — dbt parse | Project/profile/macros/YAML parse thành công | Not Run | Chưa chạy lại với cấu hình tài khoản mới |
| DE-07 — dbt data tests | Staging → Snapshot → Silver → Gold → Mart và singular tests đạt | Blocked | Loader chưa nạp Bronze trong DagRun mới; pass cũ thuộc 2026-09-21 |
| DE-08 — Airflow | DagRun end-to-end `SUCCESS` | Failed | DagRun 2026-11-13 dừng ở `load_snowflake`; các task sau không chạy |

Khi chạy lại, ghi **ngày, DagRun/commit và bằng chứng** vào từng gate. Chỉ đổi `Failed`/`Blocked` sang `Verified` sau khi có lần chạy mới đạt. `dbt parse` và Compose config không kiểm tra dữ liệu Snowflake.

## Tiêu chí hoàn tất

- [x] Source contract và cú pháp Compose đạt trên code hiện tại.
- [ ] Sửa thông tin đăng nhập Snowflake trong môi trường Airflow rồi chạy lại Bronze load.
- [ ] Chạy lại dbt parse, test của từng lớp và singular tests.
- [ ] Ghi DagRun mới có trạng thái `SUCCESS`.

Giới hạn đã biết: loader MinIO → Snowflake vẫn quét Parquet lịch sử; `record_hash` theo từng record dùng để tránh nạp trùng.

## Tài liệu liên quan

- Lệnh vận hành và recovery: [Data Platform Operations](operation.md).
- Luồng các lớp: [System Architecture Lineage](System_Architecture_Lineage.md).
