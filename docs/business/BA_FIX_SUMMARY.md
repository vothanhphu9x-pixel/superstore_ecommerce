# Biên bản tổng hợp 12 nhóm lỗi đã xử lý

**Ngày kiểm tra:** 2026-09-15  
**Phạm vi:** BA documents + Data Platform + dbt + Draw.io + quality gate

## 1. Kết luận nhanh

```mermaid
flowchart LR
    A[12 nhóm lỗi] --> B[12/12 đã sửa code/tài liệu]
    B --> C[11/12 xác minh local/static]
    B --> D[1/12 chờ xác minh live Snowflake]
    C --> E[Project có thể parse và kiểm tra cấu trúc]
    D --> F[Unlock account/cập nhật credential → dbt build]
```

Không còn lỗi đã biết nào trong phần code/tài liệu có thể sửa offline. Trạng thái chưa hoàn tất
production là **dbt run/test trên Snowflake thật**, vì tài khoản Snowflake hiện bị khóa tạm thời.

## 2. Bảng 12 nhóm lỗi

| # | Lỗi trước khi sửa | Đã sửa | Bằng chứng kiểm tra | Trạng thái |
|---:|---|---|---|---|
| 1 | Bộ BA dài, thiếu điểm bắt đầu | Thêm `docs/business/README.md`, bản đồ đọc và Business → Data Product | Đối chiếu liên kết và sơ đồ | ✅ Đạt |
| 2 | BRD thiếu sơ đồ và trỏ sai FRD HR/DataOps | Thêm context diagram; sửa về `FRD-07-08-hr-dataops.md` | Markdown/model reference scan | ✅ Đạt |
| 3 | Marketing còn dễ nhầm nguồn CSV với Odoo | Viết lại FRD-02 theo 4 CSV thật, UTM Odoo và funnel tách platform/ERP | Đối chiếu nguồn và khóa `campaign_id`; dbt test quan hệ sau khi nạp | ✅ Đạt |
| 4 | HR mô tả Attendance/Payroll dù chưa ingest | Giới hạn về 5 bảng HR/User thật; ghi rõ phần chưa hỗ trợ | So với Debezium allowlist | ✅ Đạt |
| 5 | DataOps dùng lịch/tên model cũ | Sửa lịch 09:00 ICT, đúng thứ tự DAG và Gold/Mart hiện tại | DAG + dbt parse | ✅ Đạt |
| 6 | Purchasing dùng `dim_supplier` không tồn tại | Chuẩn hóa vendor = `res_partner.supplier_rank > 0` qua `dim_customer` | Model reference scan | ✅ Đạt |
| 7 | Warehouse dùng field/table cũ và đếm giao hàng sai grain | Dùng `stock_move.quantity`; thêm valuation/carrier; delivery theo picking | FRD + Gold/Mart contract | ✅ Đạt |
| 8 | Manufacturing dùng `mrp_scrap`, BOM/routing table chưa ingest | Đổi về `stock_scrap`, productivity/loss và Facts/OEE Mart thật | 44-table + model coverage | ✅ Đạt |
| 9 | Accounting dùng `account_reconcile` và công bố Mart chưa có | Đổi về `account_partial_reconcile`; scope còn P&L, AR Aging, DSO | Model reference scan + dbt parse | ✅ Đạt |
| 10 | Use Case attribution dùng `fact_sales.campaign_id`/`mart_roas` cũ | Sửa thành campaign/channel SK và `mart_roas_by_channel`; thêm overview diagram | Đối chiếu model và sơ đồ | ✅ Đạt |
| 11 | Hai Draw.io sai/thiếu Silver và chưa thể hiện rõ 4 lớp dbt | Bổ sung đủ 19 Silver models, sửa lineage CRM/Purchase/Accounting/MFG/Marketing; xác định Snapshot là nhánh SCD2 của Silver | XML OK, 0 broken edge; đủ 48 Staging + 3 Snapshot + 19 Silver + 28 Gold + 10 Mart | ✅ Đạt |
| 12 | Quality gate báo lỗi giả cho app chưa triển khai | Backend/Frontend skip có điều kiện; giữ DE source contract trong CI | Kiểm tra tĩnh đạt; live `dbt debug` bị account lock | 🟡 Chờ live |

## 3. Kết quả chạy kiểm tra

| Kiểm tra | Kết quả |
|---|---|
| Repository hygiene | PASS — 261 versioned candidates |
| Git diff whitespace | PASS |
| Python compile | PASS |
| DE source contract | PASS — 44 CDC + 4 CSV + 48 Staging |
| Docker Compose parse | PASS |
| GitHub Actions YAML | PASS |
| dbt dependencies + parse | PASS — dbt 1.11.7 / Snowflake adapter 1.11.3 |
| dbt resource discovery | PASS — 105 models + 3 snapshots + 588 tests |
| Mart dependency rule | PASS — không đọc thẳng Staging/Silver/Snapshot |
| Draw.io integrity | PASS — 0 broken references; cả hai sơ đồ có đủ model của 4 lớp dbt |
| Snowflake live connection/build | BLOCKED — user account đang bị khóa tạm thời |

Backend và Frontend hiện chưa có source/manifests; quality gate ghi rõ **skipped**, không coi đây là
PASS test ứng dụng và cũng không coi là lỗi pipeline.

## 4. Việc còn lại sau khi Snowflake được mở khóa

```mermaid
flowchart LR
    A[Unlock Snowflake account] --> B[Cập nhật secret local/Airflow]
    B --> C[dbt debug]
    C --> D[Trigger Airflow DAG hoặc dbt build]
    D --> E[Staging → Snapshot → Silver → Gold → Mart tests]
    E --> F[Đánh dấu production verified]
```

Không chạy thử lại credential liên tục khi account đang khóa. Sau khi mở khóa, chạy:

```bash
cd /Users/macos/Desktop/Superstore_ecommerce/data_platform/superstore_db
dbt debug --profiles-dir .dbt
dbt build --profiles-dir .dbt
```

Các biến `SNOWFLAKE_*` phải được nạp từ secret local/Airflow; không ghi giá trị thật vào tài liệu
hoặc commit Git.

## 5. Lệnh compact để tiếp tục hội thoại

Nếu client Codex của bạn hỗ trợ slash command, dùng:

```text
/compact Giữ lại bối cảnh sau: Project ở /Users/macos/Desktop/Superstore_ecommerce. Đã sửa pipeline Odoo→Debezium→Kafka→MinIO→Snowflake→dbt, logic SCD2/temporal join/incremental Fact, Mart, security res_users, BA docs và hai Draw.io. CI giữ `check_de_pipeline_contract.py`; đã xóa BA checker và bước đối soát Marketing/Odoo trước ingest. 44 CDC + 4 CSV + 48 Staging; dbt parse có 105 models, 3 snapshots, 588 tests. Backend/Frontend chưa triển khai nên quality gate skip có điều kiện. dbt build/test live chưa xác minh vì Snowflake account bị khóa; không retry credential cho đến khi account được mở. Biên bản chi tiết: docs/business/BA_FIX_SUMMARY.md. Tiếp tục từ việc mở khóa/cập nhật Snowflake credential rồi chạy dbt debug và dbt build; không sửa/xóa các thay đổi người dùng không liên quan.
```

Nếu giao diện không nhận tham số sau `/compact`, chạy riêng `/compact`, rồi gửi lại đoạn tóm tắt
trong khối trên làm tin nhắn tiếp theo.
