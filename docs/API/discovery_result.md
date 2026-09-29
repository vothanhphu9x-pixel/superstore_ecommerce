# API Discovery Result

## Identification

- Validation date: 2026-09-24
- Scope: STEP 5 — FastAPI analytics API
- Status: **Verified locally**

## API contract

| Capability | Source | Result |
|---|---|---|
| KPI summary | Snowflake Gold `fact_sales` | Verified |
| Revenue trend/category/region | Snowflake Mart `mart_revenue_monthly` | Verified |
| Top products | Gold `fact_sales` + `dim_product` | Verified |
| Authentication | Header `X-API-Key` | Verified |
| Cache | Redis, fail-open | Verified |
| Readiness | Snowflake bắt buộc, Redis báo riêng | Verified |

API chỉ đọc dữ liệu bằng `SUPERSTORE_API_USER` và role `ANALYTICS_READONLY`.

## Validation results

| Gate | Result | Evidence |
|---|---|---|
| Python syntax | Pass | `make python-syntax` |
| Backend tests | Pass | 15 tests |
| Docker build | Pass | Image `superstore-api:step5-check` |
| Liveness | Pass | `/health/live` trả `200` |
| Readiness | Pass | `/health/ready` trả `200` |
| API authentication | Pass | Thiếu API key trả `403` |
| Dashboard metrics | Pass | 5/5 endpoints trả `200` và đúng contract |
| Docker Compose config | Pass | `docker compose config --quiet` |
| Repository hygiene | Pass | Không có secret hoặc runtime data được stage |

## Current boundaries

- Không ghi dữ liệu vào Snowflake hoặc Odoo.
- Không dùng cookie hoặc customer session; API key chỉ dành cho internal client.
- Redis lỗi không làm dừng API; Snowflake lỗi làm readiness trả `503` và metric trả `502`.
- GitHub Quality Gate cài `requirements-dev.txt`; Docker production chỉ cài `requirements.txt`.

Hướng dẫn chạy và kiểm tra: [operation.md](operation.md).
