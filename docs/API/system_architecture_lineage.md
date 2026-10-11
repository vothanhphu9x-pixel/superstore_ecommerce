# API System Architecture & Lineage

API cung cấp dữ liệu phân tích chỉ đọc từ Snowflake. Các route `/api/staff/*` và
`/api/dashboard*` đều yêu cầu `X-API-Key`; dashboard còn yêu cầu cookie đăng nhập
staff và kiểm tra role. Redis phục vụ cache metric và rate limit login;
khi Redis lỗi, rate limit dùng bộ đếm trong tiến trình.

## 1. Kiến trúc tổng thể

```mermaid
flowchart LR
    C["Browser / Swagger / Next.js BFF"]

    subgraph API["FastAPI :8000"]
        AUTH["X-API-Key"]
        LOGIN["Staff login + rate limit"]
        SESSION["Cookie superstore_staff + role"]
        DASH["Dashboard contract + cache"]
        QUERY["Analytics query"]
    end

    USERS[(SQLite staff users)]
    LIMIT[(In-process rate-limit fallback)]
    REDIS[(Redis cache and login rate limit)]
    SF[(Snowflake Gold and Mart)]

    C --> AUTH
    AUTH --> LOGIN --> USERS
    LOGIN -->|Set-Cookie HttpOnly| C
    LOGIN --> REDIS
    LOGIN -. Redis unavailable .-> LIMIT
    AUTH --> SESSION --> USERS
    SESSION --> DASH
    DASH <--> REDIS
    DASH --> QUERY -->|ANALYTICS_READONLY| SF
    QUERY --> DASH --> C
```

`API_KEY` xác thực client nội bộ; `STAFF_JWT_SECRET` ký session staff. Tài khoản
staff được lưu ở `RAG_CHATBOT/data/internal_users.db` (Docker mount vào `/app/data`).

## 2. Data lineage

```mermaid
flowchart LR
    ODOO[(Odoo PostgreSQL)]
    CSV[Marketing CSV]
    CDC[Debezium + Kafka]
    LAKE[(MinIO Parquet)]
    RAW[(Snowflake Bronze)]
    DBT[dbt<br/>Staging → Silver → Gold → Mart]

    FACT[(fact_sales)]
    PRODUCT[(dim_product)]
    REVENUE[(mart_revenue_monthly)]

    API[FastAPI analytics]
    CLIENT[Dashboard consumer]

    ODOO --> CDC --> LAKE --> RAW --> DBT
    CSV --> LAKE
    DBT --> FACT
    DBT --> PRODUCT
    DBT --> REVENUE

    FACT -->|KPI| API
    FACT -->|Top products| API
    PRODUCT -->|Product attributes| API
    REVENUE -->|Trend / category / region| API
    API --> CLIENT
```

| API metric | Snowflake source |
|---|---|
| `kpi` | `ANALYTIC_LAYER_GOLD_LAYER.fact_sales` |
| `revenue-trend` | `ANALYTIC_LAYER_MART_LAYER.mart_revenue_monthly` |
| `by-category` | `ANALYTIC_LAYER_MART_LAYER.mart_revenue_monthly` |
| `by-region` | `ANALYTIC_LAYER_MART_LAYER.mart_revenue_monthly` |
| `top-products` | `ANALYTIC_LAYER_GOLD_LAYER.fact_sales` + `dim_product` |

## 3. Luồng xử lý một request

```mermaid
sequenceDiagram
    actor Client
    participant API as FastAPI
    participant Auth as API key + staff session
    participant Users as SQLite staff users
    participant Limit as Redis / in-process fallback
    participant Cache as Redis metric cache
    participant SF as Snowflake

    Client->>API: POST /api/staff/login + X-API-Key
    API->>Limit: Check login rate limit
    API->>Users: Verify email, password, active
    API-->>Client: Staff profile + Set-Cookie superstore_staff
    Client->>API: GET /api/dashboard/{metric} + key + cookie
    API->>Auth: Verify key, cookie, auth_version, role
    alt Key sai / session thiếu / role không được phép
        Auth-->>Client: 403 / 401 / 403
    else Đủ quyền
        API->>API: Validate month range + limit
        API->>Cache: GET request key
        alt Cache hit
            Cache-->>API: Cached payload
            API-->>Client: 200, cached=true
        else Cache miss hoặc Redis unavailable
            API->>SF: Parameterized SELECT
            SF-->>API: Rows
            API->>API: Validate metric contract
            API->>Cache: SET payload + TTL
            API-->>Client: 200, cached=false
        end
    end
```

Login có giới hạn mặc định 10 lần/phút theo IP mà API nhìn thấy. Redis là
bộ đếm chính; Redis lỗi thì dùng fallback trong tiến trình. Sau BFF Docker,
nhiều người có thể dùng chung IP container nếu `TRUST_PROXY_HEADERS=false`. Dashboard
`/api/dashboard` chỉ trả metric được role phép xem; metric
không được phép trả `403`. Redis cache lỗi thì API vẫn truy vấn Snowflake. Snowflake
lỗi hoặc metric sai contract trả `502`.

## 4. Cấu trúc module

```mermaid
flowchart TD
    APP[api/app.py<br/>app + middleware]
    HR[api/routers/health.py]
    DR[api/routers/dashboard.py]
    SR[api/routers/staff.py]
    SCHEMA[api/schemas/dashboard.py]
    STAFFSCHEMA[api/schemas/staff.py]
    VALIDATE[api/services/dashboard.py]

    AUTH[core/auth.py]
    STAFF[core/internal_auth.py]
    RATE[core/rate_limit.py]
    IP[core/client_ip.py]
    CACHE[core/cache.py]
    CONFIG[core/config.py]
    LOG[core/logging.py]
    CLI[scripts/manage_staff.py]

    QUERIES[analytics/dashboard_queries.py]
    CONTRACTS[analytics/contracts.py]
    REL[analytics/relations.py]
    CONNECTOR[analytics/connector.py]

    APP --> HR
    APP --> DR
    APP --> SR
    APP --> LOG
    DR --> AUTH
    DR --> STAFF
    DR --> CACHE
    DR --> SCHEMA
    DR --> VALIDATE
    DR --> QUERIES
    DR --> CONTRACTS
    SR --> AUTH
    SR --> STAFF
    SR --> STAFFSCHEMA
    SR --> RATE
    SR --> IP
    CLI --> STAFF
    RATE --> CACHE
    QUERIES --> REL
    QUERIES --> CONNECTOR
    AUTH --> CONFIG
    CACHE --> CONFIG
    REL --> CONFIG
    CONNECTOR --> CONFIG
```

## 5. Health và quyền truy cập

```mermaid
flowchart TD
    LIVE["/health/live"] -->|API process chạy| L200["200 healthy"]
    READY["/health/ready"] --> SF{Snowflake SELECT 1?}
    SF -->|Không| R503[503 not_ready]
    SF -->|Có| REDIS{Redis ping?}
    REDIS -->|Có| R200[200 ready + Redis healthy]
    REDIS -->|Không / disabled| R200B[200 ready + cache unavailable/disabled]
```

- Snowflake user: `SUPERSTORE_API_USER`.
- Snowflake role: `ANALYTICS_READONLY`.
- Role chỉ có `USAGE` và `SELECT` trên Gold/Mart; không có quyền ghi.
- API key được so sánh an toàn và không truyền qua query string.
- Staff password được hash bằng scrypt; JWT `HttpOnly` có hạn dùng (mặc định 8 giờ).
- Thay role, password hoặc disable user làm session cũ mất hiệu lực qua `auth_version`.
- `admin`/`analyst` thấy mọi metric; `ceo`, `cfo`, `sales` thấy các nhóm được khai báo
  trong `METRIC_CONTRACTS`. Các role khác hiện chưa có dashboard metric.
- `POST /api/staff/logout` xóa cookie; `/api/staff/me` cho biết role và metric được phép.
- SQL sử dụng parameter binding; tên database/schema/table được kiểm tra trước khi ghép.
- Kết quả bị giới hạn bởi `SNOWFLAKE_MAX_ROWS` và query timeout.

Hướng dẫn cài đặt, smoke test và quality gate: [operation.md](operation.md).
