# Frontend Discovery Result

## Identification

- Review date: 2026-10-06
- Scope: Next.js dashboard, BFF proxy và staff login/session
- Status: **Login UI và dashboard theo role đã có; runtime E2E chưa kiểm lại**

## Implementation baseline

| Thành phần     | Hiện trạng                                         |
| -------------- | -------------------------------------------------- |
| Framework      | Next.js `16.3.6`, React `19.3.0`                   |
| Dashboard      | KPI, revenue trend, category, region, top products |
| BFF            | `/api/internal/[...path]`: dashboard + staff routes |
| Upstream       | FastAPI `/api/dashboard/*`, `/api/staff/*`          |
| Authentication | Next server gắn `X-API-Key`; chuyển staff cookie `HttpOnly` và `Set-Cookie` |
| Access         | `proxy.ts` redirect khi thiếu cookie; server layout xác thực `/staff/me` |
| Staff UI       | `/login`, `LoginForm`, `StaffBar` logout; chỉ render metric được role cho phép |

## Validation results

| Gate               | Result   | Evidence                                                         |
| ------------------ | -------- | ---------------------------------------------------------------- |
| Dependency install | Pass | `npm ci` (2026-10-06) |
| Security audit     | Pass | `npm audit --audit-level=high`: 0 lỗ hổng |
| BFF routes         | Code review | GET `/staff/me`, `/dashboard*`; POST `/staff/login`, `/staff/logout`; POST sai Origin bị chặn |
| Cookie/key boundary | Code review | `internalApi.ts` là `server-only`; BFF chuyển cookie và `Set-Cookie` |
| Lint/type-check/build | Pass | `npm run check` (2026-10-06) |
| Docker build       | Pass | `docker build -t superstore-frontend:audit-fix .` (2026-10-06) |
| End-to-end BFF     | Chưa kiểm lại | Cần login qua BFF, kiểm tra `/staff/me`, redirect và metric |
| Docker Compose config | Pass | `docker compose --profile app config --quiet` (2026-10-06) |

## Known gaps

- `RAG_CHATBOT/frontend/.env.example` còn cờ preview cũ
  `ALLOW_UNAUTHENTICATED_INTERNAL_UI`, trong khi code không đọc cờ này; ví dụ
  chưa khai báo `Frontend_Origin` mà BFF đang dùng để kiểm tra POST Origin.
- BFF forward mọi `dashboard/*` theo prefix; FastAPI trả `404` cho metric lạ.
- Compose nạp `frontend/.env.local` qua `env_file`; không nội suy hai biến BFF từ
  `data_platform/.env` hay bắt buộc export vào shell.
- Next-specific ESLint plugin đã bỏ do phụ thuộc `braces` chưa có bản vá;
  ESLint core, TypeScript và React Hooks vẫn chạy.
- Chưa có automated component/E2E test cho frontend.

## Completion criteria

- [x] `npm ci`, `npm audit --audit-level=high`, `npm run check` pass.
- [x] Docker frontend image build thành công; chưa xác nhận container health/runtime.
- [x] Trang Next có login/logout, redirect và chỉ render metric theo role.
- [ ] BFF login, gửi cookie, gọi `/staff/me` và metric theo role được xác minh E2E.

Hướng dẫn chạy: [operation.md](operation.md).
Kiến trúc: [system_architecutre_lineage.md](system_architecutre_lineage.md).
Truy vết lỗi: [error_tracing.md](error_tracing.md).
