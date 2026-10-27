# API Operations

## 1. Cấu hình và chạy

FastAPI đọc cấu hình từ `RAG_CHATBOT/.env` khi chạy local. Docker Compose nạp file đó
vào API container; các giá trị đặt trong Compose có thể ghi đè một số biến cho container.
Không đưa secret thật vào Git.

Các biến cốt lõi:

```dotenv
API_KEY=...
STAFF_JWT_SECRET=...
INTERNAL_EMAIL_DOMAINS=yourcompany.com
STAFF_DB_PATH=data/internal_users.db
REDIS_URL=redis://localhost:6379/0
```

`API_KEY` và `STAFF_JWT_SECRET` phải là hai secret khác nhau; JWT secret dài ít nhất
32 ký tự. Để chạy API local, cài `requirements-dev.txt` trong virtualenv của
`RAG_CHATBOT`, rồi:

```bash
cd RAG_CHATBOT
source .venv/bin/activate
python -m uvicorn api.app:app --host 0.0.0.0 --port 8000 --reload
```

Redis local được chạy bằng service `redis` trong `data_platform/docker-compose.yml`:

```bash
cd data_platform
docker compose up -d redis
```

Swagger local: <http://localhost:8000/docs>.

## 2. Chạy API bằng Docker Compose

Từ thư mục `data_platform`, profile `app` bật API và các dependency cần thiết:

```bash
docker compose --profile app up -d --build api
docker compose ps api redis
```

Compose đọc `RAG_CHATBOT/.env`; không cần export biến vào terminal. Container có tên
`superstore_api`. Staff DB nằm trong volume `staff_auth_data`, độc lập với SQLite local.
Các bước chạy test không đặt ở đây; xem [Test Operations](../tests/operation.md).

## 3. Kết nối Snowflake

API dùng user riêng `SUPERSTORE_API_USER` với role chỉ đọc `ANALYTICS_READONLY`.
Tạo/cấp role một lần bằng script `data_platform/setup/02_snowflake_role.sql` dưới
`ACCOUNTADMIN`; không dùng `ACCOUNTADMIN`, loader role hay dbt role để chạy API hằng ngày.
Sau đó cấu hình trong `RAG_CHATBOT/.env`:

```dotenv
SNOWFLAKE_ACCOUNT=...
SNOWFLAKE_USER=SUPERSTORE_API_USER
SNOWFLAKE_PASSWORD=...
SNOWFLAKE_ROLE=ANALYTICS_READONLY
SNOWFLAKE_WAREHOUSE=COMPUTE_WH
SNOWFLAKE_DATABASE=SUPERSTORE_DB
SNOWFLAKE_GOLD_SCHEMA=ANALYTIC_LAYER_GOLD_LAYER
SNOWFLAKE_MART_SCHEMA=ANALYTIC_LAYER_MART_LAYER
```

Kiểm tra quyền và đặt mật khẩu trong SnowSQL/Snowsight, không nhập câu SQL ở shell:

```sql
USE ROLE ACCOUNTADMIN;
SHOW GRANTS TO USER SUPERSTORE_API_USER;
ALTER USER SUPERSTORE_API_USER
    SET PASSWORD = '<STRONG_PASSWORD>'
        DEFAULT_ROLE = ANALYTICS_READONLY
        MUST_CHANGE_PASSWORD = FALSE;
```

Không ghi password vào command history, Git hoặc log. Nếu đổi tên user, cập nhật cả
script setup và `SNOWFLAKE_USER`.

## 4. Quản lý staff

Email phải thuộc domain trong `INTERNAL_EMAIL_DOMAINS`. CLI hỏi password tương tác
(tối thiểu 12 ký tự); không truyền password qua command line.

Local, từ `RAG_CHATBOT`:

```bash
python -m scripts.manage_staff add user@yourcompany.com --name "Staff Name" --role admin
python -m scripts.manage_staff list
python -m scripts.manage_staff role user@yourcompany.com cfo
python -m scripts.manage_staff password user@yourcompany.com
python -m scripts.manage_staff disable user@yourcompany.com
python -m scripts.manage_staff enable user@yourcompany.com
```

Docker Compose:

```bash
docker exec -it superstore_api \
  python -m scripts.manage_staff add user@yourcompany.com \
  --name "Staff Name" --role admin

docker exec -it superstore_api python -m scripts.manage_staff list
```

Đổi role/password hoặc khóa account làm session cũ mất hiệu lực. Production staff
được tạo trong API container trên VPS; xem [Deploy Operations](../deploy/operation.md).

## 5. Route phân biệt khi vận hành

| Route | Dùng cho |
|---|---|
| `/health/live` | Liveness FastAPI cơ bản |
| `/health/ready` | Readiness phụ thuộc Snowflake; có thể trả `503` nếu Snowflake lỗi |
| `/api/health/live` | Probe nhanh cho Docker, Nginx và CD; không query Snowflake |
| `/api/health/ready` | Probe nội bộ staff SQLite + Redis; không public qua Nginx production |
| `/docs` | Swagger cho phát triển; production public API không expose đường dẫn này |

Frontend nên gọi Next.js same-origin BFF `/api/internal/...`; không gửi API key từ browser.
Chi tiết luồng: [Frontend Architecture](../frontend/system_architecture_lineage.md).
