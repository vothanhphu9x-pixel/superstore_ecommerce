# Test Operations — Superstore

File này là nơi chạy test. Phạm vi và expected result theo
[Test Plan](test_plan.md); kết quả từng case ghi trong
[Traceability Matrix](traceability_matrix.md).

## 1. Chạy toàn bộ trước commit

Chuẩn bị backend `.venv`, Redis, `data_platform/.env`, staff E2E (mục 2.8),
`airflow-scheduler` và dữ liệu Snowflake đã nạp đủ (mục 2.9). Sau đó chạy từ
root repository:

```bash
cd /Users/macos/Desktop/Superstore_ecommerce
make verify
```

Lệnh dừng ở bước đầu tiên fail. Các lệnh riêng bên dưới dùng để khoanh vùng lỗi,
theo đúng thứ tự `make verify`.

## 2. Các bước theo thứ tự Makefile

### 2.1. Git hygiene

```bash
make verify-hygiene
```

Kiểm tra file nhạy cảm/runtime không lọt Git và lỗi whitespace.

### 2.2. Python syntax

```bash
make python-syntax
```

Kiểm tra cú pháp các file Python chưa bị xóa trong worktree.

### 2.3. Backend — toàn bộ pytest

Sau khi cài `RAG_CHATBOT/requirements-dev.txt`, chạy Redis local trước vì
login tests gọi Redis thật dù `CACHE_ENABLED=false`:

```bash
cd /Users/macos/Desktop/Superstore_ecommerce/data_platform
docker compose up -d redis
cd ..
make backend-check
```

`backend-check` chạy toàn bộ `RAG_CHATBOT/tests/` một lần, gồm Auth, Dashboard,
Integration và Operations/observability; chỉ in thông báo pass nếu mọi test đạt.
Khi cần khoanh vùng, chạy từng target:

```bash
make test-auth
make test-dashboard
make test-integration
make test-operations
```

`make test-operations` kiểm tra liveness, request ID, `/metrics` và `http.log` trong thư mục
tạm. Kết quả pass không chứng minh Prometheus server đã scrape metrics.

**Kiểm tra thêm khi triển khai:** Pytest dùng Snowflake giả lập; CI chỉ kiểm tra
`/health/live`. Sau khi khởi chạy API bằng cấu hình của môi trường đích, kiểm tra:

```bash
curl -i http://localhost:8000/health/live
curl -i http://localhost:8000/health/ready
curl -i http://localhost:8000/api/health/live
curl -i http://localhost:8000/api/health/ready
```

Kết quả theo đúng thứ tự: `/health/live` trả `200` với `status=healthy`;
`/health/ready` trả `200` với `services.snowflake.status=healthy`, hoặc `503`
khi Snowflake lỗi; `/api/health/live` trả `200` với `status=ok`;
`/api/health/ready` trả `200` với `staff_store=true` và `redis=true`, hoặc
`503` nếu một trong hai lỗi. Hai endpoint `ready` kiểm tra **các phụ thuộc khác
nhau**; không dùng kết quả của cái này thay cho cái kia. Đây là kiểm tra môi
trường thật, không thay thế các test auth/dashboard tự động.

### 2.4. Frontend static checks và bảo mật bundle

```bash
cd /Users/macos/Desktop/Superstore_ecommerce
make frontend-check
```

Target này chạy `npm ci` → lint → type-check → production build; **không** chạy
Playwright. Kiểm tra lỗ hổng dependency riêng bằng `npm audit --audit-level=high`
trong `RAG_CHATBOT/frontend`. Nếu audit báo lỗi, xem đường phụ thuộc trước khi
cập nhật; không dùng `npm audit fix --force` chỉ để ép hết cảnh báo. Để kiểm tra
API key không lọt vào bundle browser, vào thư mục frontend và nạp secret local
trong cùng terminal mà không in giá trị:

```bash
cd /Users/macos/Desktop/Superstore_ecommerce/RAG_CHATBOT/frontend
(
set -a
. ./.env.local
set +a

if [ -z "${API_KEY:-}" ]; then
  echo "ERROR: API_KEY is empty"
  exit 1
fi

if rg -q -F "$API_KEY" .next/static; then
  echo "ERROR: API_KEY leaked into browser bundle"
  exit 1
fi

if rg -n 'NEXT_PUBLIC_API_KEY|NEXT_PUBLIC_API_URL' . \
  --glob '!node_modules/**' --glob '!.next/**'; then
  echo "ERROR: internal API configuration exposed as NEXT_PUBLIC"
  exit 1
fi

echo "OK: internal API key is not in browser bundle"
)
```

### 2.5. Docker Compose

```bash
cd /Users/macos/Desktop/Superstore_ecommerce
make compose-check
```

Chỉ kiểm tra cấu hình, không khởi động container.

Ngay sau đó, `make verify` kiểm tra Compose production bằng env mẫu và cú pháp
Prometheus/Alertmanager, gồm cả alert rules:

```bash
make production-config-check
```

Lệnh không đọc secret VPS hoặc gửi cảnh báo thật.

### 2.6. DE pipeline contract

```bash
make pipeline-contract
```

Kiểm tra hợp đồng nguồn và các thành phần của pipeline.

Tiếp theo chạy kiểm tra Newman/Postman offline như PR CI:

```bash
make newman-check
```

Lệnh cài đúng dependency từ lockfile, kiểm tra cú pháp JavaScript và chạy test
collection; không gọi website production.

### 2.7. dbt parse

```bash
make dbt-parse
```

Đọc `data_platform/.env`, cài dbt packages và parse project; chưa test dữ liệu.

### 2.8. Browser E2E với Docker

Không mở thêm server local. API/Next.js dùng cấu hình và staff DB của Docker;
Playwright chạy trên máy Mac và gọi `http://localhost:3000`. Tài khoản E2E
được lưu trong Docker volume `staff_auth_data`, không phải SQLite ở máy host.
Đây là **staff DB của stack Docker đang chạy**, không phải DB test tách biệt:
chỉ dùng stack development, không trỏ vào production.

**Bước 1 — bật container và xem trạng thái:**

```bash
cd /Users/macos/Desktop/Superstore_ecommerce
make frontend-e2e-up
```

**Bước 2 — kiểm tra rồi mới tạo staff `marketing`:**

```bash
docker exec -it superstore_api python -m scripts.manage_staff list
```

Nếu danh sách đã có `e2e.superstore.2026@gmail.com` với role `marketing` và
`ACTIVE=True`, **bỏ qua lệnh `add`**. Nếu chưa có, tạo một lần:

```bash
docker exec -it superstore_api \
  python -m scripts.manage_staff add e2e.superstore.2026@gmail.com \
  --name "E2E Tester" --role marketing
```

CLI hỏi password hai lần. Nhập **đúng password trong**
`RAG_CHATBOT/frontend/e2e-test-env`; chỉ dùng tài khoản test. Nếu tài khoản đã
có nhưng sai role hoặc đang bị khóa, chỉ chạy lệnh sửa tương ứng thay vì tạo lại:

```bash
docker exec -it superstore_api \
  python -m scripts.manage_staff role e2e.superstore.2026@gmail.com marketing
docker exec -it superstore_api \
  python -m scripts.manage_staff enable e2e.superstore.2026@gmail.com
```

Nếu password trong container không khớp `e2e-test-env`, đặt lại:

```bash
docker exec -it superstore_api \
  python -m scripts.manage_staff password e2e.superstore.2026@gmail.com
```

Email phải thuộc `INTERNAL_EMAIL_DOMAINS` của API container.
Tạo lại container không cần tạo lại user vì volume giữ dữ liệu; chỉ chạy lệnh
`add` lần đầu hoặc sau khi volume staff bị xóa. Email CLI phải trùng
`E2E_STAFF_EMAIL` trong `e2e-test-env`.

**Bước 3 — chạy test và quan sát:**

```bash
cd /Users/macos/Desktop/Superstore_ecommerce
make frontend-e2e
```

Muốn xem browser chạy trực tiếp, thay lệnh trên bằng
`make frontend-e2e E2E_ARGS=--headed`.

Target sẽ build/chạy lại API và Next.js, cài npm/Chromium nếu cần rồi chạy
Playwright. Nó nạp `E2E_STAFF_EMAIL` và `E2E_STAFF_PASSWORD` từ
`e2e-test-env` (Git ignore), **không tự tạo hay đổi staff**. Mở
`http://localhost:3000/login` để tự đăng nhập; dùng `E2E_ARGS=--debug` nếu muốn
dừng từng bước trong Playwright Inspector. Xem log server bằng:

```bash
cd /Users/macos/Desktop/Superstore_ecommerce/data_platform
docker compose --profile app logs -f api frontend
```

`APP_ORIGIN` trong `frontend/.env.local` phải đúng
`http://localhost:3000`; nếu khác, POST login/logout sẽ bị chặn `403` (thiếu
biến khi chạy production sẽ trả `500`). File
`e2e-test-env` là credential local bị Git ignore; CI không đọc file này.

**Kiểm tra BFF thủ công khi cần truy lỗi:**

```bash
curl -i http://localhost:3000/api/internal/health
curl -i http://localhost:3000/api/health
curl -i -X PUT http://localhost:3000/api/internal/dashboard
curl -i -X POST -H 'Origin: http://untrusted.example' \
  http://localhost:3000/api/internal/staff/logout
```

Kỳ vọng theo thứ tự: `404` (route ngoài allowlist); `200` với
`{"status":"ok","api":"up"}` nếu Next.js gọi được FastAPI, ngược lại `503`;
`405` (method PUT không được mở); `403` (Origin khác `APP_ORIGIN`). Playwright
đã tự kiểm tra Origin guard trong `frontend/e2e/login.spec.ts`; hai ca
allowlist/method còn là kiểm tra thủ công. Không đưa API key hoặc cookie thật
vào kết quả test.

### 2.9. dbt data tests trên Snowflake

Sau khi pipeline đã nạp đủ các layer vào Snowflake, chạy từ root repository:

```bash
cd /Users/macos/Desktop/Superstore_ecommerce
make dbt-tests
```

`dbt-tests` dùng dbt venv trong `airflow-scheduler`, chạy Staging → Snapshot →
Silver → Gold → Mart → singular và dừng ở layer đầu tiên fail. Khi chỉ cần một
layer, dùng `make dbt-test-staging`, `dbt-test-snapshot`, `dbt-test-silver`,
`dbt-test-gold`, `dbt-test-mart` hoặc `dbt-test-singular`. Mỗi target tự chặn
nếu account Snowflake trong container không khớp `data_platform/.env`; khi đổi
cấu hình phải tạo lại `airflow-scheduler` trước.
Airflow tự chạy generic tests ngay sau từng layer và singular tests sau Mart;
PR CI chỉ chạy `dbt parse`, không xem parse pass là data quality pass.

## 3. Chạy và đọc kết quả trên CI

Chỉ commit khi `make verify` pass. PR CI chạy lại các kiểm tra không cần
Snowflake thật trên runner sạch, với staff E2E tạm và cấu hình giả cho dbt parse.

Workflow `.github/workflows/quality.yml` (`Quality Gate`) tự chạy khi mở/cập nhật
Pull Request và khi push vào `main`:

1. Commit thay đổi vào một branch và push branch đó lên GitHub.
2. Mở hoặc cập nhật Pull Request vào `main`; không cần tự khởi động workflow.
3. Trong Pull Request → **Checks** (hoặc Actions → `Quality Gate`), mở từng job:

| Job                     | Kiểm tra                                                                    | Khi fail, xem trước                                         |
| ----------------------- | --------------------------------------------------------------------------- | ----------------------------------------------------------- |
| `Repository hygiene`    | File/secret/runtime data không lọt vào Git                                  | Bước `check_repo_hygiene.py`                                |
| `Python syntax`         | Compile Python đã được Git track                                            | File và dòng báo syntax error                               |
| `FastAPI tests`         | Toàn bộ `RAG_CHATBOT/tests/` (gồm operations), Redis test và `/health/live` | Test case fail hoặc log FastAPI                             |
| `Next.js checks`        | `npm ci`, lint, type-check, build, E2E Playwright với Redis test            | Bước đầu tiên fail; nếu E2E fail, xem log API/Next cuối job |
| `Newman synthetic checks` | Cú pháp runner và test Postman collection offline                         | Bước `npm run check` hoặc `npm test`                         |
| `Compose and dbt parse` | Compose dev/production, Monitoring rules, DE contract, dbt deps/parse      | Lỗi cấu hình, alert rule hoặc model/dbt parse                |

Job `Next.js checks` tự tạo SQLite staff test tạm, sinh password/JWT secret tạm,
seed staff `marketing`, cài Chromium rồi chạy FastAPI và Next.js trước khi chạy
`npm run test:e2e`. Không đưa credential thật vào workflow.

Workflow **chưa có `workflow_dispatch`**, nên hiện không chạy bằng nút **Run
workflow**. Khi cần chạy lại, dùng chức năng **Re-run failed jobs** trên lần chạy
đó (nếu tài khoản có quyền), hoặc cập nhật PR bằng commit mới.

CI chỉ chạy `dbt parse` với cấu hình giả an toàn; nó **không chạy dbt data tests
trên Snowflake**. Các test dữ liệu Staging → Snapshot → Silver → Gold → Mart và
singular tests chạy trong Airflow sau khi pipeline nạp xong.

Workflow báo đỏ chỉ thực sự chặn merge khi các job cần thiết được đặt thành
**required status checks** trong GitHub branch ruleset/protection cho `main`.
Cấu hình này nằm trên GitHub, không nằm trong file YAML của repo.

## 4. Deploy smoke trên production

CD tự chạy `deploy/production/tests/smoke_public.py` sau khi Quality Gate pass
và API/frontend được deploy. Cấu hình GitHub Environment: `FRONTEND_ORIGIN`
(variable), `MONITOR_EMAIL` và `MONITOR_PASSWORD` (secrets). Đây là gate riêng,
không thuộc Dev/Makefile hay PR CI.

| Case ID | Kiểm tra | Kết quả mong đợi |
| ------- | -------- | ---------------- |
| `DEPLOY-01` | Public health | `/api/health` trả `200`, `status=ok`, `api=up`. |
| `DEPLOY-02` | Truy cập trước login | `/api/internal/staff/me` trả `401`. |
| `DEPLOY-03` | Login và cookie CFO | Login thành công với role `cfo`; cookie có `Secure`, `HttpOnly`, `SameSite=Lax`, `Path=/`. |
| `DEPLOY-04` | KPI contract | CFO đọc được KPI; response có đủ field bắt buộc. |
| `DEPLOY-05` | Dashboard RBAC | `by-category` không có trong index của CFO; gọi trực tiếp trả `403`. |
| `DEPLOY-06` | Logout | Cookie bị xóa; `/api/internal/staff/me` sau logout trả `401`. |

Smoke chỉ đọc dữ liệu nghiệp vụ; có thể ghi rate-limit, cache và logs. Kết quả
ghi nhận theo release/CD run.

Chi tiết: [Test Plan](test_plan.md), [Traceability Matrix](traceability_matrix.md).
Khi fail, xem step `Smoke test production website and CFO access` trong job CD;
không chạy lại bằng credential production nếu chưa được phép.

## 5. Monitoring end-to-end — Phase 8

Đây là kiểm tra sau khi monitoring đã triển khai, khác với browser E2E và CD
deploy smoke. Đọc tiêu chí `E2E-01`–`E2E-08` trong [Test Plan §2.9](test_plan.md)
và ghi kết quả thực vào [báo cáo Phase 8](end_to_end_validation.md).

### 5.1. Chuẩn bị môi trường

Ghi môi trường, release SHA và thời điểm UTC trước khi chạy. Production chỉ
gửi request nhỏ và đọc metrics/logs. Các ca cố ý tạo `503` hoặc dừng
API/Redis/exporter cần **stack staging riêng**, với database, secret, đường log
và hộp thư thử riêng. Repo chưa có Compose staging hoặc nguồn tạo `503` riêng
cho staging: giữ `E2E-04`–`E2E-08` ở trạng thái `BLOCKED` tới khi có môi trường
phù hợp. Không dùng Compose production để chạy fault injection.

### 5.2. Quan sát production — `E2E-01`–`E2E-03`

1. Theo [Monitoring Operation §1.1–1.2](../deploy/monitoring/operation.md),
   đo Counter/Histogram trước và sau một request thật; lưu route, status, giá
   trị và thời điểm. `/metrics`, `/api/health/live`, `/api/health/ready` bị
   loại khỏi HTTP Counter/Histogram, nên dùng request API khác.
2. Theo [Monitoring Operation §2](../deploy/monitoring/operation.md), lấy
   `x-request-id` của response và đối chiếu FastAPI `http.log`, Nginx access
   log và hai stream Loki. Request cần đi qua Nginx để kiểm tra Nginx log.
3. Kiểm tra timer Newman `public`/`staff`, trạng thái Kuma, năm target
   `up=1` (gồm Alertmanager sau Phase 7), `redis_up=1` và các panel tương ứng.
   Hai truy vấn `newman_last_run_timestamp_seconds{job="node",mode="timer"}`
   và `newman_consecutive_failures{job="node",mode="timer"}` phải trả hai
   collection mỗi truy vấn; `node_textfile_scrape_error{job="node"}=0` chỉ
   xác nhận collector không báo lỗi đọc file. Dùng
   [Query Library](../deploy/monitoring/promql_logql_library.md) và
   [Synthetic Baseline](../deploy/monitoring/synthetic_baseline.md).
Panel có dữ liệu hoặc container `Running` không đủ để đánh dấu `PASS`; lưu
giá trị truy vấn, log hoặc ảnh tại cùng khoảng thời gian.

### 5.3. Tạo lỗi và phục hồi trên staging — `E2E-04`–`E2E-08`

Chạy từng ca riêng, sau đó phục hồi và xác nhận bình thường trước khi sang ca
tiếp theo. Staging cần cùng tên Prometheus job/rule và chu kỳ scrape `15s` như
[cấu hình production](../../deploy/production/prometheus.yml), nhưng dùng
receiver email thử. Rule target/Redis có `for: 2m`: ghi lần lượt Pending,
Firing, receiver/email và Resolved. [Monitoring Operation §7.3](../deploy/monitoring/operation.md)
mô tả cách thử email bằng rule riêng trên staging.

| Case | Tác động trên staging | Bằng chứng cần lưu |
| ---- | --------------------- | ------------------ |
| `E2E-04` | Gửi request tới nguồn trả `503` chỉ có trên staging | Counter nhãn `status="503"`, HTTP/Nginx log và Loki |
| `E2E-05` | Dừng Redis, giữ exporter | `up{job="redis"}=1`, `redis_up=0`, `SuperstoreRedisUnavailable` Pending → Firing |
| `E2E-06` | Dừng riêng Redis exporter, phục hồi; sau đó dừng riêng API | `up{job="redis"}=0` rồi `up{job="fastapi"}=0`; `SuperstoreScrapeTargetDown` Pending → Firing cho từng target |
| `E2E-07` | Giữ lỗi đến khi alert Firing | Alertmanager nhận đúng receiver và email Firing đến hộp thư thử |
| `E2E-08` | Khởi động lại thành phần vừa dừng | `up`/`redis_up` về `1`, alert hết Firing và email Resolved đến hộp thư thử |

Chỉ ghi `PASS` cho luồng email khi hộp thư nhận thật. `E2E-04` gửi một request
`503`, chưa đạt rule 5xx ≥3 lỗi trên cùng route trong 5 phút, nên ca này không
yêu cầu email. Sau ca cuối, xác nhận các
service staging hoạt động và không còn alert thử Firing; gỡ rule thử khỏi
staging. `make production-config-check` đã chạy rule test bằng dữ liệu giả,
không thay cho kiểm tra end-to-end này.

### 5.4. Kết quả

Điền UTC, release SHA, giá trị trước/sau, log/panel/email và defect vào
[báo cáo Phase 8](end_to_end_validation.md). Phase 8 chỉ `DONE` khi các ca
bắt buộc pass, staging đã phục hồi và email Firing/Resolved được xác nhận.

## 6. Ghi nhận kết quả

Với mỗi PR, ghi Case ID, kết quả, URL GitHub Actions/Airflow run và Defect ID
(nếu có) vào mục **Test traceability** của PR template. Cập nhật
[Traceability Matrix](traceability_matrix.md) khi thêm/đổi case, test hoặc chốt
baseline. Không đánh dấu `PASS` chỉ vì test file đã tồn tại hoặc `dbt parse`
thành công.

Monitoring Phase 8 dùng [báo cáo riêng](end_to_end_validation.md); cập nhật
[Traceability Matrix](traceability_matrix.md) khi case/requirement thay đổi hoặc
khi chốt baseline đã xác minh. Ca chưa thể chạy ghi `BLOCKED`.

Chưa thêm `--cov-fail-under` vào CI. Đo coverage của suite hiện tại rồi mới
thống nhất ngưỡng chặn merge.
