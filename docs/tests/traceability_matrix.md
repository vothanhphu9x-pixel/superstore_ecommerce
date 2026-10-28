# Test Traceability Matrix — Superstore

Matrix này dùng đúng Case ID trong `test_plan.md`. Cột **Code** phản ánh file đang có trong working tree; **không có nghĩa test đã pass trên CI**.
Chi tiết tình huống/expected result xem [Test Plan](test_plan.md); lệnh chạy xem
[Test Operations](operation.md).

Đây là bảng ánh xạ dùng chung; mỗi PR điền các case bị ảnh hưởng và bằng chứng
chạy test trong `.github/pull_request_template/traceability_matrix.md`. Chỉ cập nhật bảng này khi
đổi requirement, Case ID, test/control hoặc ghi nhận một baseline đã xác nhận.

- `Có`: đang tồn tại trong repo.
- `Chưa xác minh`: cần kiểm tra cấu hình ngoài repository.
- Cột kết quả/bằng chứng để trống cho đến khi có baseline được xác nhận cho từng case.
- Một case có nhiều test chỉ đạt khi tất cả test bắt buộc đều pass.

## 1. Authentication

| Jira Story | Case ID | Acceptance Criterion                             | Test / control                                                                                                                                                                                               | Code | Kết quả | Commit / run / bằng chứng | Defect |
| ---------- | ------- | ------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ---- | ------- | ------------------------- | ------ |
|            | AUTH-01 | Thiếu/sai API key bị từ chối                     | `tests/auth/test_staff_api.py::test_missing_request_key_is_forbidden`; `::test_wrong_request_key_is_forbidden`; `::test_login_requires_api_key`                                                              | Có   |         |                           |        |
|            | AUTH-02 | API thiếu cấu hình key phải fail closed          | `tests/auth/test_staff_api.py::test_missing_api_configuration_fails_closed`                                                                                                                                  | Có   |         |                           |        |
|            | AUTH-03 | Sai mật khẩu không tạo session                   | `tests/auth/test_staff_api.py::test_wrong_password_does_not_create_session`; `tests/auth/test_internal_auth.py::test_password_hash_round_trip`                                                               | Có   |         |                           |        |
|            | AUTH-04 | Login đúng tạo HttpOnly cookie và trả profile    | `tests/auth/test_staff_api.py::test_valid_login_sets_cookie_and_unlocks_index`; `tests/auth/test_internal_auth.py::test_staff_authentication`                                                                | Có   |         |                           |        |
|            | AUTH-05 | Có API key nhưng thiếu staff session bị từ chối  | `tests/auth/test_staff_api.py::test_api_key_without_staff_session_is_unauthorized`                                                                                                                           | Có   |         |                           |        |
|            | AUTH-06 | Staff cookie không thay thế API key              | `tests/auth/test_staff_api.py::test_staff_cookie_does_not_replace_api_key`                                                                                                                                   | Có   |         |                           |        |
|            | AUTH-07 | Cookie sai hoặc token cũ sau đổi role bị từ chối | `tests/auth/test_staff_api.py::test_invalid_staff_cookie_is_unauthorized`; `::test_role_change_invalidates_existing_cookie`; `tests/auth/test_internal_auth.py::test_role_change_invalidates_existing_token` | Có   |         |                           |        |
|            | AUTH-08 | Logout xóa session; lần gọi sau trả `401`        | `tests/auth/test_staff_api.py::test_logout_clears_cookie_and_session`                                                                                                                                        | Có   |         |                           |        |
|            | AUTH-09 | Login vượt giới hạn trả `429` và `Retry-After`   | `tests/auth/test_staff_api.py::test_login_rate_limit_returns_429`                                                                                                                                            | Có   |         |                           |        |

Đường dẫn `tests/...` trong ba nhóm backend tính từ `RAG_CHATBOT/`. `test_internal_auth.py::test_rejects_unapproved_domain` và `::test_role_metric_permissions` bổ sung kiểm tra domain email và quyền role; chúng không thay thế các API case ở trên.

## 2. Dashboard và response contract

| Jira Story | Case ID | Acceptance Criterion                                    | Test / control                                                                                                                                                              | Code | Kết quả | Commit / run / bằng chứng | Defect |
| ---------- | ------- | ------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---- | ------- | ------------------------- | ------ |
|            | DASH-01 | Role chỉ thấy metric được phép; KPI sai quyền trả `403` | `tests/dashboard/test_dashboard_api.py::test_dashboard_index_and_metric_follow_staff_role`                                                                                  | Có   |         |                           |        |
|            | DASH-02 | Metric hợp lệ trả `200` và dữ liệu đúng contract        | `tests/dashboard/test_dashboard_api.py::test_authorized_metric_uses_session_without_snowflake`                                                                              | Có   |         |                           |        |
|            | DASH-03 | Month key sai trả `422`                                 | `tests/dashboard/test_time_dashboard_validation.py::test_invalid_month_key`; `tests/dashboard/test_dashboard_api.py::test_invalid_month_returns_422`                        | Có   |         |                           |        |
|            | DASH-04 | Metric không tồn tại trả `404`                          | `tests/dashboard/test_dashboard_api.py::test_unknown_metric_returns_404`                                                                                                    | Có   |         |                           |        |
|            | DASH-05 | Payload sai contract trả `502`                          | `tests/dashboard/test_dashboard_api.py::test_invalid_query_payload_returns_502`                                                                                             | Có   |         |                           |        |
|            | DASH-06 | Query lỗi trả `502`, không lộ lỗi nội bộ                | `tests/dashboard/test_dashboard_api.py::test_query_failure_returns_502`                                                                                                     | Có   |         |                           |        |
|            | DASH-07 | Mỗi query có contract; thiếu field/sai shape bị từ chối | `tests/dashboard/test_contracts.py::test_every_query_has_contract`; `::test_valid_kpi_contract`; `::test_missing_field_fails_contract`; `::test_wrong_shape_fails_contract` | Có   |         |                           |        |

`DASH-02`, `DASH-05` và `DASH-06` dùng Snowflake query giả lập. Không dùng kết quả của chúng làm bằng chứng kết nối Snowflake thật thành công.

## 3. API integration

| Jira Story | Case ID | Acceptance Criterion                                           | Test / control                                                                       | Code | Kết quả | Commit / run / bằng chứng | Defect |
| ---------- | ------- | -------------------------------------------------------------- | ------------------------------------------------------------------------------------ | ---- | ------- | ------------------------- | ------ |
|            | FLOW-01 | Login → đổi role → cookie cũ hết hiệu lực → login lại → logout | `tests/integration/test_api_flow.py::test_login_role_change_relogin_and_logout_flow` | Có   |         |                           |        |

`FLOW-01` tích hợp FastAPI với SQLite test; login còn gọi Redis thật để giới
hạn đăng nhập. Chưa kiểm tra Snowflake thật.

## 4. Operations và observability

| Jira Story | Case ID | Acceptance Criterion                                                                 | Test / control                                                                         | Code | Kết quả | Commit / run / bằng chứng | Defect |
| ---------- | ------- | ------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------- | ---- | ------- | ------------------------- | ------ |
|            | OBS-01  | Liveness trả `200`; HTTP response có request ID; `/metrics` dùng nhãn route template | `tests/operations/test_observability.py::test_operations_and_redacted_request_logging` | Có   |         |                           |        |
|            | OBS-02  | HTTP log không lộ giá trị API key, cookie, query hoặc path thật                      | Cùng test OBS-01                                                                       | Có   |         |                           |        |

Test dùng file log tạm và metrics trong tiến trình TestClient; chưa kiểm tra
Prometheus server hay readiness khi dependency lỗi.

## 5. Frontend E2E và BFF

| Jira Story | Case ID | Acceptance Criterion                                                   | Test / control                                                                            | Code | Kết quả | Commit / run / bằng chứng | Defect |
| ---------- | ------- | ---------------------------------------------------------------------- | ----------------------------------------------------------------------------------------- | ---- | ------- | ------------------------- | ------ |
|            | FE-01   | Chưa login mở dashboard phải chuyển sang login                         | `RAG_CHATBOT/frontend/e2e/login.spec.ts` — _unauthenticated dashboard redirects to login_ | Có   |         |                           |        |
|            | FE-02   | Login qua Next.js tạo cookie đúng; browser không gọi FastAPI trực tiếp | `RAG_CHATBOT/frontend/e2e/login.spec.ts` — _staff can log in and log out through Next.js_ | Có   |         |                           |        |
|            | FE-03   | Logout xóa cookie; vào dashboard lại phải chuyển sang login            | Cùng test E2E của `FE-02`                                                                 | Có   |         |                           |        |
|            | FE-04   | Sai mật khẩu hiển thị lỗi, không tạo session                           | `RAG_CHATBOT/frontend/e2e/login.spec.ts` — _wrong password does not create a session_     | Có   |         |                           |        |
|            | FE-05   | POST từ Origin khác cấu hình bị BFF chặn                               | `RAG_CHATBOT/frontend/e2e/login.spec.ts` — _BFF rejects a cross-site POST_                | Có   |         |                           |        |

CI dùng SQLite staff tạm. E2E local Docker dùng volume staff của stack development, nên không chạy trên stack production.

## 6. Data quality

| Jira Story | Case ID | Acceptance Criterion                                                  | Test / control                                                                                                                              | Code | Kết quả | Commit / run / bằng chứng | Defect |
| ---------- | ------- | --------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- | ---- | ------- | ------------------------- | ------ |
|            | DATA-01 | Staging key và metadata đáp ứng các ràng buộc đã khai báo             | `data_platform/superstore_db/models/staging/staging.yml`                                                                                    | Có   |         |                           |        |
|            | DATA-02 | Snapshot SCD2 có version key và khoảng hiệu lực hợp lệ, không overlap | `data_platform/superstore_db/snapshots/snapshots.yml`                                                                                       | Có   |         |                           |        |
|            | DATA-03 | Business key active có đúng một current version                       | `data_platform/superstore_db/tests/assert_scd2_active_business_key_has_one_current.sql`                                                     | Có   |         |                           |        |
|            | DATA-04 | Một fact source không match nhiều SCD2 dimension versions             | `data_platform/superstore_db/tests/assert_fact_temporal_join_max_one.sql`                                                                   | Có   |         |                           |        |
|            | DATA-05 | Fact có dimension SK khi source nằm trong SCD2 window được hỗ trợ     | `data_platform/superstore_db/tests/assert_fact_scd2_key_present_in_supported_window.sql`                                                    | Có   |         |                           |        |
|            | DATA-06 | Soft delete được truyền từ Silver xuống Gold                          | `data_platform/superstore_db/tests/assert_soft_delete_propagation.sql`                                                                      | Có   |         |                           |        |
|            | DATA-07 | Bút toán đáp ứng kiểm tra cân Nợ/Có                                   | `data_platform/superstore_db/tests/assert_debit_equals_credit.sql`                                                                          | Có   |         |                           |        |
|            | DATA-08 | Mart giữ các business rule đã khai báo                                | `data_platform/superstore_db/tests/assert_mart_revenue_consistent.sql`; `assert_mart_pnl_consistent.sql`; `assert_mart_roas_consistent.sql` | Có   |         |                           |        |

dbt YAML tests chạy sau layer tương ứng; singular tests xuyên layer chạy sau khi Mart đã được tạo. `dbt parse` không phải bằng chứng `DATA-01` đến `DATA-08` đã pass.

## 7. CI quality gate

| Jira Story | Case ID | Acceptance Criterion                                          | Test / control                                 | Code          | Kết quả | Commit / run / bằng chứng | Defect |
| ---------- | ------- | ------------------------------------------------------------- | ---------------------------------------------- | ------------- | ------- | ------------------------- | ------ |
|            | CI-01   | Repository hygiene pass                                       | `quality.yml` — job `hygiene`                  | Có            |         |                           |        |
|            | CI-02   | Python files được track biên dịch cú pháp thành công          | `quality.yml` — job `python-syntax`            | Có            |         |                           |        |
|            | CI-03   | Backend pytest pass; FastAPI khởi động và `/health/live` pass | `quality.yml` — job `backend`                  | Có            |         |                           |        |
|            | CI-04   | Frontend `npm ci`, lint, type-check và build pass             | `quality.yml` — job `frontend`                 | Có            |         |                           |        |
|            | CI-05   | E2E dùng credential/SQLite tạm, chạy thật và pass, không skip | `quality.yml` — step `Run frontend E2E`        | Có            |         |                           |        |
|            | CI-06   | Compose, DE contract và dbt parse pass                        | `quality.yml` — job `configuration`            | Có            |         |                           |        |
|            | CI-07   | Job bắt buộc fail thì PR không được merge                     | GitHub branch ruleset / required status checks | Chưa xác minh |         |                           |        |

## 8. Production deploy smoke

| Jira Story | Case ID   | Acceptance Criterion                   | Test / control                                       | Code | Kết quả | Commit / run / bằng chứng | Defect |
| ---------- | --------- | -------------------------------------- | ---------------------------------------------------- | ---- | ------- | ------------------------- | ------ |
|            | DEPLOY-01 | Public health trả trạng thái tốt       | `smoke_public.py` — `/api/health` `200`              | Có   |         |                           |        |
|            | DEPLOY-02 | Anonymous không đọc được staff session | `smoke_public.py` — `/staff/me` `401` trước login    | Có   |         |                           |        |
|            | DEPLOY-03 | CFO login và nhận cookie bảo mật       | `smoke_public.py` — CFO profile và cookie flags      | Có   |         |                           |        |
|            | DEPLOY-04 | KPI khớp response contract             | `smoke_public.py` — đủ field KPI                     | Có   |         |                           |        |
|            | DEPLOY-05 | CFO bị giới hạn đúng metric            | `smoke_public.py` — category ẩn; request trả `403`   | Có   |         |                           |        |
|            | DEPLOY-06 | Logout xóa cookie và session           | `smoke_public.py` — cookie bị xóa; `/staff/me` `401` | Có   |         |                           |        |

Đây là kiểm tra trên production sau deploy, không phải test Dev hay PR CI. Chỉ
đánh dấu `PASS` khi workflow CD và smoke step hoàn tất thành công; ghi commit
SHA/release cùng URL workflow run. Tài khoản CFO giám sát và dữ liệu production
chỉ được dùng theo cấu hình được phê duyệt. `DEPLOY-04` hiện chưa được phát ra
bởi script; cần đồng bộ mã case khi chỉnh smoke code.

## 9. Cách cập nhật

1. Trong mỗi PR, điền Story/AC, Case ID, kết quả và URL run vào mục **Test traceability** của PR template. Nếu fail, ghi Defect ID và link lần retest.
2. Trong matrix này, điền Jira Story thật; cập nhật test/control và cột **Code** khi coverage thay đổi hoặc có Case ID mới.
3. Chỉ điền **Kết quả** và **Commit / run / bằng chứng** của matrix khi chốt baseline đã kiểm chứng. Dùng `PASS`, `FAIL`, `BLOCKED` hoặc `SKIPPED`; `SKIPPED` không chứng minh requirement đã đạt.
