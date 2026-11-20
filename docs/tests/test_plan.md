# Test Plan — Superstore

> Các mã `TRAIN-*` dùng để luyện tập, không phải Jira ID thật. Thay bằng Story ID chính thức khi áp dụng vào PR.

File này mô tả case và kết quả mong đợi; lệnh chạy nằm trong
[Test Operations](operation.md), bằng chứng từng case nằm trong
[Traceability Matrix](traceability_matrix.md).

## 1. Phạm vi và trạng thái

| Domain          | Phạm vi                                                       | Hiện trạng                                                                                  |
| --------------- | ------------------------------------------------------------- | ------------------------------------------------------------------------------------------- |
| Authentication  | API key, staff login, cookie, RBAC, logout, rate limit        | Có `tests/auth/test_staff_api.py` và `test_internal_auth.py`                                |
| Dashboard       | Validation, quyền xem metric, response contract, lỗi truy vấn | Có `tests/dashboard/`                                                                       |
| API integration | Login → đổi role → đăng nhập lại → logout                     | Có `tests/integration/test_api_flow.py`                                                     |
| Operations      | Liveness, request ID, HTTP metrics và log không lộ secret     | Có `tests/operations/test_observability.py`                                                 |
| Frontend E2E    | Redirect, login/logout qua BFF, cookie, Origin guard          | Có 4 test trong `frontend/e2e/login.spec.ts`                                                |
| Data quality    | Staging, Snapshot, Silver, Gold, Mart                         | Có dbt YAML và singular SQL tests; chạy local/Airflow, không chạy trong PR CI               |
| CI              | Tự động chạy test và báo fail                                 | Có `.github/workflows/quality.yml`; required checks chưa xác minh                           |
| Deploy smoke    | Kiểm tra website/API production sau khi deploy                | Có `deploy/production/tests/smoke_public.py`; chạy trong workflow CD, không thuộc Dev/PR CI |
| Newman offline  | Kiểm tra collection/runner và metric xuất ra không lộ secret | Có `deploy/production/newman/test/runner.test.js`; Local/CI không gọi production |
| Monitoring E2E | Request → metrics/logs → alert/email → phục hồi | Có cấu hình metrics/rule/log; chưa có staging để tạo lỗi có chủ đích |

## 2. Test cases

### 2.1 Authentication — `TRAIN-AUTH-01`

| Case ID | Tình huống                              | Expected                                    | Test                                                                                                          | Triển khai |
| ------- | --------------------------------------- | ------------------------------------------- | ------------------------------------------------------------------------------------------------------------- | ---------- |
| AUTH-01 | Thiếu hoặc sai API key                  | `403`                                       | `test_missing_request_key_is_forbidden`, `test_wrong_request_key_is_forbidden`, `test_login_requires_api_key` | Có         |
| AUTH-02 | API chưa cấu hình key                   | `503`, không mở endpoint                    | `test_missing_api_configuration_fails_closed`                                                                 | Có         |
| AUTH-03 | Sai mật khẩu                            | `401`, không tạo cookie                     | `test_wrong_password_does_not_create_session`                                                                 | Có         |
| AUTH-04 | Đăng nhập đúng                          | `200`, cookie `HttpOnly`, `/me` trả profile | `test_valid_login_sets_cookie_and_unlocks_index`                                                              | Có         |
| AUTH-05 | Có API key nhưng không có staff session | `401`                                       | `test_api_key_without_staff_session_is_unauthorized`                                                          | Có         |
| AUTH-06 | Có cookie nhưng thiếu API key           | `403`                                       | `test_staff_cookie_does_not_replace_api_key`                                                                  | Có         |
| AUTH-07 | Cookie không hợp lệ hoặc role đã đổi    | `401`                                       | `test_invalid_staff_cookie_is_unauthorized`, `test_role_change_invalidates_existing_cookie`                   | Có         |
| AUTH-08 | Logout                                  | Xóa cookie; lần gọi sau trả `401`           | `test_logout_clears_cookie_and_session`                                                                       | Có         |
| AUTH-09 | Login vượt giới hạn                     | `429`, có `Retry-After`                     | `test_login_rate_limit_returns_429`                                                                           | Có         |

Các case API trên nằm trong `RAG_CHATBOT/tests/auth/test_staff_api.py`. `test_internal_auth.py` kiểm tra thêm password hash, xác thực staff, domain email, token cũ sau đổi role và quyền xem metric.

### 2.2 Dashboard và contract — `TRAIN-DASH-01`

| Case ID | Tình huống                                               | Expected                                          | Test                                                                  | Triển khai                       |
| ------- | -------------------------------------------------------- | ------------------------------------------------- | --------------------------------------------------------------------- | -------------------------------- |
| DASH-01 | Role chỉ thấy metric và contract được phép               | Index chỉ liệt kê metric được phép; KPI trả `403` | `test_dashboard_index_and_metric_follow_staff_role`                   | Có trong `test_dashboard_api.py` |
| DASH-02 | Metric hợp lệ                                            | `200`, dữ liệu đúng contract                      | `test_authorized_metric_uses_session_without_snowflake`               | Có trong `test_dashboard_api.py` |
| DASH-03 | Month key không hợp lệ                                   | `422`                                             | `test_time_dashboard_validation.py`; `test_invalid_month_returns_422` | Có cả unit và API test           |
| DASH-04 | Metric không tồn tại                                     | `404`                                             | `test_unknown_metric_returns_404`                                     | Có trong `test_dashboard_api.py` |
| DASH-05 | Query trả payload sai contract                           | `502`, không trả dữ liệu sai cho client           | `test_invalid_query_payload_returns_502`                              | Có trong `test_dashboard_api.py` |
| DASH-06 | Query phát sinh lỗi                                      | `502`, không lộ chi tiết nội bộ                   | `test_query_failure_returns_502`                                      | Có trong `test_dashboard_api.py` |
| DASH-07 | Mỗi metric có contract; sai shape/thiếu field bị từ chối | Contract validation fail                          | `test_contracts.py`                                                   | Có trong `tests/dashboard/`      |

Các API test dùng query giả lập; chúng **không chứng minh** truy vấn Snowflake thật trả dữ liệu đúng.

### 2.3 API integration — `TRAIN-FLOW-01`

| Case ID | Luồng                                                                                                    | Expected                                   | Test                                                                                 | Triển khai |
| ------- | -------------------------------------------------------------------------------------------------------- | ------------------------------------------ | ------------------------------------------------------------------------------------ | ---------- |
| FLOW-01 | Staff marketing login → vào dashboard → đổi role thành admin → cookie cũ bị từ chối → login lại → logout | Quyền và session cập nhật đúng ở từng bước | `tests/integration/test_api_flow.py::test_login_role_change_relogin_and_logout_flow` | Có         |

Test này đi qua FastAPI router, auth service và SQLite test; login còn gọi Redis
thật để giới hạn đăng nhập. Chưa kiểm tra Snowflake thật.

### 2.4 Operations và observability — `TRAIN-OBS-01`

| Case ID | Tình huống                                                | Expected                                                                                                 | Test                                                                                   | Triển khai |
| ------- | --------------------------------------------------------- | -------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------- | ---------- |
| OBS-01  | Gọi endpoint liveness và HTTP request có tham số nhạy cảm | `/api/health/live` trả `200`; response có request ID; `/metrics` có counter với nhãn route dạng template | `tests/operations/test_observability.py::test_operations_and_redacted_request_logging` | Có         |
| OBS-02  | Gửi API key, cookie và query/path chứa giá trị nhạy cảm   | `http.log` có route `/test/{item_id}` nhưng không chứa giá trị nhạy cảm hoặc giá trị path thật           | Cùng test OBS-01                                                                       | Có         |

Test dùng FastAPI riêng và thư mục log tạm; không chứng minh Prometheus server
đang thu thập metrics hoặc readiness kiểm tra Redis/staff store thành công.

### 2.5 Frontend E2E và BFF — `TRAIN-FE-01`

| Case ID | Tình huống                            | Expected                                                                                   | Test                                                          | Triển khai |
| ------- | ------------------------------------- | ------------------------------------------------------------------------------------------ | ------------------------------------------------------------- | ---------- |
| FE-01   | Chưa login mở `/dashboard`            | Redirect sang `/login?next=/dashboard`                                                     | `login.spec.ts`: unauthenticated dashboard redirects to login | Có         |
| FE-02   | Login đúng qua Next.js                | Vào dashboard; cookie `HttpOnly`, `SameSite=Lax`; browser không gọi cổng FastAPI trực tiếp | `login.spec.ts`: staff can log in and log out through Next.js | Có         |
| FE-03   | Logout rồi mở dashboard               | Cookie không còn; redirect về login                                                        | Cùng test E2E của FE-02                                       | Có         |
| FE-04   | Sai mật khẩu                          | Hiển thị lỗi; không có session                                                             | `login.spec.ts`: wrong password does not create a session     | Có         |
| FE-05   | POST từ Origin khác `Frontend_Origin` | BFF trả `403`                                                                              | `login.spec.ts`: BFF rejects a cross-site POST                | Có         |

CI dùng staff test role `marketing` và SQLite tạm riêng. E2E local Docker dùng staff DB trong volume của stack development; tạo tài khoản test một lần. Cả hai không cần nạp dashboard metric từ Snowflake và không kiểm tra toàn bộ data platform.

### 2.6 Data quality — `TRAIN-DATA-01`

dbt generic tests đã khai báo cạnh model trong các file `staging.yml`, `snapshots.yml`, `silver.yml`, `gold.yml`, `mart.yml`. Singular tests ở `data_platform/superstore_db/tests/`. Không chuyển chúng vào `RAG_CHATBOT/tests/`.

| Case ID | Điều cần bảo vệ                                                              | Bằng chứng test hiện có                                                                                         | Expected                       |
| ------- | ---------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------- | ------------------------------ |
| DATA-01 | Staging key và metadata hợp lệ                                               | `models/staging/staging.yml`                                                                                    | Các dbt tests của Staging pass |
| DATA-02 | Snapshot/SCD2 không có khoảng hiệu lực sai hoặc overlap                      | `snapshots/snapshots.yml`                                                                                       | Mỗi test trả 0 dòng lỗi        |
| DATA-03 | Business key active có đúng một current version                              | `assert_scd2_active_business_key_has_one_current.sql`                                                           | 0 dòng lỗi                     |
| DATA-04 | Fact temporal join không match nhiều dimension versions                      | `assert_fact_temporal_join_max_one.sql`                                                                         | 0 dòng lỗi                     |
| DATA-05 | Fact có dimension key khi thời điểm source nằm trong SCD2 window được hỗ trợ | `assert_fact_scd2_key_present_in_supported_window.sql`                                                          | 0 dòng lỗi                     |
| DATA-06 | Soft delete đi từ Silver xuống Gold                                          | `assert_soft_delete_propagation.sql`                                                                            | 0 dòng lỗi                     |
| DATA-07 | Accounting cân Nợ/Có                                                         | `assert_debit_equals_credit.sql`                                                                                | 0 dòng lỗi                     |
| DATA-08 | Mart giữ đúng business rule                                                  | Ví dụ `assert_mart_revenue_consistent.sql`, `assert_mart_pnl_consistent.sql`, `assert_mart_roas_consistent.sql` | 0 dòng lỗi                     |

Airflow hiện chạy dbt test sau từng layer và chạy singular tests **sau Mart**. Không chạy các singular test xuyên layer quá sớm khi model phụ thuộc chưa được tạo.

### 2.7 CI quality gate — `TRAIN-CI-01`

| Case ID | Kiểm tra                               | Hiện trạng                                 | Pass criteria                                                   |
| ------- | -------------------------------------- | ------------------------------------------ | --------------------------------------------------------------- |
| CI-01   | Repository hygiene                     | Job `hygiene` trong `quality.yml`          | `check_repo_hygiene.py` pass                                    |
| CI-02   | Python syntax                          | Job `python-syntax` trong `quality.yml`    | `py_compile` của Python files được track pass                   |
| CI-03   | Backend pytest + API liveness          | Job `backend` trong `quality.yml`          | Pytest pass; FastAPI khởi động và `/health/live` trả thành công |
| CI-04   | Frontend install/lint/type-check/build | Job `frontend` trong `quality.yml`         | `npm ci`, lint, type-check và build đều pass                    |
| CI-05   | Frontend E2E                           | Job `frontend` trong `quality.yml`         | Tạo credential/SQLite tạm; E2E chạy và pass, không skip         |
| CI-06   | Newman collection/runner offline       | `newman/test/runner.test.js`; job `newman` | `npm ci`, cú pháp, public/staff giả lập và metric không lộ secret pass |
| CI-07   | Compose/Monitoring/DE/dbt parse        | Job `configuration` trong `quality.yml`    | Compose, rule Prometheus/Alertmanager, DE contract, dbt parse pass |
| CI-08   | Không cho merge khi gate fail          | Cần xác minh GitHub required status checks | PR không merge được nếu job bắt buộc fail                       |

`dbt parse` trong PR CI chỉ kiểm tra cấu trúc, không thay thế dbt data tests trên Snowflake chạy local/Airflow.
Thứ tự trên theo vị trí job trong `quality.yml`; các job không có `needs` nên GitHub có thể chạy song song.
Nhóm login test cần Redis thật; job backend và frontend E2E hiện cấp Redis
service riêng. Nếu service không khỏe hoặc login trả `503`, CI-03/CI-05 fail.

### 2.8 Production deploy smoke — `TRAIN-DEPLOY-01`

Đây là bước xác minh sau deploy trên website production thật, tách biệt với
pytest, frontend E2E và dbt tests chạy trong Dev/CI. Workflow
`.github/workflows/production.yml` chỉ gọi script sau khi CI thành công và API
cùng frontend đã được deploy.

| Case ID   | Hạng mục           | Tiêu chí đạt                                                               | Kiểm tra          |
| --------- | ------------------ | -------------------------------------------------------------------------- | ----------------- |
| DEPLOY-01 | Public health      | `/api/health` trả `200`, `status=ok`, `api=up`                             | `smoke_public.py` |
| DEPLOY-02 | Anonymous access   | `/api/internal/staff/me` trước login trả `401`                             | `smoke_public.py` |
| DEPLOY-03 | CFO login / cookie | Login role `cfo`; cookie có `Secure`, `HttpOnly`, `SameSite=Lax`, `Path=/` | `smoke_public.py` |
| DEPLOY-04 | KPI contract       | KPI response có đủ field bắt buộc                                          | `smoke_public.py` |
| DEPLOY-05 | Dashboard RBAC     | `by-category` không có trong index và gọi trực tiếp trả `403`              | `smoke_public.py` |
| DEPLOY-06 | Logout             | Cookie bị xóa; `/api/internal/staff/me` sau logout trả `401`               | `smoke_public.py` |

Smoke test lấy `FRONTEND_ORIGIN` từ GitHub Environment variable và credential
CFO từ Environment secrets. Chỉ đọc dữ liệu nghiệp vụ; có thể cập nhật
rate-limit/cache/log runtime. Khi fail, kiểm tra log job, website/API và cấu
hình trước khi đánh dấu release đạt.

### 2.9 Monitoring end-to-end — `TRAIN-MON-01`

Đây là Phase 8 sau khi monitoring được triển khai. Cách chạy và thu thập bằng
chứng ở [Test Operations §5](operation.md#5-monitoring-end-to-end--phase-8);
kết quả từng lần chạy ở [báo cáo Phase 8](end_to_end_validation.md).

| Case ID | Môi trường | Acceptance Criterion | Test / control | Hiện trạng |
| ------- | ---------- | -------------------- | -------------- | ---------- |
| E2E-01 | Production | Request thật làm HTTP Counter và Histogram tăng đúng route/status | Prometheus trước/sau request; `core/observability.py` | Thủ công |
| E2E-02 | Production | Cùng `x-request-id` có trong FastAPI/Nginx log và Loki | Response header, hai file log, LogQL | Thủ công |
| E2E-03 | Production | Newman/Kuma, năm scrape target và bốn chuỗi Newman timer phản ánh đúng trên Prometheus/Grafana; textfile collector không lỗi | Timer, Kuma, `up`, `redis_up`, timestamp/consecutive failures, `node_textfile_scrape_error`, panel | Thủ công |
| E2E-04 | Staging | Request trả `503` làm Counter nhãn `status="503"` tăng; HTTP/Nginx log đi tới Loki | Nguồn tạo `503` chỉ trên staging, PromQL/LogQL | Chưa có staging/nguồn tạo `503` |
| E2E-05 | Staging | Redis dừng nhưng exporter còn chạy: `up{job="redis"}=1`, `redis_up=0`; rule Pending → Firing | `SuperstoreRedisUnavailable` | Có rule; thiếu staging |
| E2E-06 | Staging | Dừng riêng exporter/API: `up{job="redis"}`/`up{job="fastapi"}=0`; rule Pending → Firing | `SuperstoreScrapeTargetDown` | Có rule; thiếu staging |
| E2E-07 | Staging | Firing đến đúng Alertmanager receiver và email thử được nhận | Alertmanager API/log + hộp thư thử | Thiếu staging/bằng chứng email |
| E2E-08 | Staging | Khôi phục service: metric về bình thường, rule hết Firing, email Resolved được nhận | Prometheus, Alertmanager, hộp thư thử | Thiếu staging/bằng chứng email |

`promtool test rules` trong `make production-config-check` kiểm tra logic rule
bằng dữ liệu giả; không thay thế `E2E-05`–`E2E-08`. FastAPI ghi status HTTP cụ
thể như `503`, không ghi nhãn `5xx`. Nginx/Loki chỉ được kiểm chứng nếu request
đi qua Nginx staging. Không gây lỗi hoặc dừng service trên production.

## 3. Môi trường và dữ liệu test

**Giống nhau:** Local `make verify` và PR CI đều kiểm tra hygiene, Python, pytest, frontend lint/type-check/build, Compose dev/production và Monitoring rules, DE contract, Newman offline, dbt parse và E2E. API tests dùng `TestClient`, SQLite tạm, API key/JWT test, tắt cache và mock Snowflake; cả hai E2E đều yêu cầu `Frontend_Origin` khớp URL browser.

| Phần         | Local qua Makefile                                                                                                                          | PR CI                                                                                            |
| ------------ | ------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| Backend      | `make backend-check`: chạy toàn bộ `tests/` một lần trong `.venv`; Redis local cho login.                                                   | Chạy toàn bộ pytest một lần với Redis service riêng; kiểm tra thêm `/health/live`.               |
| Frontend E2E | `make frontend-e2e`: API/Next.js trong Docker development; staff ở volume `staff_auth_data`, credential trong `e2e-test-env` bị Git ignore. | API/Next.js chạy trong job với Redis service; SQLite tạm, staff và secret tạo riêng cho mỗi run. |
| Cấu hình dbt | `make verify` đọc `data_platform/.env`; dbt data tests dùng dbt trong Airflow để kiểm tra dữ liệu đã nạp.                                   | Chỉ parse với cấu hình giả; không kết nối Snowflake.                                             |
| Data quality | Airflow test sau từng layer; `make verify` chạy lại toàn bộ trên Snowflake đã chọn.                                                         | Không chạy dbt data tests.                                                                       |

Không lưu password, cookie, token hoặc bản sao dữ liệu khách hàng thật vào repo hay báo cáo lỗi; không dùng production để tạo dữ liệu lỗi thử nghiệm.

Production deploy smoke là gate riêng sau merge: CD chạy sau khi Quality Gate
thành công, deploy commit đã kiểm tra rồi mới gọi website production. Nó không
được tính vào `make verify` hoặc PR CI.

Monitoring Phase 8 chạy theo [§2.9](#29-monitoring-end-to-end--train-mon-01)
sau khi hệ thống đã triển khai. Production chỉ có ca quan sát an toàn; các ca
tạo lỗi cần staging riêng và không thuộc `make verify` hay PR CI.

## 4. Thứ tự thực thi

1. Chuẩn bị local: backend `.venv`, staff E2E, Airflow và Snowflake đã nạp đủ dữ liệu.
2. `make verify` chạy: Git hygiene → Python syntax → Backend → Frontend static → Compose dev/production và Monitoring rules → DE contract → Newman offline → dbt parse → Docker E2E → dbt data tests; dừng ngay khi có lỗi.
3. Chỉ commit khi toàn bộ pass. PR CI chạy lại các kiểm tra không cần Snowflake thật; Airflow vẫn test dữ liệu sau từng layer.
4. Sau merge, CD deploy đúng commit đã qua Quality Gate rồi chạy các case production được liệt kê ở Mục 2.8. Smoke fail thì release chưa được xác nhận khỏe.
5. Khi vận hành monitoring, chạy Phase 8 theo Mục 2.9; ghi bằng chứng production/staging riêng.

Các lệnh thực thi và cách đọc kết quả chỉ đặt trong [Test Operations](operation.md).

## 5. Tiêu chí pass/fail và xử lý defect

Một domain đạt khi các test bắt buộc pass và có bằng chứng. `dbt parse` không chứng minh data quality; Newman offline không chứng minh website production khỏe. Test bị skip không được tính là pass. Với production, chỉ xác nhận release khỏe khi toàn bộ case deploy smoke đang được script thực thi trong CD run đều pass; monitoring E2E được ghi nhận riêng theo §2.9. Nếu fail, ghi release là chưa đạt và xử lý trước khi thông báo hoàn tất.

Khi fail, ghi:

- Defect ID, severity, Story/Case ID;
- môi trường và commit SHA;
- bước tái hiện;
- expected và actual;
- log/ảnh đã che secret;
- test tái hiện lỗi và kết quả retest.

Lỗi được sửa xong phải chạy lại case lỗi **và** các test liên quan để kiểm tra regression.

## 6. Test report và traceability

Sau mỗi lần chạy, cập nhật [Traceability Matrix](traceability_matrix.md) theo chuỗi:

```text
Story → Acceptance Criterion → Case ID → test function/SQL → Dev/CI, Airflow hoặc production CD run → kết quả
```

Không đánh dấu `PASS` trước khi có kết quả chạy thật.
Với production cases trong Mục 2.8, ghi commit/release SHA và URL production workflow run; không gộp bằng chứng này với PR CI.
Với `E2E-01`–`E2E-08`, ghi UTC, release SHA, giá trị trước/sau, log/panel/email
và defect vào [báo cáo Phase 8](end_to_end_validation.md); matrix chỉ giữ ánh xạ
Case ID ↔ requirement/control và baseline đã xác minh.
