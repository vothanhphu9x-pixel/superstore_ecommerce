# Frontend Discovery Result

## Identification

- Validation date: 2026-09-28
- Scope: Next.js dashboard + BFF proxy
- Status: **Implemented — local source quality gate passed**

## Implementation baseline

| Thành phần     | Hiện trạng                                         |
| -------------- | -------------------------------------------------- |
| Framework      | Next.js `16.3.6`, React `19.3.0`                   |
| Dashboard      | KPI, revenue trend, category, region, top products |
| BFF            | `/api/internal/[...path]`                          |
| Upstream       | FastAPI `/api/dashboard/*`                         |
| Authentication | Server-side `X-API-Key`                            |
| Access         | Local preview guard; chưa có staff authentication  |

## Validation results

| Gate               | Result   | Evidence                                                         |
| ------------------ | -------- | ---------------------------------------------------------------- |
| Dependency install | Verified | `npm ci` cài 288 packages, không có cảnh báo deprecated          |
| Security audit     | Verified | `npm audit --audit-level=high` trả `0 vulnerabilities`           |
| BFF allowlist      | Verified | Chỉ `/dashboard` và 5 metric được proxy                          |
| API key boundary   | Verified | `internalApi.ts` dùng `server-only`; browser không giữ key       |
| ESLint             | Verified | ESLint 10 + TypeScript + React Hooks + Next Core Web Vitals pass |
| Type-check         | Verified | `npm run typecheck` pass                                         |
| Production build   | Verified | `npm run build` pass                                             |
| Docker build       | Not Run  | Chưa xác minh image hiện tại                                     |
| End-to-end BFF     | Not Run  | Cần FastAPI và Snowflake cùng hoạt động                          |

## Known gaps

- Chưa có staff authentication; preview không được public deploy.
- `docker-compose.yml` đang bật preview cho môi trường local.
- Chưa có automated component/E2E test cho frontend.

## Completion criteria

- [x] `npm run lint`, `npm run typecheck`, `npm run build` đều pass.
- [ ] Docker frontend build và health check thành công.
- [ ] BFF gọi đủ 5 metrics và không lộ `API_KEY` ra browser.
- [ ] Staff authentication được triển khai trước khi public deploy.

Hướng dẫn chạy: [operation.md](operation.md).
Kiến trúc: [system_architecutre_lineage.md](system_architecutre_lineage.md).
Truy vết lỗi: [error_tracing.md](error_tracing.md).
