# Testing Strategy — Superstore

Trang này định nghĩa phạm vi và tiêu chí kiểm thử. [Test Plan](test_plan.md)
định nghĩa case/expected result; [Traceability Matrix](traceability_matrix.md)
lưu liên kết với requirement và bằng chứng; [Test Operations](operation.md)
là nơi duy nhất hướng dẫn chạy test. Runbook [API](../API/operation.md) và
[Frontend](../frontend/operation.md) chỉ hướng dẫn cấu hình và khởi chạy service.

## 1. Scope

- FastAPI: staff authentication, API key, session, RBAC, dashboard validation,
  response contract, liveness và HTTP observability.
- Next.js: redirect, login/logout, cookie và BFF Origin guard.
- Data platform: dbt generic tests trong YAML và singular tests trong `data_platform/superstore_db/tests/`.

## 2. Test levels

| Level         | Vị trí                                | Mục đích                                                  |
| ------------- | ------------------------------------- | --------------------------------------------------------- |
| Unit          | `RAG_CHATBOT/tests/auth`, `dashboard` | Kiểm tra auth helper, month key và response contract      |
| API/component | `RAG_CHATBOT/tests/auth`, `dashboard`, `operations` | Kiểm tra HTTP bằng TestClient; SQLite tạm, Snowflake mock; kiểm tra health, metrics và log |
| Integration   | `RAG_CHATBOT/tests/integration`       | Kiểm tra nhiều thành phần FastAPI cùng hoạt động          |
| Browser E2E   | `RAG_CHATBOT/frontend/e2e`            | Kiểm tra browser → Next.js BFF → FastAPI                  |
| Data quality  | dbt YAML và singular SQL              | Kiểm tra dữ liệu sau khi pipeline nạp                     |

TestClient + query giả lập **không** chứng minh Snowflake thật hoạt động.
Các test login hiện vẫn gọi Redis thật để giới hạn đăng nhập; test observability
dùng file log tạm và kiểm tra `/metrics` của tiến trình test, không kiểm tra
Prometheus server. dbt data tests chạy trong Airflow sau khi nạp từng layer;
PR CI chỉ chạy `dbt parse`, không kết nối Snowflake.

## 3. Environment và test data

- Unit/API: SQLite và HTTP log trong `tmp_path`, staff `@company.com`, API
  key/JWT chỉ dùng cho test; nhóm login cần Redis khả dụng.
- E2E trên CI: staff test role `marketing`, SQLite tạm riêng và password sinh cho từng run.
- E2E local Docker: dùng API/frontend container và staff SQLite trong volume `staff_auth_data` của stack đang chạy; tài khoản test tạo một lần, credential nằm trong file `frontend/e2e-test-env` bị Git ignore. Đây **không phải** database test riêng, nên không chạy với stack production.
- Không dùng tài khoản staff, database Snowflake hoặc secret production.
- `Frontend_Origin` phải khớp chính xác Origin của browser.

## 4. Pass criteria

Một PR chỉ sẵn sàng merge khi pytest, lint, type-check, build, E2E, Compose/DE contract và dbt parse đều pass; không còn defect nghiêm trọng chưa xử lý. Chỉ khi GitHub cấu hình các job này là **required status checks** thì gate fail mới chặn merge.

Coverage là tín hiệu hỗ trợ, không thay thế test case. Chưa có số đo coverage được xác minh cho suite hiện tại, nên CI chưa bật ngưỡng `--cov-fail-under`.

## 5. Quy trình mỗi Story

Requirement Analysis → Test Design → Test Implementation → Test Execution → Defect Management → CI Quality Gate → Test Reporting → Traceability.

Mỗi Acceptance Criterion phải có ít nhất một test case hoặc ghi rõ lý do chưa tự động hóa. Kết quả test được lấy từ CI/lần chạy thực tế, không ghi “PASS” mặc định trong tài liệu.

## 6. Known gaps

- Login tests dùng Redis thật: local cần bật Redis, CI cấp Redis service riêng
  cho backend/E2E. Chưa có test riêng cho cache Redis hoặc Snowflake thật.
- Test observability mới kiểm tra request thành công, liveness, metrics và
  redaction; chưa kiểm tra readiness `503` hoặc log của request lỗi.
- Unit auth đã có cho password hash, email domain, JWT khi đổi role và quyền metric; chưa có test mọi nhánh/edge case của các helper này.
- Frontend E2E mới bao phủ redirect, login/logout, cookie, sai mật khẩu và Origin guard; chưa kiểm tra metric thật với Snowflake.
- Chưa có test tự động cho cache runtime và hai nhánh BFF allowlist/method (`404`/`405`); Test Operations ghi cách kiểm tra thủ công.
- Chưa đo lại coverage và chưa xác minh required status checks trong GitHub.
