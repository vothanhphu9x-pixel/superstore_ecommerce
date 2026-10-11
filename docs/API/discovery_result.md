# API Discovery Result

## Identification

- Review date: 2026-10-07
- Scope: FastAPI analytics API, staff session và dashboard theo role
- Status: **Đã triển khai; backend test suite pass**

## API contract

| Capability | Source | Result |
|---|---|---|
| KPI summary | Snowflake Gold `fact_sales` | Có query + contract; chưa chạy lại với session mới |
| Revenue trend/category/region | Snowflake Mart `mart_revenue_monthly` | Có query + contract; chưa chạy lại với session mới |
| Top products | Gold `fact_sales` + `dim_product` | Có query + contract; chưa chạy lại với session mới |
| API authentication | Header `X-API-Key` cho `/api/staff/*` và `/api/dashboard*` | Sai/thiếu key trả `403`; key chưa cấu hình trả `503` |
| Staff login/session | SQLite + scrypt; JWT cookie `superstore_staff` | Login, me, logout đã có trong code |
| Dashboard authorization | API key + staff cookie + metric groups theo role | `GET /api/dashboard` chỉ trả metric được phép |
| Login rate limit | Redis theo IP, mặc định 10 lần/phút; fallback trong tiến trình | Có trong code; chưa kiểm lại runtime |
| Cache | Redis metric cache, lỗi thì truy vấn Snowflake trực tiếp | Có trong code; chưa kiểm lại runtime |
| Readiness | Snowflake bắt buộc; Redis báo trạng thái riêng | Có trong code; chưa kiểm lại runtime |

API chỉ đọc dữ liệu bằng `SUPERSTORE_API_USER` và role `ANALYTICS_READONLY`.

## Validation results

| Gate | Result | Evidence |
|---|---|---|
| Python syntax | Pass | `compileall -q analytics api core scripts` (2026-10-06) |
| Backend tests | Pass | `pytest -q`: 30 pass, 1 deprecation warning (2026-10-07); auth route test không gọi Snowflake thật |
| Docker API build | Chưa kiểm lại | Không dùng image cũ làm bằng chứng cho code hiện tại |
| API runtime + 5 metric | Chưa kiểm lại | Cần smoke test với key + staff cookie trên môi trường đang chạy |
| Docker Compose config | Pass | `docker compose --profile app config --quiet` (2026-10-06) |
| Repository hygiene | Chưa kiểm lại | Kiểm staged files trước commit |

## Current boundaries

- Không ghi dữ liệu vào Snowflake hoặc Odoo.
- Staff session dùng cookie; đây không phải customer session. `API_KEY` vẫn là secret
  giữa client nội bộ/Next.js BFF và FastAPI.
- Redis cache lỗi không làm dừng metric; Snowflake lỗi làm readiness trả `503` và metric trả `502`.
- GitHub Quality Gate cài `requirements-dev.txt`; Docker production chỉ cài `requirements.txt`.
- `tests/test_api_auth.py` kiểm tra API key + staff cookie, login/logout, role
  và session hết hiệu lực bằng SQLite tạm; nhánh `429` dùng mock rate limit.
  Các test này chưa thay thế smoke test runtime.
- Với `TRUST_PROXY_HEADERS=false`, API nhận IP của BFF/container làm IP login;
  nhiều nhân viên có thể chia sẻ cùng một bucket rate limit.
- CLI staff nằm ở `RAG_CHATBOT/scripts/manage_staff.py`; database SQLite được ignore bởi Git
  và mount tại `/app/data` khi chạy Docker.

Hướng dẫn chạy và kiểm tra: [operation.md](operation.md).
