# Frontend System Architecture & Lineage

Frontend là Next.js BFF cho dashboard nội bộ. Browser giữ cookie `HttpOnly`
`superstore_staff`; `API_KEY` chỉ nằm ở Next.js server. Đã có trang login,
redirect khi chưa đăng nhập, xác thực session phía server và logout.

## 1. Kiến trúc

```mermaid
flowchart LR
    U["Browser"]

    subgraph NEXT["Next.js :3000"]
        PROXY["proxy.ts: thiếu cookie → /login"]
        LOGIN["/login + LoginForm"]
        LAYOUT["Internal layout: GET /staff/me"]
        UI["Dashboard theo role + StaffBar logout"]
        CLIENT["dashboardService + staffService"]
        BFF["/api/internal/..."]
        GUARD["Method/path allowlist + POST Origin"]
        SERVER["internalFetch server-only + API key"]
    end

    API["FastAPI :8000<br/>API key + staff session + role"]
    STAFF[(SQLite staff DB)]
    CACHE[(Redis)]
    GOLD[(Snowflake Gold)]
    MART[(Snowflake Mart)]

    U --> PROXY
    PROXY -->|"chưa có cookie"| LOGIN --> CLIENT
    PROXY -->|"có cookie"| LAYOUT --> UI --> CLIENT --> BFF
    LAYOUT --> SERVER
    U -->|"staff cookie"| BFF
    BFF --> GUARD --> SERVER
    SERVER -->|"X-API-Key + cookie"| API
    API --> STAFF
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

    Browser->>Next: GET /dashboard khi thiếu cookie
    Next-->>Browser: Redirect /login?next=/dashboard
    Browser->>Next: POST /api/internal/staff/login
    Next->>Next: Check method/path + Origin
    Next->>API: POST /api/staff/login + X-API-Key
    API-->>Next: Staff profile + Set-Cookie
    Next-->>Browser: Giữ Set-Cookie cho localhost:3000
    Browser->>Next: GET /dashboard + cookie
    Next->>API: GET /api/staff/me + key + cookie
    API-->>Next: Staff profile + allowed metrics
    Browser->>Next: GET /api/internal/dashboard/{metric} + cookie
    Next->>API: GET /api/dashboard/{metric} + key + cookie
    API->>API: Verify staff session + role
    API->>Data: Cache lookup hoặc Snowflake query
    Data-->>API: Metric payload
    API-->>Next: HTTP status + JSON
    Next-->>Browser: Giữ status + body
```

`LoginForm` gọi `staffService.login`; layout server gọi trực tiếp `/api/staff/me`
qua `internalFetch` (không dùng `staffService.me`); `StaffBar` gọi
`staffService.logout`. `proxy.ts` chỉ kiểm tra cookie
có tồn tại để redirect sớm, **không** tự xác thực chữ ký/role. Dashboard chỉ
render metric trong `StaffProfile.metrics`; FastAPI vẫn kiểm tra quyền từng request.

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
    X["proxy.ts<br/>redirect khi thiếu cookie"]
    L["app/login/page.tsx + LoginForm"]
    S["app/(internal)/layout.tsx<br/>xác thực /staff/me"]
    P["app/(internal)/dashboard/page.tsx"]
    V["DashboardView<br/>layout + date range"]
    B["StaffBar + StaffSessionProvider"]
    C["Dashboard components<br/>render KPI/chart/error"]
    H["useMetric<br/>loading + fetch state"]
    A["lib/api.ts<br/>dashboardService + staffService + ApiError"]
    R["route.ts<br/>method/path + Origin + cookie proxy"]
    I["internalApi.ts<br/>server-only key + timeout 15s"]

    X --> L --> A
    X --> S --> P --> V --> C --> H --> A --> R --> I
    S --> B --> A
```

## 4. Security boundary

- `API_KEY` chỉ được đọc trong Next.js server và gắn vào upstream request.
- BFF cho `GET /staff/me`, `GET /dashboard*`, `POST /staff/login` và
  `POST /staff/logout`; FastAPI từ chối metric lạ. `dashboard/*` hiện được
  forward theo prefix, chưa có allowlist cố định năm metric ở BFF.
- BFF chuyển cookie tới FastAPI và chuyển `Set-Cookie` của login/logout về browser.
  Browser không đọc được giá trị cookie `HttpOnly` bằng JavaScript.
- POST có `Origin` khác origin của Next.js bị trả `403`; POST không có Origin
  được phép để hỗ trợ curl/server-side client.
- Không còn preview guard hay phụ thuộc `ALLOW_UNAUTHENTICATED_INTERNAL_UI`.
  `.env.example` vẫn chứa cờ cũ nhưng code không đọc nó.
- POST từ Origin khác `Frontend_Origin` bị chặn; request không có Origin được
  chấp nhận cho CLI/server-side client. Cấu hình phải đúng origin browser thực tế.
- Next.js không cache request; FastAPI dùng Redis cho metric và rate limit login,
  fallback trong tiến trình nếu Redis lỗi.

Luồng truy vết lỗi chi tiết: [error_tracing.md](error_tracing.md).
