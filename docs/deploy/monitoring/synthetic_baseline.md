# Monitoring — Synthetic baseline bằng Newman/Postman và Uptime Kuma

## 1. Mục tiêu

```text
Uptime Kuma (VPS) ── 60 giây ──► public API, website, login, cổng HTTPS
Newman (VPS)       ── systemd timer ─► login → Next.js BFF → FastAPI
                                          ├─ Redis: rate limit, cache
                                          └─ Snowflake: 5 metric dashboard
Newman ── file .prom ─► Node Exporter ─► Prometheus ─► Grafana dashboard
Postman Cloud      ── tùy chọn thay Newman; kiểm tra từ bên ngoài VPS
FastAPI /metrics + Node/Redis Exporter ──► Prometheus ──► PromQL/Grafana
```

Kuma và một runner collection tạo **traffic tổng hợp có kiểm soát** khi chưa có
người dùng thật. Mặc định dùng Newman tự chạy trên VPS; Postman Cloud là lựa
chọn bên ngoài nếu cần. Prometheus tự scrape bốn job: fastapi, redis, node,
prometheus.
Đây là baseline **idle + synthetic**, chưa phản ánh giờ cao điểm hoặc sức
chịu tải của ứng dụng.

FastAPI loại /api/health/live, /api/health/ready và /metrics khỏi HTTP
Counter/Histogram. Health probe thành công **không** làm API-01–07 tăng; các
request dashboard của Newman/Postman mới tạo mẫu HTTP để đo bằng PromQL.

## 2. Danh sách URL cần kiểm tra

Trong bảng: API = https://api.gymtech.id.vn; WEB =
https://superstore.gymtech.id.vn. Xác nhận domain production trước khi tạo
monitor.

| Nhóm             | Method và URL                                | Mong đợi                                | Đường được kiểm tra                   |
| ---------------- | -------------------------------------------- | --------------------------------------- | ------------------------------------- |
| Public           | GET API/api/health/live                      | 200; status=ok, release=commit SHA      | DNS/TLS → Nginx → FastAPI             |
| Public           | GET WEB/api/health                           | 200; status=ok, api=up                  | Vercel → Next.js → FastAPI            |
| Public           | GET WEB/login                                | 200; HTML có “Staff sign in”            | Trang đăng nhập Next.js               |
| Boundary         | GET API/api/health/ready                     | 404                                     | Nginx không công khai readiness       |
| Boundary         | GET API/metrics                              | 404                                     | Nginx không công khai metrics         |
| Staff chưa login | GET WEB/api/internal/staff/me                | 401                                     | BFF → FastAPI từ chối thiếu session   |
| Staff            | POST WEB/api/internal/staff/login            | 200; role=sales, Secure HttpOnly cookie | BFF → Redis rate limit → SQLite staff |
| Staff            | GET WEB/api/internal/staff/me                | 200; role=sales                         | Session qua BFF/FastAPI               |
| Dashboard        | GET WEB/api/internal/dashboard               | 200; liệt kê đủ 5 metric                | Quyền và contract                     |
| Dashboard        | GET WEB/api/internal/dashboard/kpi           | 200; object có số liệu                  | Redis/Snowflake Gold                  |
| Dashboard        | GET WEB/api/internal/dashboard/revenue-trend | 200; list có dữ liệu                    | Redis/Snowflake Mart                  |
| Dashboard        | GET WEB/api/internal/dashboard/by-category   | 200; list có dữ liệu                    | Redis/Snowflake Mart                  |
| Dashboard        | GET WEB/api/internal/dashboard/by-region     | 200; list có dữ liệu                    | Redis/Snowflake Mart                  |
| Dashboard        | GET WEB/api/internal/dashboard/top-products  | 200; list có dữ liệu                    | Redis/Snowflake Gold                  |
| Cache            | Gọi lại GET WEB/api/internal/dashboard/kpi   | 200; cached=true                        | Redis cache                           |
| UI               | GET WEB/dashboard với session                | 200; HTML có “Dashboard kinh doanh”     | Next.js render và kiểm tra session    |
| Staff            | POST WEB/api/internal/staff/logout           | 200; xóa cookie                         | Kết thúc phiên                        |
| Staff sau logout | GET WEB/api/internal/staff/me                | 401                                     | Không còn gửi cookie                  |

Năm metric dùng cùng query
?month_from=20230101&month_to=20271201; top-products thêm &limit=10. Đây là
khoảng mặc định trong analytics/dashboard_queries.py. Chạy thủ công và xác
nhận có dữ liệu trước khi bật lịch. Tài khoản synthetic role **sales** được
xem cả năm metric; tài khoản CFO của deploy smoke là luồng khác.

Các URL nội bộ /api/health/ready, /metrics, Redis, Prometheus, Loki, MinIO và
Grafana không mở ra Internet. Runner bên ngoài VPS không gọi được chúng. Kuma chạy
trong **Compose stack riêng**, chưa nối mạng nội bộ production; localhost trong
Kuma là container Kuma, không phải VPS. Để theo dõi nội bộ, dùng Prometheus
up/redis_up/Node Exporter và [Monitoring Operation](operation.md). Loki,
MinIO và Grafana hiện chưa có probe tự động độc lập; không đánh dấu chúng đã
được Kuma kiểm tra.

| Thành phần nội bộ    | Phép đo tự động hiện có                             |
| -------------------- | --------------------------------------------------- |
| FastAPI              | Prometheus up{job="fastapi"}; Postman Staff Journey |
| Redis                | Prometheus redis_up{job="redis"} và Redis memory    |
| VPS                  | Node Exporter: CPU, RAM, disk, network              |
| Prometheus           | Self-scrape up{job="prometheus"}                    |
| SQLite staff         | Postman login và GET /staff/me                      |
| Snowflake            | Năm query dashboard trong Postman Staff Journey     |
| Loki, MinIO, Grafana | Chưa có probe tự động trong cấu hình hiện tại       |

## 3. Uptime Kuma — kiểm tra liên tục

Trên Mac, mở tunnel và truy cập http://localhost:3002:

```bash
ssh -N -L 3002:127.0.0.1:3002 deploy@YOUR_VPS_IP
```

Vào **Add New Monitor**, tạo từng monitor:

| Tên             | Loại              | Đích                                        | Điều kiện Up            |
| --------------- | ----------------- | ------------------------------------------- | ----------------------- |
| api-live        | HTTP(s) - Keyword | https://api.gymtech.id.vn/api/health/live   | 200; chứa "status":"ok" |
| website-api     | HTTP(s) - Keyword | https://superstore.gymtech.id.vn/api/health | 200; chứa "api":"up"    |
| website-login   | HTTP(s) - Keyword | https://superstore.gymtech.id.vn/login      | 200; chứa Staff sign in |
| api-tcp-443     | TCP Port          | api.gymtech.id.vn:443                       | Kết nối được            |
| website-tcp-443 | TCP Port          | superstore.gymtech.id.vn:443                | Kết nối được            |

Cho HTTP monitor: GET, interval 60s, timeout 10s, retries 2, bật xác minh
TLS. TCP Port chỉ xác nhận kết nối TCP; HTTP monitor mới xác nhận TLS, status
và nội dung. Kiểm tra heartbeat đầu tiên ở trạng thái **Up**. Kuma cùng VPS
nên không phát hiện được lúc **cả VPS và Kuma** đều ngừng; Postman Cloud là
điểm đo bên ngoài. Chỉ ghi notification là hoạt động sau khi gửi thử thành công.

## 4. Postman Cloud — tùy chọn thay Newman

Giữ phần này khi cần điểm đo ngoài VPS. Nếu dùng Newman để tránh lịch chạy
Postman Cloud, chuyển thẳng đến §6 và chỉ bật lịch Newman.

### 4.1. Biến và tài khoản

Tạo workspace private và environment “Superstore production synthetic”:

| Biến                   | Giá trị                                        |
| ---------------------- | ---------------------------------------------- |
| api_origin             | https://api.gymtech.id.vn                      |
| frontend_origin        | https://superstore.gymtech.id.vn               |
| month_from / month_to  | 20230101 / 20271201                            |
| monitor_email_sales    | Email staff riêng có role sales; share value   |
| monitor_password_sales | Secure variable dùng Shared Vault; share value |

Trên VPS, kiểm tra danh sách staff; chỉ tạo **tài khoản riêng** nếu chưa có.
Thay YOUR_ALLOWED_DOMAIN bằng domain thuộc INTERNAL_EMAIL_DOMAINS:

```bash
COMPOSE=/opt/superstore/current/deploy/production/bin/compose.sh
sudo bash "$COMPOSE" exec api python -m scripts.manage_staff list
sudo bash "$COMPOSE" exec api python -m scripts.manage_staff add \
  monitor-sales@YOUR_ALLOWED_DOMAIN --name "Synthetic Monitor" --role sales
```

Ở request login dùng body
`{"email":"{{monitor_email_sales}}","password":"{{monitor_password_sales}}"}`.
**Save** request và environment trước khi chạy Monitor. `Send` thủ công có
thể dùng thay đổi chưa lưu hoặc giá trị local; Monitor đọc bản đã lưu và
**shared value**. Secret trong Shared Vault cũng cần được gắn vào secure
variable rồi share variable. Nếu login trong Monitor trả `422`, kiểm tra biến
email/password và response login trước khi điều tra các dashboard `401`.

Ở từng request: vào **Settings → Disable cookie jar**. Với request có session,
thêm header Cookie: superstore_staff={{staff_session}}. Biến staff_session
chỉ tồn tại trong **một collection run**; không lưu JWT vào environment,
collection hoặc Git. Request ẩn danh, login và sau logout **không** thêm Cookie.

Đặt tên **mọi request** bắt đầu bằng HTTP status mong đợi, ví dụ
“200 API live”, “401 Staff anonymous”, “404 Public metrics”. Ở
**Scripts → Post-response của mỗi collection**, đặt test chung:

```javascript
const expected = Number(pm.info.requestName.slice(0, 3));
pm.test("HTTP " + expected, () => pm.response.to.have.status(expected));
```

Các test nội dung ở dưới chạy thêm sau test chung. Nhờ vậy 18 URL đều được
kiểm tra status trong mỗi lần monitor tự chạy.

### 4.2. Collection “Superstore Public” — 5 request

Tạo đúng năm request theo thứ tự dưới đây. Mỗi request có
Scripts → Post-response kiểm tra nội dung tương ứng; status đã có test chung:

```text
200 GET {{api_origin}}/api/health/live
200 GET {{frontend_origin}}/api/health
200 GET {{frontend_origin}}/login
404 GET {{api_origin}}/api/health/ready
404 GET {{api_origin}}/metrics
```

Ví dụ post-response riêng cho API live:

```javascript
pm.test("API live", () => {
  pm.response.to.have.status(200);
  const body = pm.response.json();
  pm.expect(body.status).to.eql("ok");
  pm.expect(body.release).to.match(/^[0-9a-f]{40}$/);
});
```

Website health kiểm tra status=ok và api=up; login page chứa “Staff sign in”;
hai URL Boundary phải trả 404. Public collection không tạo traffic dashboard
cho FastAPI P95.

Post-response riêng cho website health và login page:

```javascript
// Website health
pm.test("Next.js reaches FastAPI", () => {
  const body = pm.response.json();
  pm.expect(body.status).to.eql("ok");
  pm.expect(body.api).to.eql("up");
});

// Login page: đặt riêng trong request /login
pm.test("Login HTML", () => {
  pm.expect(pm.response.text()).to.include("Staff sign in");
});
```

Hai test trên đặt ở **hai request tương ứng**, không dán cả hai vào cùng một
request.

### 4.3. Collection “Superstore Staff Journey” — 13 request

Tạo đúng 13 request theo thứ tự. Chỉ các request từ dòng 3 đến dòng 12
cần Cookie; riêng dòng 2 và 12 là POST cần Origin:

```text
401 GET  {{frontend_origin}}/api/internal/staff/me
200 POST {{frontend_origin}}/api/internal/staff/login
200 GET  {{frontend_origin}}/api/internal/staff/me
200 GET  {{frontend_origin}}/api/internal/dashboard
200 GET  {{frontend_origin}}/api/internal/dashboard/kpi?month_from={{month_from}}&month_to={{month_to}}
200 GET  {{frontend_origin}}/api/internal/dashboard/revenue-trend?month_from={{month_from}}&month_to={{month_to}}
200 GET  {{frontend_origin}}/api/internal/dashboard/by-category?month_from={{month_from}}&month_to={{month_to}}
200 GET  {{frontend_origin}}/api/internal/dashboard/by-region?month_from={{month_from}}&month_to={{month_to}}
200 GET  {{frontend_origin}}/api/internal/dashboard/top-products?month_from={{month_from}}&month_to={{month_to}}&limit=10
200 GET  {{frontend_origin}}/api/internal/dashboard/kpi?month_from={{month_from}}&month_to={{month_to}}
200 GET  {{frontend_origin}}/dashboard
200 POST {{frontend_origin}}/api/internal/staff/logout
401 GET  {{frontend_origin}}/api/internal/staff/me
```

Tên request trong Postman bắt đầu bằng status, tiếp theo là tên gợi nhớ;
**không** nhập số status vào URL. Login:

```text
POST {{frontend_origin}}/api/internal/staff/login
Origin: {{frontend_origin}}
Content-Type: application/json
```

Body JSON:

```json
{ "email": "{{monitor_email_sales}}", "password": "{{monitor_password_sales}}" }
```

Post-response của login kiểm tra cookie và giữ token **chỉ trong run**:

```javascript
pm.test("Sales login and secure cookie", () => {
  pm.response.to.have.status(200);
  const profile = pm.response.json();
  pm.expect(profile.role).to.eql("sales");
  pm.expect(profile.metrics).to.include.members([
    "kpi",
    "revenue-trend",
    "by-category",
    "by-region",
    "top-products",
  ]);
  const cookie = pm.response.headers.get("set-cookie") || "";
  pm.expect(cookie).to.match(/httponly/i);
  pm.expect(cookie).to.match(/secure/i);
  pm.expect(cookie).to.match(/samesite=lax/i);
  const token = cookie.match(/^superstore_staff=([^;]+)/i)?.[1];
  pm.expect(token).to.be.a("string").and.not.empty;
  pm.variables.set("staff_session", token);
});
```

Post-response riêng của GET /staff/me sau login và GET /dashboard index:

```javascript
// GET /api/internal/staff/me sau login
pm.test("Sales session", () => {
  pm.expect(pm.response.json().role).to.eql("sales");
});

// GET /api/internal/dashboard: đặt riêng trong request index
pm.test("Five visible metrics", () => {
  pm.expect(pm.response.json().metrics).to.include.members([
    "kpi",
    "revenue-trend",
    "by-category",
    "by-region",
    "top-products",
  ]);
});
```

Hai test trên đặt ở **hai request tương ứng**.
Với mỗi request metric, dùng cùng post-response script sau để kiểm tra
contract và dữ liệu không rỗng:

```javascript
const fields = {
  kpi: ["REVENUE", "GROSS_PROFIT", "ORDERS", "AVG_ORDER_VALUE", "MARGIN_PCT"],
  "revenue-trend": ["MONTH_DATE_KEY", "REVENUE", "COGS", "GROSS_PROFIT"],
  "by-category": ["CATEGORY", "REVENUE", "GROSS_PROFIT"],
  "by-region": ["REGION", "REVENUE", "GROSS_PROFIT"],
  "top-products": [
    "PRODUCT_ID",
    "PRODUCT_NAME",
    "CATEGORY",
    "REVENUE",
    "GROSS_PROFIT",
    "QUANTITY",
  ],
};
pm.test("Metric contract and populated data", () => {
  pm.response.to.have.status(200);
  const body = pm.response.json();
  const required = fields[body.metric];
  pm.expect(required).to.be.an("array");
  const rows = Array.isArray(body.data) ? body.data : [body.data];
  pm.expect(body.row_count).to.eql(rows.length);
  pm.expect(rows.length).to.be.greaterThan(0);
  rows.forEach((row) =>
    required.forEach((key) => pm.expect(row).to.have.property(key)),
  );
});
```

Ở lần gọi KPI thứ hai, thêm test cached=true; production cần bật
CACHE_ENABLED=true. Với GET /dashboard, kiểm tra HTML có “Dashboard kinh
doanh”. Postman không chạy JavaScript của browser; E2E Playwright kiểm tra UI
thật.

```javascript
// Chỉ ở request KPI thứ hai
pm.test("KPI cached in Redis", () => {
  pm.expect(pm.response.json().cached).to.eql(true);
});
```

Logout là POST với header Origin: {{frontend_origin}} và Cookie như các
request có session. Kiểm tra status 200 và Set-Cookie xóa superstore_staff,
sau đó chạy pm.variables.unset("staff_session"). GET /staff/me cuối cùng
không gửi Cookie và phải trả 401. Không in password/JWT/Set-Cookie ra Console
hoặc screenshot.

```javascript
// Chỉ ở request logout
pm.test("Staff cookie cleared", () => {
  const cookie = pm.response.headers.get("set-cookie") || "";
  pm.expect(cookie).to.match(/^superstore_staff=/i);
  pm.expect(cookie).to.match(/max-age=0|expires=/i);
});
pm.variables.unset("staff_session");
```

### 4.4. Lịch chạy và chi phí

Chạy **Collection Runner trên Mac** trước; xác nhận cả 18 request pass và
Staff Journey thật sự trả dữ liệu từ Snowflake. Tạo hai Cloud Monitors, chọn
**một region**, bật SSL validation, giữ đúng **Run order**, đặt timeout đủ
cho query Snowflake. Bắt đầu: Public mỗi **1 minute**; Staff Journey mỗi **1 giờ**.
Chạy **Run now** và kiểm tra kết quả từng request.

## 5. Đo bằng PromQL rồi chọn threshold

Giữ lịch và region ổn định; đo ở mốc **1 ngày → 14 ngày → 30 ngày** tính từ
lượt Monitor theo lịch đầu tiên pass toàn bộ Staff Journey. Ghi số lượt dự kiến/thực tế,
pass/fail/timeout và thời gian đáp ứng **theo từng URL**. Đối chiếu lỗi với
FastAPI http.log, Nginx log, Loki và Snowflake query history. Lượt bị thiếu
không tính là pass.

## 6. Newman — chạy collection trên VPS, không dùng Postman Cloud

Newman đọc **chính các file YAML trong `postman/collections`** và chuyển trong
bộ nhớ sang Postman Collection v2.1. Không cần export JSON hoặc Postman API.
`public` chạy mỗi 5 phút, `staff` chạy mỗi phút. Mỗi lượt ghi kết quả tổng hợp,
HTTP status và thời gian từng request vào file `.prom`; không ghi body, password
hay cookie. Node Exporter đọc file này để Prometheus/Grafana hiển thị.
Staff gọi lại 13 request mỗi phút; Redis cache có thể trả dashboard mà không
truy vấn Snowflake ở từng lượt. Vì vậy đây là kiểm tra API/luồng đăng nhập,
không phải phép kiểm tra kết nối Snowflake mới mỗi phút.

Nếu chuyển hẳn sang Newman, **tắt lịch hai Postman Cloud Monitors** để không
chạy trùng. Newman trên VPS không phải điểm đo bên ngoài: nếu cả VPS ngừng,
timer cũng ngừng; Grafana sẽ thấy `time() - newman_last_run_timestamp_seconds`
tăng, nhưng cần một probe ngoài VPS để cảnh báo khi cả VPS/Prometheus đều mất.

### 6.1. Chuẩn bị release và tài khoản

Sau khi commit và deploy phiên bản có `deploy/production/newman/` và `postman/`,
kiểm tra cả hai thư mục đã có trong `/opt/superstore/current/`. CI chạy kiểm
thử Newman bằng HTTP server giả; nó không dùng credential production. Trên VPS,
kiểm tra hoặc tạo **staff role sales riêng** như §4.1. Sau đó tạo file cấu hình
root-only và điền email/password của tài khoản đó:

```bash
sudo install -o root -g root -m 600 \
  /opt/superstore/current/deploy/production/newman/newman.env.example \
  /etc/superstore/newman.env
sudo nano /etc/superstore/newman.env
sudo chmod 600 /etc/superstore/newman.env
```

Đặt `API_ORIGIN`, `FRONTEND_ORIGIN`, `MONITOR_EMAIL_SALES`,
`MONITOR_PASSWORD_SALES`; không dùng `{{vault:...}}` vì Newman không đọc
Postman Vault. File này không nằm trong Git. Không thêm secret vào command,
collection YAML, log hoặc Grafana.

### 6.2. Chạy tay trước khi bật lịch

```bash
NEWMAN=/opt/superstore/current/deploy/production/newman
sudo bash "$NEWMAN/run.sh" public
sudo bash "$NEWMAN/run.sh" staff
```

Lần đầu script build image Newman từ `package-lock.json`; các lượt sau dùng
image cùng release. Cả hai phải in `PASS`, `requests=5` và `requests=13`.
Nếu staff fail, xem tên request trong output; login cần `200`, bước
`/staff/me` sau login cần `200`. Script trả mã khác `0` khi thất bại.
File kết quả kiểm thử tay nằm ở
`/opt/superstore/metrics/newman/newman-{public,staff}-manual.prom`. Lượt chạy
tay có nhãn `mode="manual"`, không đi vào dashboard theo lịch.

### 6.3. Bật lịch tự chạy

```bash
sudo bash "$NEWMAN/install.sh"
systemctl list-timers 'superstore-newman@*'
sudo systemctl start superstore-newman@public.service
sudo systemctl start superstore-newman@staff.service
sudo journalctl -u 'superstore-newman@*.service' -n 50 --no-pager
```

Hai timer dùng `/opt/superstore/current`, nên release mới dùng collection/code
mới khi timer chạy tiếp. `install.sh` nạp và khởi động lại timer để áp dụng
lịch mới. Hai collection có khóa chạy riêng; một lượt Staff chậm không chặn
Public. Khi cần dừng
lịch: `sudo systemctl disable --now superstore-newman@public.timer
superstore-newman@staff.timer`.
Kết quả theo lịch nằm ở `newman-{public,staff}-timer.prom` với nhãn
`mode="timer"`.

## 7. Xem kết quả trên Prometheus và Grafana

Sau khi cài trên VPS, tạo lại đúng hai container để nạp mount/config mới:

```bash
COMPOSE=/opt/superstore/current/deploy/production/bin/compose.sh
sudo bash "$COMPOSE" up -d --force-recreate node-exporter grafana
```

Sau một lượt Newman và một lần scrape (15 giây), kiểm tra:

```bash
curl -i -fsSG http://127.0.0.1:9090/api/v1/query \
  --data-urlencode 'query=newman_last_run_success{mode="timer"}'
curl -i -fsSG http://127.0.0.1:9090/api/v1/query \
  --data-urlencode 'query=node_textfile_scrape_error'
```

**Mong đợi:** có hai series (`collection="public"` và `collection="staff"`,
đều có `mode="timer"`) với giá trị `1` khi pass;
`node_textfile_scrape_error=0`. Mở Grafana qua SSH tunnel ở
[Operation §0.3](operation.md) → folder **Superstore Monitoring** → dashboard
**Superstore — Newman synthetic checks**. Dashboard có lần chạy mới nhất,
