# API System Architecture & Lineage

API cung cấp dữ liệu phân tích read-only từ Snowflake cho frontend và internal client.
Mọi dashboard endpoint yêu cầu `X-API-Key`; Redis chỉ tăng tốc và không phải nguồn dữ liệu.

## 1. Kiến trúc tổng thể

```mermaid
flowchart LR
    C[Frontend / Swagger / Internal client]

    subgraph API[FastAPI :8000]
        MW[CORS + response-time middleware]
        AUTH[X-API-Key authentication]
        ROUTER[Dashboard router]
        CONTRACT[Request + response contract]
        QUERY[Analytics query service]
    end

    REDIS[(Redis cache)]
    SF[(Snowflake<br/>Gold + Mart)]

    C -->|HTTP GET| MW
    MW --> AUTH
    AUTH -->|403 nếu key sai| C
    AUTH --> ROUTER
    ROUTER --> CONTRACT
    CONTRACT -->|cache key| REDIS
    REDIS -->|cache hit| CONTRACT
    CONTRACT -->|cache miss| QUERY
    QUERY -->|ANALYTICS_READONLY| SF
    SF --> QUERY
    QUERY --> CONTRACT
    CONTRACT -->|cache TTL| REDIS
    CONTRACT -->|JSON + cached flag| C
```

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
    participant Auth as API-key auth
    participant Cache as Redis
    participant SF as Snowflake

    Client->>API: GET /api/dashboard/{metric}
    API->>Auth: Verify X-API-Key
    alt Key thiếu hoặc sai
        Auth-->>Client: 403 Forbidden
    else Key hợp lệ
        API->>API: Validate month range + limit
        API->>Cache: GET hashed request key
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

Redis hoạt động theo cơ chế fail-open: nếu Redis lỗi, API vẫn truy vấn Snowflake. Snowflake
là dependency bắt buộc; lỗi kết nối hoặc contract trả `502` cho metric.

## 4. Cấu trúc module

```mermaid
flowchart TD
    APP[api/app.py<br/>app + middleware]
    HR[api/routers/health.py]
    DR[api/routers/dashboard.py]
    SCHEMA[api/schemas/dashboard.py]
    VALIDATE[api/services/dashboard.py]

    AUTH[core/auth.py]
    CACHE[core/cache.py]
    CONFIG[core/config.py]
    LOG[core/logging.py]

    QUERIES[analytics/dashboard_queries.py]
    CONTRACTS[analytics/contracts.py]
    REL[analytics/relations.py]
    CONNECTOR[analytics/connector.py]

    APP --> HR
    APP --> DR
    APP --> LOG
    DR --> AUTH
    DR --> CACHE
    DR --> SCHEMA
    DR --> VALIDATE
    DR --> QUERIES
    DR --> CONTRACTS
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
    LIVE[/health/live/] -->|API process chạy| L200[200 healthy]
    READY[/health/ready/] --> SF{Snowflake SELECT 1?}
    SF -->|Không| R503[503 not_ready]
    SF -->|Có| REDIS{Redis ping?}
    REDIS -->|Có| R200[200 ready + Redis healthy]
    REDIS -->|Không / disabled| R200B[200 ready + cache unavailable/disabled]
```

- Snowflake user: `SUPERSTORE_API_USER`.
- Snowflake role: `ANALYTICS_READONLY`.
- Role chỉ có `USAGE` và `SELECT` trên Gold/Mart; không có quyền ghi.
- API key được so sánh an toàn và không truyền qua query string.
- SQL sử dụng parameter binding; tên database/schema/table được kiểm tra trước khi ghép.
- Kết quả bị giới hạn bởi `SNOWFLAKE_MAX_ROWS` và query timeout.

Hướng dẫn cài đặt, smoke test và quality gate: [operation.md](operation.md).
