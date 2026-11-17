# Odoo — Discovery Result

## Trạng thái

- **Verified:** đã chạy và có bằng chứng.
- **Failed:** đã chạy nhưng không đạt.
- **Blocked:** chưa thể chạy do thiếu dịch vụ, quyền hoặc kết nối.
- **Not Run:** chưa có kết quả thực tế cho lần kiểm tra hiện tại.

## Thông tin lần kiểm tra

- Jira issue: SUP-62 Validate odoo configuration and establish source-of-truth map
- Ngày cập nhật tài liệu: **2026-11-14**. Ngày chạy khảo sát gốc chưa được ghi lại.
- Kết luận: các bảng số liệu và quan hệ bên dưới là **baseline lịch sử**; chưa chạy lại truy vấn PostgreSQL/Odoo trong lượt này.
- Odoo edition: Community
- Odoo series: 18.0
- Odoo source commit: `788c2f3f19a3a2c70e2efcc683e21965c634b6de`
- PostgreSQL database: `superstore_erp`
- PostgreSQL user used for discovery: `odoo`

## Thành phần cần kiểm soát

```text
Odoo module/model → PostgreSQL table + id → business key → FK/relationship → CDC source
```

Các kết quả sau ghi lại lần khảo sát gốc; `verified` ở bảng cũ **không** có nghĩa đã kiểm tra lại ngày 2026-11-14.

### Runtime baseline

| Check               | Result   | Evidence                   |
| ------------------- | -------- | -------------------------- |
| Odoo binary         | verified | `make -C odoo_dev version` |
| Odoo startup        | verified | Startup log                |
| HTTP login          | verified | `GET /web/login`           |
| Database connection | verified | `01_instance_check.sql`    |
| Core module         | verified | `ir_module_module`         |

### Installed modules

| Module          | State     | Version  | Required by scope |
| --------------- | --------- | -------- | ----------------- |
| base            | installed | 18.0.1.3 | Yes               |
| contacts        | installed | 18.0.1.0 | Yes               |
| product         | installed | 18       | Yes               |
| sale_management | installed | 18       | Yes               |
| sale_stock      | installed | 18       | Yes               |
| crm             | installed | 18       | Confirm           |
| purchase        | installed | 18       | Yes               |
| purchase_stock  | installed | 18       | Yes               |
| stock           | installed | 18       | Yes               |
| mrp             | installed | 18       | Yes               |
| account         | installed | 18       | Yes               |
| hr              | installed | 18       | Yes               |
| hr_contract     | installed | 19       | Yes               |
| utm             | installed | 18       | Yes               |

### Entity counts

- Total partners: 2026
- Customers: 2000
- Suppliers: 20
- Partners missing email: 4
- Product variants: 454
- Product variants missing SKU: 0
- Employees: 46
- Sales order states:
  - sale: 20.862
  - cancel: 294
- Purchase order states: 2218
- Stock location usages:
  - internal: 35
  - view: 8
  - inventory: 2
  - transit: 2
  - customer: 1
  - supplier: 1
  - production: 1
- Accounting document states:
  - entry / posted: 11,108
  - in_invoice / posted: 2,218
  - out_invoice / posted: 9,867

### Relationship quality

| Relationship                                            | Orphan rows | Status   |
| ------------------------------------------------------- | ----------: | -------- |
| `sale_order.partner_id → res_partner.id`                |           0 | verified |
| `sale_order_line.order_id → sale_order.id`              |           0 | verified |
| `sale_order_line.product_id → product_product.id`       |           0 | verified |
| `product_product.product_tmpl_id → product_template.id` |           0 | verified |
| `purchase_order_line.order_id → purchase_order.id`      |           0 | verified |
| `account_move_line.move_id → account_move.id`           |           0 | verified |

### Important observations

- Email technical-key suitability: verified
- SKU business-key suitability: verified - `454/454 product variants have SKU`
- Product cost physical table: verified - `product_product (standard_price)`
- Product description availability: missing
- Custom commission table: uninstalled
- Missing expected tables: verified
- Product image source: Verified — stored via `ir_attachment`.

### Decisions required

- Commission module scope: Decision Needed — commission is not currently an approved business capability.
- Missing module installation: Not Applicable — all required modules are installed.
- External marketing data ownership: Decision Needed — ownership and source-of-truth boundaries for external marketing data are not yet defined.

## Checklist kết quả

| Gate | Kỳ vọng | Kết quả | Bằng chứng / lần chạy |
|---|---|---|---|
| ODOO-01 — Runtime | Odoo khởi động, login và PostgreSQL kết nối được | Not Run | Bảng runtime baseline ghi kết quả cũ nhưng thiếu ngày/run mới |
| ODOO-02 — Module/table | Module trong scope đã cài; model có bảng và khóa `id` | Not Run | Cần chạy lại `01_instance_check.sql`, `02_installed_modules.sql`, `03_source_tables.sql` |
| ODOO-03 — Dữ liệu | Customer, product, order, stock, invoice counts còn đúng | Not Run | Cần chạy lại `05_data_profile.sql`; số ở trên là baseline lịch sử |
| ODOO-04 — Quan hệ | Sáu quan hệ trong bảng không có orphan | Not Run | Cần chạy lại `04_relationships.sql` |
| ODOO-05 — Key/source | Email, SKU, product cost và image source còn đúng | Not Run | Cần đối chiếu lại source/table và kết quả profile |
| ODOO-06 — Quyết định BA | Phạm vi commission và ownership marketing được chốt | Blocked | Hai quyết định còn mở trong bản khảo sát gốc |

Khi chạy lại, ghi ngày, database/source commit và bằng chứng của từng gate. Không sao chép `Verified` từ baseline cũ sang lần mới nếu chưa truy vấn lại.

## Tiêu chí hoàn tất

- [ ] Chạy lại kiểm tra runtime, module, dữ liệu và quan hệ trên Odoo/PostgreSQL hiện tại.
- [ ] Ghi ngày và kết quả truy vấn thực tế, cập nhật baseline nếu dữ liệu thay đổi.
- [ ] Chốt scope commission và ownership dữ liệu marketing ngoài Odoo.

## Tài liệu liên quan

- SQL khảo sát: `odoo_dev/discovery/01_instance_check.sql` đến `05_data_profile.sql`.
- Vận hành Odoo: [Odoo Operations](operation.md).
- Nguồn và business key: [Entity Map](entity_map.md).
