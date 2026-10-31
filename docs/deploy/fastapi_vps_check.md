# FastAPI VPS — vận hành và kiểm tra endpoint

Tài liệu thực hành cho FastAPI ở local và VPS. Không dán API key, JWT,
password Snowflake hoặc password staff vào Git, ticket hay terminal history.

```text
Browser → Next.js BFF → FastAPI → Redis / Snowflake
                          ↑
                    Nginx trên VPS
```

- Local có thể gọi FastAPI trực tiếp tại `http://localhost:8000`.
- Production chỉ mở FastAPI qua Nginx; cổng `8000` chỉ dùng nội bộ VPS.
- `API_KEY` xác thực BFF/FastAPI; cookie `superstore_staff` xác thực staff.

## Phần 1. Thao tác trên VPS

### 1.1. Vào VPS và xác định release hiện hành

```bash
ssh deploy@YOUR_VPS

pwd
ls -la
cd
less <> cat <> nano
find . -maxdepth 3 -type f

readlink -f /opt/superstore/current
readlink -f /opt/superstore/previous
```

Luôn dùng `compose.sh` trong `current`. Helper này tự nạp stack config, image
digest và release SHA; không chạy `docker compose` tùy ý ở thư mục home.

### 1.2. Kiểm tra container và log

```bash
# Trạng thái API và Redis
sudo docker ps
sudo bash /opt/superstore/current/deploy/production/bin/compose.sh ps

# Lệnh này cho biết image ID, thời điểm container được khởi động và trạng thái hiện tại.
sudo docker inspect superstore-api-1 \
  --format 'Image ID: {{.Image}}{{println}}Started: {{.State.StartedAt}}{{println}}Status: {{.State.Status}}'
sudo docker inspect superstore-api-1 \
  --format '{{.Config.Image}}'

# liệt kê tên các service
sudo bash /opt/superstore/current/deploy/production/bin/compose.sh \
  config --services

# thông tin cấu hình nhạy cảm
sudo bash /opt/superstore/current/deploy/production/bin/compose.sh \
  config

# Container stdout/stderr; dùng khi API báo 5xx hoặc không khởi động
sudo docker logs --tail=50 superstore-api-1
sudo bash /opt/superstore/current/deploy/production/bin/compose.sh \
  logs --tail=150 api redis

# File log bền vững trên VPS
sudo tail -n 100 /opt/superstore/logs/api/http.log
sudo tail -n 100 /opt/superstore/logs/api/application.log

# Nginx proxy và TLS
sudo tail -n 100 /var/log/nginx/superstore-access.log
sudo tail -n 100 /var/log/nginx/superstore-error.log
```

### 1.3. Thao tác an toàn

| Tình huống             | Lệnh                                 | Tác dụng                                                  |
| ---------------------- | ------------------------------------ | --------------------------------------------------------- |
| Kiểm tra service       | `docker compose ps`                  | Xem trạng thái các container trong project                |
| Xem log                | `docker compose logs --tail=100 api` | Đọc 100 dòng log gần nhất của service `api`               |
| Theo dõi log           | `docker compose logs -f api`         | Theo dõi log mới liên tục                                 |
| Khởi động lại service  | `docker compose restart api`         | Restart container hiện tại                                |
| Tải image mới          | `docker compose pull api`            | Pull image theo cấu hình và tag trong Compose             |
| Tạo/cập nhật container | `docker compose up -d api`           | Đồng bộ container với cấu hình và image hiện có           |
| Dừng service           | `docker compose stop api`            | Dừng service, không xóa container                         |
| Dừng cả project        | `docker compose down`                | Dừng và xóa container, network do Compose project quản lý |

Không dùng `docker compose down`, không xóa volume `staff` và không `pull` image
thủ công. Deploy phiên bản mới phải đi qua CD để giữ image digest và release
traceability.

### 1.4. Kiểm tra cấu hình và Snowflake trong đúng container

Các lệnh này không in secret, nhưng dùng đúng env, network và role của API
production:

```bash
# Xác nhận các giá trị không nhạy cảm
sudo bash /opt/superstore/current/deploy/production/bin/compose.sh \
  exec -T api \
  python -c "from core.config import get_settings; s=get_settings(); print({'env': s.app_env, 'role': s.snowflake_role, 'database': s.snowflake_database})"

# Kết nối Snowflake: SELECT 1
sudo bash /opt/superstore/current/deploy/production/bin/compose.sh \
  exec -T api \
  python -c "import asyncio; from analytics.connector import snowflake_health; print(asyncio.run(snowflake_health()))"

# Query KPI thật: kiểm tra thêm schema, table, column và quyền đọc Gold
sudo bash /opt/superstore/current/deploy/production/bin/compose.sh \
  exec -T api \
  python -c "import asyncio; from analytics.dashboard_queries import kpi_summary; print(asyncio.run(kpi_summary(20230101, 20271201)))"
```

Nếu `snowflake_health()` pass nhưng `kpi_summary()` fail, kết nối đúng nhưng SQL,
quyền Gold hoặc cấu trúc dữ liệu KPI có vấn đề.

## Phần 2. Gọi và kiểm tra endpoint

### bảng endpoint

| Nơi gọi                     | Đường dẫn                                                                                       | Ý nghĩa                                                  |
| --------------------------- | ----------------------------------------------------------------------------------------------- | -------------------------------------------------------- |
| Browser → Next.js           | `/login`, `/dashboard`                                                                          | Trang đăng nhập và dashboard                             |
| Browser → Next.js BFF       | `/api/internal/staff/login`, `/api/internal/staff/me`, `/api/internal/staff/logout`             | Proxy các API staff được allowlist                       |
| Browser → Next.js BFF       | `/api/internal/dashboard`, `/api/internal/dashboard/{metric}`                                   | Proxy dashboard API                                      |
| Browser → Next.js           | `/api/health`                                                                                   | Next.js probe FastAPI `/api/health/live` phía server     |
| Next.js → FastAPI           | `/api/staff/...`, `/api/dashboard/...`                                                          | API nội bộ; Next.js gắn API key và chuyển cookie khi cần |
| Trực tiếp FastAPI / Swagger | `/health/live`, `/health/ready`, `/health`; `/api/health/live`, `/api/health/ready`, `/metrics` | Hai nhóm readiness phục vụ mục đích khác nhau            |

### 2.1. Health local

Khởi động local stack:

```bash
cd /Users/macos/Desktop/Superstore_ecommerce/data_platform
docker compose --profile app up -d api redis frontend
```

Gọi FastAPI trực tiếp:

```bash
curl -i http://localhost:8000/api/health/live
curl -i http://localhost:8000/api/health/ready
```

- `live`: tiến trình FastAPI đang chạy.
- `ready`: SQLite staff và Redis đã sẵn sàng.

### 2.2. Login, cookie và dashboard local

Chỉ đặt secret trong terminal hiện tại:

```bash
export API_KEY='...'
export STAFF_EMAIL='...'
export STAFF_PASSWORD='...'
```

Khi dùng HTTP local, `RAG_CHATBOT/.env` phải có
`STAFF_COOKIE_SECURE=false`; recreate API nếu vừa thay đổi.

```bash
# Login và lưu cookie
curl -sS -i \
  -X POST http://localhost:8000/api/staff/login \
  -H 'Content-Type: application/json' \
  -H "X-API-Key: $API_KEY" \
  -d "{\"email\":\"$STAFF_EMAIL\",\"password\":\"$STAFF_PASSWORD\"}"

# Xác nhận session
curl -sS -i \
  -b /tmp/superstore-staff.cookies \
  -H "X-API-Key: $API_KEY" \
  http://localhost:8000/api/staff/me

# Query KPI thật qua endpoint
curl -sS \
  -b /tmp/superstore-staff.cookies \
  -H "X-API-Key: $API_KEY" \
  'http://localhost:8000/api/dashboard/kpi?month_from=20230101&month_to=20271201' \
  | python3 -m json.tool

# logout
curl -sS -i \
  -X POST http://localhost:8000/api/staff/logout \
  -H 'Content-Type: application/json' \
  -H "X-API-Key: $API_KEY" \
```

`-c` lưu cookie sau login; `-b` gửi lại cookie. Dọn session sau khi xong:

```bash
rm -f /tmp/superstore-staff.cookies
unset API_KEY STAFF_EMAIL STAFF_PASSWORD
```

### 2.3. Health production

Từ máy local, chỉ cần domain public; không gọi thẳng `VPS_IP:8000`:

```bash
curl -i https://api.YOUR_DOMAIN/api/health/live
curl -I http://api.YOUR_DOMAIN/api/health/live
```

Kỳ vọng HTTPS liveness trả `200`; HTTP trả `308` redirect sang HTTPS.

Gọi FastAPI trực tiếp trên VPS:

```bash
curl -sS http://127.0.0.1:8000/openapi.json |
jq -r '.paths | to_entries[] |
  .key as $path |
  .value | keys[] |
  "\(ascii_upcase) \($path)"'

curl -i http://127.0.0.1:8000/api/health/ready
curl -sS -i http://127.0.0.1:8000/api/dashboard/kpi
```

từ browser -> vps (test tương tự như mục 2.2)

```bash
curl -i https://superstore.gymtech.id.vn/api/health
```

### 2.4. Đọc kết quả endpoint

| Kết quả                                | Ý nghĩa                                                 | Bước tiếp theo                                   |
| -------------------------------------- | ------------------------------------------------------- | ------------------------------------------------ |
| `401 Staff authentication is required` | Thiếu/hết hạn cookie staff                              | Login lại, dùng cookie jar với `-b`.             |
| `403` metric                           | Staff có session nhưng role không được xem metric       | Kiểm tra role và `ROLE_DASHBOARD_GROUPS`.        |
| `502 Unable to load metric ...`        | FastAPI nhận request nhưng query Snowflake/SQL thất bại | Xem log API, rồi chạy `kpi_summary()` ở Mục 1.4. |
| `/api/health/ready` trả `503`          | SQLite staff hoặc Redis chưa sẵn sàng                   | Kiểm tra `compose.sh ps` và API/Redis logs.      |
| Public endpoint không vào được         | DNS, TLS, Nginx hoặc release có vấn đề                  | Kiểm tra liveness, Nginx log và `current`.       |
