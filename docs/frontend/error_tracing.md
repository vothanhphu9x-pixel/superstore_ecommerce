# Truy vết lỗi Client → Next.js BFF → FastAPI -> Redis/Snowflake

## 1. Luồng request

```mermaid
flowchart LR
    C[Browser] -->|/api/internal/dashboard/...| N[Next.js BFF]
    N -->|INTERNAL_API_URL<br/>X-API-Key| F[FastAPI]
    F --> R[(Redis cache)]
    F --> S[(Snowflake)]

    C -. lỗi mạng / hiển thị .-> C
    N -. allowlist / env / kết nối .-> N
    F -. auth / validation / query .-> F
    R -. cache lỗi: API vẫn chạy .-> R
    S -. query lỗi: metric 502 .-> S
```

Next.js chỉ proxy `/dashboard` và 5 metric được allowlist. BFF giữ `API_KEY` ở server,
gọi FastAPI rồi trả nguyên HTTP status và response body về browser.

## 2. Error class và cách lỗi được truyền

```mermaid
flowchart LR
    F1[Browser fetch lỗi hoặc response không OK] --> A[ApiError]
    A -->|status + message| UI[useMetric → giao diện]

    F2[URL / API_KEY / internal path sai] --> C[InternalApiConfigurationError]
    C -->|Next.js catch| R503[503 generic cho browser]
    C -->|chi tiết thật| NL[Next.js server log]

    F3[Payload Snowflake sai contract] --> V[ContractViolation]
    V -->|FastAPI catch| R502A[502 Data contract failed]

    F4[Số dòng vượt SNOWFLAKE_MAX_ROWS] --> Q[QueryResultTooLarge]
    Q -->|FastAPI catch chung| R502B[502 Unable to load metric]

    F5[Auth / metric / query parameter sai] --> H[HTTPException]
    H --> RX[403 / 404 / 422 / 503]
```

`InternalApiConfigurationError`, `ContractViolation` và lỗi Snowflake không trả stack trace
cho browser. Muốn thấy nguyên nhân gốc phải xem log đúng tầng.

## 3. Xác định lỗi theo response

```mermaid
flowchart TD
    E[Request lỗi] --> S{HTTP status}
    S -->|0 / Failed to fetch| C[Browser không tới được Next.js]
    S -->|403| A[API key Next.js và FastAPI không khớp]
    S -->|404| P[Path/metric không nằm trong allowlist]
    S -->|422| V[month_from, month_to hoặc limit không hợp lệ]
    S -->|503| G[BFF bị khóa, thiếu env hoặc Snowflake chưa ready]
    S -->|502| B[Next.js không tới FastAPI hoặc FastAPI query/contract lỗi]
```

| Dấu hiệu                               | Error class/nhóm lỗi             | Kiểm tra đầu tiên                                         | Vị trí lỗi thường gặp                    |
| -------------------------------------- | -------------------------------- | --------------------------------------------------------- | ---------------------------------------- |
| Status `0`, `Failed to fetch`          | `ApiError`                       | Browser Network và Next.js có chạy không                  | Client → Next.js                         |
| `404 Internal API path is not allowed` | Next.js allowlist                | URL metric và `ALLOWED_METRICS`                           | Next.js route proxy                      |
| `403 Invalid or missing API key`       | `HTTPException`                  | `API_KEY` của Next.js và FastAPI phải giống nhau          | Next.js → FastAPI auth                   |
| `422`                                  | `HTTPException`                  | `month_from <= month_to`, dạng `YYYYMM01`, `limit=1..100` | FastAPI validation                       |
| `503 dashboard is locked`              | Next.js access guard             | `ALLOW_UNAUTHENTICATED_INTERNAL_UI=true` khi chạy preview | Next.js BFF                              |
| `503 proxy is not configured`          | `InternalApiConfigurationError`  | `INTERNAL_API_URL`, `API_KEY`                             | Next.js server env                       |
| `503 /health/ready`                    | Snowflake exception              | Chi tiết `services.snowflake`                             | FastAPI → Snowflake                      |
| `502 Cannot connect to backend`        | Fetch/timeout exception          | FastAPI có chạy, URL/port/DNS đúng, timeout 15 giây       | Next.js → FastAPI                        |
| `502 Unable to load metric`            | `QueryResultTooLarge` hoặc query | Snowflake role/schema/table/query, `SNOWFLAKE_MAX_ROWS`   | FastAPI analytics                        |
| `502 Data contract failed`             | `ContractViolation`              | Tên và kiểu cột query trả về                              | FastAPI contract                         |
| Redis unavailable                      | Redis exception                  | `/health/ready.services.redis`                            | Không chặn API; request chạy không cache |

## 4. Thứ tự kiểm tra

```mermaid
flowchart TD
    A[1. Browser Network<br/>đọc status + detail] --> B[2. Kiểm tra Next.js log<br/>tìm internal-proxy]
    B --> C[3. FastAPI /health/live]
    C --> D[4. FastAPI /health/ready]
    D --> E[5. Gọi trực tiếp metric FastAPI]
    E --> F[6. Kiểm tra Snowflake / Redis nếu cần]
```

```bash
# FastAPI process
curl -i http://localhost:8000/health/live
curl -i http://localhost:8000/health/ready

# Log khi chạy bằng Docker Compose
cd data_platform
docker compose logs --tail=100 frontend api redis

# Gọi FastAPI trực tiếp, bỏ qua Next.js BFF
curl -i \
  -H "X-API-Key: $API_KEY" \
  "http://localhost:8000/api/dashboard/kpi?month_from=20230101&month_to=20231201"
```

## 5. Cách khoanh vùng nhanh

- Gọi FastAPI trực tiếp **thành công**, nhưng qua `/api/internal/...` lỗi: kiểm tra Next.js BFF.
- `/health/live` lỗi: FastAPI chưa chạy hoặc sai port.
- `/health/live` đạt nhưng `/health/ready` lỗi: kiểm tra Snowflake.
- Readiness đạt nhưng metric lỗi `502`: kiểm tra query, schema và data contract.
- Response đúng nhưng giao diện lỗi: kiểm tra browser console và component render.

Không ghi `API_KEY`, Snowflake password hoặc toàn bộ `.env` vào log/ticket.
