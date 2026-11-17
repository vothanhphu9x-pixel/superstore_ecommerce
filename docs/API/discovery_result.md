# API — Discovery Result

## Trạng thái

- **Verified:** đã chạy và có bằng chứng.
- **Failed:** đã chạy nhưng không đạt.
- **Blocked:** chưa thể chạy do thiếu dịch vụ, quyền hoặc kết nối.
- **Not Run:** chưa có kết quả thực tế; đọc code không được tính là pass.

## Thông tin lần kiểm tra

- Ngày cập nhật: **2026-11-14**; môi trường: Mac local.
- Phạm vi: FastAPI, staff authentication/RBAC, dashboard, Redis và Snowflake.
- Kết luận: **17 test độc lập đạt**; bộ pytest đầy đủ chưa đạt vì các ca login trả `503` khi Redis local không khả dụng. Chưa kiểm tra Snowflake thật trong lượt này.

## Thành phần cần kiểm soát

```text
Browser/Next BFF → API key → staff cookie + RBAC → dashboard
                                                 ├─ Redis: rate limit/cache
                                                 └─ Snowflake: Gold/Mart, chỉ đọc
```

Route chính: `/api/staff/login|me|logout`, `/api/dashboard`, `/api/dashboard/{metric}`. `/health/live` kiểm tra tiến trình; `/health/ready` kiểm tra Snowflake/Redis; `/api/health/ready` kiểm tra staff store/Redis. `/metrics` phục vụ Prometheus, không public qua Nginx production.

`API_KEY` xác thực BFF; `STAFF_JWT_SECRET` ký staff session. Hai secret có chức năng khác nhau. SQLite staff nằm trong `RAG_CHATBOT/data/` khi chạy local hoặc mount `/app/data` trong container.

Năm metric hiện có: `kpi`, `revenue-trend`, `by-category`, `by-region`, `top-products`. Query đọc Gold `fact_sales`/`dim_product` và Mart `mart_revenue_monthly`; response phải qua data contract trước khi trả về.

## Checklist kết quả

| Gate | Kỳ vọng | Kết quả | Bằng chứng / lần chạy |
|---|---|---|---|
| API-01 — Auth core | Hash, session và RBAC unit tests đạt | Verified | `pytest` nhóm auth core/contracts/validation/observability: **17 passed**, 2026-11-14 |
| API-02 — Toàn bộ pytest | Mọi test Auth, Dashboard, Integration, Operations đạt | Failed | **25 passed, 13 failed**; login trả `503` khi Redis local không chạy, 2026-11-14 |
| API-03 — Redis | Rate limit dùng Redis và login trả trạng thái mong đợi | Blocked | Docker daemon local không kết nối được; cần bật Redis rồi chạy lại API-02 |
| API-04 — Snowflake | Readiness và dashboard đọc được dữ liệu thật bằng role chỉ đọc | Not Run | Chưa thử kết nối/query trong lượt này |
| API-05 — Docker runtime | Container API lên và `/api/health/live` trả `200` | Blocked | Docker daemon local không khả dụng |
| API-06 — Production auth | Login, cookie, RBAC và KPI qua public BFF đạt | Not Run | Cần production smoke run mới; xem [Deploy Discovery](../deploy/discovery_result.md) |

Khi chạy lại, ghi ngày, kết quả và bằng chứng mới cho từng gate. Test chạy với SQLite tạm/mock Snowflake **không chứng minh** Snowflake production hoạt động.

## Tiêu chí hoàn tất

- [x] Unit tests độc lập với Redis/Snowflake đạt.
- [ ] Khởi động Redis, chạy lại toàn bộ backend pytest và đạt.
- [ ] Xác minh readiness/query Snowflake ở môi trường đã cấu hình.
- [ ] Xác minh API production bằng smoke run mới.

## Tài liệu liên quan

- Lệnh chạy: [API Operations](operation.md) và [Test Operations](../tests/operation.md).
- Luồng hệ thống: [API Architecture](system_architecture_lineage.md).
