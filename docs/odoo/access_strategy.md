# Odoo Access Strategy

Tài liệu này quy định các kênh được phép truy cập Odoo, nguyên tắc bảo mật và ranh giới giữa chính sách hiện tại với kiến trúc tích hợp dự kiến trong tương lai.

## 1. Approved access channels

| Action                           | Approved channel                                  |
| -------------------------------- | ------------------------------------------------- |
| Business create/update/delete    | Odoo UI or Odoo ORM                               |
| FastAPI live operational read    | Dedicated PostgreSQL read-only account            |
| Customer order/invoice read      | Read-only query filtered by JWT `partner_id`      |
| CDC ingestion                    | Dedicated replication account and table allowlist |
| Dashboard/analytics              | Snowflake read-only role                          |
| Future external write            | Odoo API after separate approval                  |
| Direct FastAPI SQL write to Odoo | **Prohibited**                                    |

Odoo API writes must execute through the Odoo ORM. An approved API integration does not authorize direct `INSERT`, `UPDATE` or `DELETE` statements against PostgreSQL.

## 2. Security rules

1. FastAPI must not accept a customer-provided `partner_id` as proof of ownership.
2. Customer `partner_id` comes from the verified server-side JWT/session.
3. SQL must be parameterized.
4. Odoo, FastAPI and CDC must use separate database credentials.
5. Odoo configuration and PostgreSQL passwords remain local secrets.
6. Direct SQL writes are prohibited because they bypass Odoo ORM rules and workflows.
7. Analytical data does not represent guaranteed live operational state.

## 3. Current application policy — STEP 3

No FastAPI-to-Odoo write path is approved in STEP 3.

A future write integration requires a separate Jira Story covering:

- Odoo model and method
- authentication
- authorization
- validation
- idempotency
- audit trail
- error mapping
- rollback behavior

## 4. Web customer identity integration — Target architecture

> **Status:** This section describes a future target architecture. The Odoo API write path shown below is not active or approved in STEP 3. When approved, it must call the Odoo API/ORM and must never write directly to PostgreSQL.

### 4.1. Mô hình xử lý khách hàng đăng ký trên website

```text
Khách đăng ký trên Website / App
              │
              ▼
Application Identity Store
(Web Database / Firebase / Supabase)
              │
              │ Lưu tài khoản, mật khẩu mã hóa và session
              ▼
Sàng lọc và xác thực hành động kinh doanh
(mua hàng / đặt cọc / tư vấn / yêu cầu báo giá)
              │
       ┌──────┴─────────────────────────────┐
       │                                    │
       ▼                                    ▼
STEP 3 hiện tại                    Tương lai sau phê duyệt
Không ghi vào Odoo                 Gọi Odoo API qua ORM
                                            │
                                            ▼
                              Kiểm tra khách hàng res.partner
                                            │
                                    ┌───────┴───────┐
                                    │               │
                                    ▼               ▼
                               Chưa tồn tại      Đã tồn tại
                                    │               │
                                    ▼               ▼
                            Tạo res.partner     Dùng partner_id cũ
                                    │               │
                                    └───────┬───────┘
                                            ▼
                              Tạo/liên kết crm.lead hoặc sale.order
                                            │
                                            ▼
                              Lưu website_user_id để liên kết ngược
```

Quy trình mục tiêu từ lúc khách đăng ký web đến khi vào Odoo được chia thành ba bước.

### 4.2. Bước 1 — Lưu tại Application Identity Store

Khi khách hàng đăng ký tài khoản trên web/app, App Database hoặc Auth Service như Firebase/Supabase chịu trách nhiệm lưu:

- thông tin đăng nhập;
- mật khẩu đã được băm/mã hóa phù hợp;
- session và trạng thái xác thực.

Ở thời điểm này, Web User là **thực thể độc lập**, chưa phải đối tác kinh doanh trong Odoo.

### 4.3. Bước 2 — Sàng lọc và xác thực

Khách hàng phải thực hiện một hành động có giá trị kinh doanh, ví dụ:

- mua hàng hoặc đặt cọc;
- điền form tư vấn;
- yêu cầu báo giá.

Hành động này chỉ tạo điều kiện kích hoạt luồng đồng bộ. Trong STEP 3 hiện tại, nó chưa được phép tự động ghi vào Odoo.

### 4.4. Bước 3 — Đồng bộ và liên kết sang Odoo

Sau khi write integration được phê duyệt, hệ thống web gọi Odoo API để tìm hoặc tạo đối tượng nghiệp vụ:

- Ưu tiên định danh bằng `website_user_id` hoặc cặp `(identity_provider, external_user_id)`.
- `email` và `phone` chỉ là tín hiệu đối chiếu sau khi xác thực; chúng có thể thay đổi hoặc trùng nên không phải candidate key tuyệt đối.
- **Nếu khách hàng đã tồn tại:** tái sử dụng `partner_id` hiện có.
- **Nếu chưa tồn tại và phát sinh đơn hàng:** tạo `res.partner`, sau đó tạo/liên kết `sale.order`.
- **Nếu chỉ gửi yêu cầu tư vấn:** có thể tạo `crm.lead` trước mà chưa bắt buộc tạo `res.partner`.

`website_user_id` là trường custom dự kiến trên `res.partner`, không phải trường chuẩn có sẵn của Odoo. Việc bổ sung trường này cần được thực hiện bằng module/migration Odoo riêng, kèm ràng buộc unique và quy trình xử lý xung đột định danh.
