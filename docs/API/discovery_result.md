# API — Discovery Result

## 1. Phạm vi

- FastAPI cung cấp dashboard analytics nội bộ; dữ liệu chỉ đọc từ Snowflake.
- Staff đăng nhập bằng SQLite-backed account; session là cookie `HttpOnly`.
- Redis dùng cho login rate limit và metric cache.
- Tài liệu này ghi nhận code được đọc ngày 2026-10-27; các lệnh kiểm tra chưa được chạy lại trong lượt rà soát này.

## 2. API hiện có

| Route | Mục đích | Bảo vệ |
|---|---|---|
| `GET /health/live` | Liveness cơ bản của FastAPI | Không yêu cầu key |
| `GET /health/ready`, `GET /health` | Kiểm tra Snowflake và Redis | Không yêu cầu key |
| `GET /api/health/live` | Probe nhẹ, trả `status` và `release` | Không yêu cầu key |
| `GET /api/health/ready` | Kiểm tra staff SQLite và Redis | Không yêu cầu key; nội bộ trên production |
| `GET /api/dashboard` | Metric được staff hiện tại xem được + contract | API key + staff cookie |
| `GET /api/dashboard/{metric}` | Đọc một metric theo tháng | API key + staff cookie + RBAC |
| `POST /api/staff/login` | Xác thực staff, đặt cookie session | API key |
| `GET /api/staff/me` | Đọc profile/session hiện tại | API key + staff cookie |
| `POST /api/staff/logout` | Xóa cookie session | API key |
| `GET /metrics` | Prometheus counters/histogram | Không nằm trong OpenAPI; production không public |

Metric hiện được khai báo: `kpi`, `revenue-trend`, `by-category`, `by-region`, `top-products`.
Nguồn chính là Gold `fact_sales`, `dim_product` và Mart `mart_revenue_monthly`.

## 3. Trách nhiệm và giới hạn

- `api/routers/`: endpoint, xác thực route và response.
- `api/services/`: kiểm tra month key.
- `api/schemas/`: request/response Pydantic.
- `analytics/`: kết nối Snowflake, SQL, relation allowlist và metric contract.
- `core/`: config, API key, staff session/RBAC, Redis cache/rate limit, client IP và logging.
- `scripts/manage_staff.py`: CLI quản lý account; SQLite nằm trong `data/` local hoặc mount `/app/data` trong container.

`API_KEY` xác thực client nội bộ/BFF; `STAFF_JWT_SECRET` ký session staff. Hai secret này
không thay thế nhau. API key thiếu hoặc placeholder khiến protected route trả `503`;
key gửi sai trả `403`. Cookie thiếu/sai trả `401`; role không được phép trả `403`.

## 4. Tình trạng xác minh

| Hạng mục | Trạng thái trong lượt rà soát |
|---|---|
| Route, config, query và contract | Đã đối chiếu code |
| Unit/API tests | Chưa chạy lại |
| Docker/Compose runtime | Chưa kiểm tra |
| Kết nối Snowflake thật | Chưa kiểm tra |

Không xem kết quả cũ trong tài liệu là bằng chứng cho code hiện tại. Hướng dẫn chạy:
[operation.md](operation.md). Kiến trúc: [system_architecture_lineage.md](system_architecture_lineage.md).
