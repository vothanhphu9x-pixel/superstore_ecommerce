# Frontend System Architecture & Lineage

Frontend là Next.js BFF cho dashboard nội bộ. Browser không giữ `API_KEY` và không kết nối
trực tiếp FastAPI hoặc Snowflake.

## 1. Kiến trúc

```mermaid
flowchart LR
    U["Browser"]

    subgraph NEXT["Next.js :3000"]
        PAGE["Dashboard page"]
        UI["Dashboard components"]
        CLIENT["dashboardService"]
        BFF["/api/internal/..."]
        GUARD["Preview guard + allowlist"]
        SERVER["internalFetch server-only"]
    end

    API["FastAPI :8000"]
    CACHE[("Redis")]
    GOLD[("Snowflake Gold")]
    MART[("Snowflake Mart")]

    U --> PAGE --> UI --> CLIENT --> BFF
    BFF --> GUARD --> SERVER
    SERVER -->|X-API-Key| API
    API --> CACHE
    API --> GOLD
    API --> MART
```

## 2. Luồng dữ liệu dashboard

```mermaid
sequenceDiagram
    actor Browser
    participant Next as Next.js BFF
    participant API as FastAPI
    participant Data as Redis / Snowflake

    Browser->>Next: GET /api/internal/dashboard/{metric}
    Next->>Next: Check preview + metric allowlist
    Next->>API: GET /api/dashboard/{metric} + X-API-Key
    API->>Data: Cache lookup hoặc Snowflake query
    Data-->>API: Metric payload
    API-->>Next: HTTP status + JSON
    Next-->>Browser: Giữ nguyên status + body
```

| Giao diện | Metric API | Giá trị business |
|---|---|---|
| KPI cards | `kpi` | Revenue, profit, orders, AOV, margin |
| Revenue trend | `revenue-trend` | Xu hướng doanh thu theo tháng |
| Category breakdown | `by-category` | Hiệu quả theo nhóm hàng |
| Region breakdown | `by-region` | Hiệu quả theo khu vực |
| Top products | `top-products` | Sản phẩm đóng góp doanh thu cao nhất |

## 3. Trách nhiệm module

```mermaid
flowchart TD
    P["app/dashboard/page.tsx<br/>runtime access guard"]
    V["DashboardView<br/>layout + date range"]
    C["Dashboard components<br/>render KPI/chart/error"]
    H["useMetric<br/>loading + fetch state"]
    A["lib/api.ts<br/>browser contract + ApiError"]
    R["route.ts<br/>allowlist + response proxy"]
    I["internalApi.ts<br/>server-only key + timeout"]

    P --> V --> C --> H --> A --> R --> I
```

## 4. Security boundary

- `API_KEY` chỉ được đọc trong Next.js server và gắn vào upstream request.
- Route BFF chỉ cho `/dashboard` và 5 metric đã khai báo.
- Browser chỉ nhận dữ liệu phân tích, không nhận Snowflake credential hoặc API key.
- `ALLOW_UNAUTHENTICATED_INTERNAL_UI=false` là mặc định; `true` chỉ dùng local preview.
- Request không cache tại Next.js; cache dữ liệu được FastAPI quản lý bằng Redis.

Luồng truy vết lỗi chi tiết: [error_tracing.md](error_tracing.md).
