# Frontend — Discovery Result

## 1. Phạm vi

- Next.js 16 App Router; internal dashboard và staff login.
- Browser gọi cùng origin Next.js; Next Route Handler làm BFF tới FastAPI.
- Production frontend được deploy lên Vercel bởi `.github/workflows/production.yml`.
- Đây là đối chiếu code ngày 2026-10-27; lint/build/E2E chưa chạy lại trong lượt rà soát này.

## 2. Route và trách nhiệm

| Next.js route | Chức năng |
|---|---|
| `/login` | Form đăng nhập; nhận `next` path đã kiểm tra |
| `/dashboard` | Dashboard nội bộ; `proxy.ts` redirect sớm nếu thiếu cookie, server layout xác thực lại với FastAPI |
| `/api/internal/[...path]` | BFF allowlist: GET profile/dashboard, POST login/logout; kiểm tra Origin với POST |
| `/api/health` | Server-side probe tới FastAPI `/api/health/live` |

Dashboard gồm KPI, doanh thu theo tháng, category, region và top products. UI chỉ hiển
thị metric trong `StaffProfile.metrics`; backend vẫn là nơi quyết định quyền.

## 3. Luồng bảo mật

- `API_KEY` và `INTERNAL_API_URL` chỉ dùng ở Next server (`internalApi.ts` có `server-only`).
- Browser gửi cookie `superstore_staff` tới same-origin BFF; Next chuyển cookie lên FastAPI.
- FastAPI `Set-Cookie` được BFF chuyển nguyên về browser; JavaScript không đọc được `HttpOnly`.
- `proxy.ts` chỉ kiểm tra cookie có tồn tại để redirect nhanh. `(internal)/layout.tsx`
  gọi `/api/staff/me` để kiểm tra session thật trước khi render dashboard.
- POST login/logout chỉ chấp nhận đúng `Frontend_Origin`; thiếu cấu hình này ở production
  làm BFF trả lỗi cấu hình.

## 4. Kiểm tra

| Hạng mục | Trạng thái lượt rà soát |
|---|---|
| Route, env boundary, login/session flow | Đã đối chiếu code |
| `npm ci`, lint, typecheck, build | Chưa chạy lại |
| Playwright E2E | Chưa chạy lại |
| Production/Vercel runtime | Chưa kiểm tra |

Không kế thừa kết quả cũ làm bằng chứng cho phiên bản hiện tại. Cách chạy:
[operation.md](operation.md). Kiến trúc: [system_architecture_lineage.md](system_architecture_lineage.md).
Khoanh vùng lỗi: [error_tracing.md](error_tracing.md).
