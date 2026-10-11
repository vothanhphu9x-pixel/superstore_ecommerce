# API Operations

## 1. Cấu hình và chạy API

Trước khi sử dụng dashboard, cấu hình `API_KEY`, `STAFF_JWT_SECRET` (ít nhất 32 ký tự),
`INTERNAL_EMAIL_DOMAINS` và `STAFF_DB_PATH` trong `RAG_CHATBOT/.env`; tạo staff bằng CLI ở Mục 3.
Domain của email phải nằm trong `INTERNAL_EMAIL_DOMAINS` (ví dụ tài khoản Gmail cần
khai báo `gmail.com`). `API_KEY` dành cho client nội bộ, còn `STAFF_JWT_SECRET`
chỉ để backend ký session.

### 1.1. Chạy local

Tạo môi trường Python và cài dependencies:

```bash
cd /Users/macos/Desktop/Superstore_ecommerce/RAG_CHATBOT

python3 -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip
pip install -r requirements-dev.txt
```

Các lệnh kiểm tra API nằm trong [Test Operations](../tests/operation.md).

Chạy Redis:

```bash
cd /Users/macos/Desktop/Superstore_ecommerce/data_platform
docker compose up -d redis
```

Chạy API:

```bash
cd /Users/macos/Desktop/Superstore_ecommerce/RAG_CHATBOT
source .venv/bin/activate

python -m uvicorn api.app:app \
  --host 0.0.0.0 \
  --port 8000 \
  --reload
```

### 1.2. Chạy bằng Docker Compose

Compose nạp `RAG_CHATBOT/.env` qua `env_file`, không cần `set -a` trong terminal.
Đặt URL BFF cho Docker theo [Frontend Operations](../frontend/operation.md).

```bash
cd /Users/macos/Desktop/Superstore_ecommerce/data_platform
docker compose --profile app up -d --build api
docker compose ps api
```

Với cả hai cách chạy, mở Swagger UI tại:

```text
http://localhost:8000/docs
```

## 2. Cấu hình Snowflake cho API

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

Lệnh `-f` chạy xong sẽ quay về terminal macOS. Để đặt mật khẩu, **mở phiên SnowSQL
tương tác** (hoặc dùng Snowsight → Worksheets); không gõ `USE`/`ALTER`/`SHOW` tại dấu
nhắc `zsh`:

```bash
snowsql -a <ACCOUNT_IDENTIFIER> -u <ADMIN_USER> -r ACCOUNTADMIN
```

Trong dấu nhắc SnowSQL, kiểm tra role rồi đặt mật khẩu cho API user. Script ở trên
đã cấp `ANALYTICS_READONLY`; chỉ chạy `GRANT ROLE` nếu kết quả `SHOW GRANTS` cho
thấy role còn thiếu:

```sql
USE ROLE ACCOUNTADMIN;
SHOW GRANTS TO USER SUPERSTORE_API_USER;
-- Chỉ khi chưa có ANALYTICS_READONLY:
-- GRANT ROLE ANALYTICS_READONLY TO USER SUPERSTORE_API_USER;

ALTER USER SUPERSTORE_API_USER
    SET PASSWORD = '<STRONG_PASSWORD>'
        DEFAULT_ROLE = ANALYTICS_READONLY
        MUST_CHANGE_PASSWORD = FALSE;
SHOW GRANTS TO USER SUPERSTORE_API_USER;
```

`DEFAULT_ROLE` không tự cấp role cho user. Dùng mật khẩu mới, không ghi mật khẩu
thật trong Git hoặc dán vào lệnh shell/chat.

Cấu hình `RAG_CHATBOT/.env` tương ứng:

```dotenv
SNOWFLAKE_USER=SUPERSTORE_API_USER
SNOWFLAKE_PASSWORD=<STRONG_PASSWORD>
SNOWFLAKE_ROLE=ANALYTICS_READONLY
```

Nếu đổi tên user API, cập nhật biến `app_user` trong `02_snowflake_role.sql` và
`SNOWFLAKE_USER` trong `.env`. API hằng ngày không sử dụng `ACCOUNTADMIN`,
`SUPERSTORE_LOADER_ROLE` hoặc `SUPERSTORE_DBT_ROLE`.

## 3. Tạo staff user đầu tiên

Domain của email staff phải có trong biến `INTERNAL_EMAIL_DOMAINS` của
`RAG_CHATBOT/.env`. Chọn **một** trong hai cách dưới đây, tương ứng với nơi API
đang chạy.

### 3.1. CLI khi chạy local

CLI staff tự đọc `RAG_CHATBOT/.env` qua `core/config.py`, nên không cần
`set -a` cho các lệnh bên dưới. Chỉ export `.env` vào terminal nếu chạy công cụ
khác yêu cầu biến môi trường của shell.

Repository đã có `data/.gitkeep`; nếu checkout cũ chưa có thì tạo thư mục:

```bash
cd /Users/macos/Desktop/Superstore_ecommerce/RAG_CHATBOT
mkdir -p data
touch data/.gitkeep
```

Tạo tài khoản admin (CLI yêu cầu mật khẩu tối thiểu 12 ký tự):

```bash
python -m scripts.manage_staff add your-email@yourcompany.com \
  --name "Your Name" \
  --role admin
```

Liệt kê và quản trị tài khoản:

```bash
python -m scripts.manage_staff list
python -m scripts.manage_staff role user@company.com cfo
python -m scripts.manage_staff password user@company.com
python -m scripts.manage_staff disable user@company.com
python -m scripts.manage_staff enable user@company.com
```

### 3.2. CLI khi chạy bằng Docker Compose

Tạo admin trong container đang chạy (mật khẩu tối thiểu 12 ký tự):

```bash
docker exec -it superstore_api \
  python -m scripts.manage_staff add your-email@yourcompany.com \
  --name "Your Name" \
  --role admin
```

Liệt kê và quản trị tài khoản trong cùng container:

```bash
docker exec -it superstore_api python -m scripts.manage_staff list
docker exec -it superstore_api python -m scripts.manage_staff role user@company.com cfo
docker exec -it superstore_api python -m scripts.manage_staff password user@company.com
docker exec -it superstore_api python -m scripts.manage_staff disable user@company.com
docker exec -it superstore_api python -m scripts.manage_staff enable user@company.com
```

`-it` cho phép nhập mật khẩu tương tác. Compose lưu SQLite ở Docker volume
`staff_auth_data`, nên tạo lại container không làm mất tài khoản; CLI local dùng
`RAG_CHATBOT/data` và **không dùng chung** dữ liệu với container.

Các rule sau đã có trong `.gitignore` ở root repository:

```gitignore
RAG_CHATBOT/data/*.db
RAG_CHATBOT/data/*.db-shm
RAG_CHATBOT/data/*.db-wal
```

Không ignore `RAG_CHATBOT/data/.gitkeep`.

Đổi role, mật khẩu hoặc trạng thái active sẽ tăng `auth_version`, làm session cũ
hết hiệu lực. `STAFF_COOKIE_SECURE=false` chỉ phù hợp HTTP local; khi chạy HTTPS đặt
`true`. `STAFF_JWT_SECRET` và `API_KEY` phải là hai secret khác nhau.
