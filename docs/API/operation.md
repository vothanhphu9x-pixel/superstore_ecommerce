# API Operations

## 1. Cài đặt và chạy local

Tạo môi trường Python và cài dependencies:

```bash
cd RAG_CHATBOT

python3 -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip
pip install -r requirements-dev.txt
```

Chạy tests:

```bash
pytest -q
```

Chạy Redis:

```bash
cd ../data_platform
docker compose up -d redis
```

Chạy API:

```bash
cd ../RAG_CHATBOT
source .venv/bin/activate

python -m uvicorn api.app:app \
  --host 0.0.0.0 \
  --port 8000 \
  --reload
```

Mở Swagger UI tại:

```text
http://localhost:8000/docs
```

## 2. Chuẩn bị Snowflake trước smoke test

API không sử dụng role nạp dữ liệu hoặc role dbt. API cần một user riêng với role chỉ đọc
`ANALYTICS_READONLY`. Điều kiện trước bước này là pipeline đã tạo xong database và các bảng
Gold/Mart.

```bash
cd /Users/macos/Desktop/Superstore_ecommerce

snowsql \
  -a <ACCOUNT_IDENTIFIER> \
  -u <ADMIN_USER> \
  -r ACCOUNTADMIN \
  -f data_platform/setup/02_snowflake_role.sql
```

Script tạo `SUPERSTORE_API_USER` và role `ANALYTICS_READONLY`, cấp quyền `USAGE` cho
warehouse/database/schema, cấp `SELECT` trên các bảng Gold/Mart hiện tại và tương lai,
rồi gán role cho user API.

Password không được hard-code trong Git. Sau khi chạy script, đặt password cho API user một
lần và xác nhận quyền:

```sql
USE ROLE ACCOUNTADMIN;
ALTER USER SUPERSTORE_API_USER
    SET PASSWORD = '<STRONG_PASSWORD>'
        DEFAULT_ROLE = ANALYTICS_READONLY
        MUST_CHANGE_PASSWORD = FALSE;
SHOW GRANTS TO USER SUPERSTORE_API_USER;
```

Cấu hình `RAG_CHATBOT/.env` tương ứng:

```dotenv
SNOWFLAKE_USER=SUPERSTORE_API_USER
SNOWFLAKE_PASSWORD=<STRONG_PASSWORD>
SNOWFLAKE_ROLE=ANALYTICS_READONLY
```

Nếu đổi tên user API, cập nhật biến `app_user` trong `02_snowflake_role.sql` và
`SNOWFLAKE_USER` trong `.env`. API hằng ngày không sử dụng `ACCOUNTADMIN`,
`SUPERSTORE_LOADER_ROLE` hoặc `SUPERSTORE_DBT_ROLE`.

## 3. Smoke test

Mở terminal mới, sau đó load `.env` mà không in secret:

```bash
cd RAG_CHATBOT
set -a
. ./.env
set +a
```

Liveness:

```bash
curl --fail -i http://localhost:8000/health/live
```

Readiness:

```bash
curl --fail -i http://localhost:8000/health/ready
```

check detail

```bash
curl -s http://localhost:8000/health/ready | python -m json.tool
```

Readiness chỉ trả `200` khi kết nối Snowflake thành công. Redis được báo riêng trong response.

Request không có API key phải bị từ chối:

```bash
curl -i http://localhost:8000/api/dashboard
```

Request có API key sai cũng phải bị từ chối:

```bash
curl -i \
  -H "X-API-Key: wrong-key" \
  http://localhost:8000/api/dashboard
```

Kết quả mong đợi:

```text
HTTP/1.1 403 Forbidden
```

Request có API key hợp lệ:

```bash
curl --fail \
  -H "X-API-Key: $API_KEY" \
  http://localhost:8000/api/dashboard
```

Kiểm tra đủ năm metric:

```bash
# KPI
curl --fail \
  -H "X-API-Key: $API_KEY" \
  "http://localhost:8000/api/dashboard/kpi?month_from=20230101&month_to=20231201"

# Revenue trend
curl --fail \
  -H "X-API-Key: $API_KEY" \
  "http://localhost:8000/api/dashboard/revenue-trend?month_from=20230101&month_to=20231201"

# Revenue by category
curl --fail \
  -H "X-API-Key: $API_KEY" \
  "http://localhost:8000/api/dashboard/by-category?month_from=20230101&month_to=20231201"

# Revenue by region
curl --fail \
  -H "X-API-Key: $API_KEY" \
  "http://localhost:8000/api/dashboard/by-region?month_from=20230101&month_to=20231201"

# Top products
curl --fail \
  -H "X-API-Key: $API_KEY" \
  "http://localhost:8000/api/dashboard/top-products?month_from=20230101&month_to=20231201&limit=10"
```

Khi Redis và cache được bật, gọi lại cùng một URL metric. Response đầu tiên chứa:

```json
"cached": false
```

Response tiếp theo phải chứa:

```json
"cached": true
```

## 4. Quality gate

```bash
cd RAG_CHATBOT

python -m compileall \
  analytics \
  api \
  core

pytest -q

docker build -t superstore-api:step5 .

git check-ignore .env
git check-ignore .venv
git check-ignore logs/application.log

cd ../data_platform
docker compose config --quiet
```

Điều kiện hoàn thành:

- Tests pass.
- Docker image build thành công.
- `/health/live` trả `200`.
- `/health/ready` trả `200`.
- Request thiếu hoặc sai API key trả `403`.
- Năm metric trả đúng contract.
- Lần gọi metric thứ hai có `cached=true` khi cache được bật.
- `.env`, `.venv` và logs bị Git ignore.
