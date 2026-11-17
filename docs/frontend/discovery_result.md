# Frontend — Discovery Result

## Trạng thái

- **Verified:** đã chạy và có bằng chứng.
- **Failed:** đã chạy nhưng không đạt.
- **Blocked:** chưa thể chạy do thiếu dịch vụ, quyền hoặc kết nối.
- **Not Run:** chưa có kết quả thực tế; đọc code không được tính là pass.

## Thông tin lần kiểm tra

- Ngày cập nhật: **2026-11-14**; môi trường: Mac local.
- Phạm vi: Next.js 16, login, dashboard và BFF tới FastAPI.
- Kết luận: **lint, type-check và production build đạt**; E2E local cần Docker/Redis nên chưa chạy trong lượt này.

## Thành phần cần kiểm soát

```text
Browser → /login, /dashboard
        → /api/internal/[...path] (Next BFF) → FastAPI staff/dashboard
        → /api/health                  → FastAPI /api/health/live
```

`proxy.ts` redirect nhanh khi thiếu cookie; layout nội bộ hỏi FastAPI `/api/staff/me` để xác minh session. BFF kiểm tra allowlist method/path và Origin cho POST, gắn API key ở server, chuyển `HttpOnly` cookie. Dashboard chỉ hiển thị metric trong staff profile; FastAPI vẫn quyết định quyền truy cập.

Dashboard hiển thị KPI, revenue trend, category, region và top products khi role được phép xem.

## Checklist kết quả

| Gate | Kỳ vọng | Kết quả | Bằng chứng / lần chạy |
|---|---|---|---|
| FE-01 — Lint | ESLint không có lỗi | Verified | `npm run lint`, 2026-11-14 |
| FE-02 — Type-check | TypeScript không có lỗi | Verified | `npm run typecheck`, 2026-11-14 |
| FE-03 — Build | Next.js production build tạo được route | Verified | `npm run build`; có `/login`, `/dashboard`, `/api/internal/[...path]`, 2026-11-14 |
| FE-04 — E2E local | Login/logout, sai mật khẩu và chặn cross-site POST đạt | Blocked | Docker daemon local không kết nối được; chưa chạy Playwright trong lượt này |
| FE-05 — CI | Frontend job và Playwright trên PR đạt | Not Run | Cần URL/SHA của Quality Gate run mới |
| FE-06 — Vercel | Public website và BFF production hoạt động | Not Run | Cần production smoke run mới; xem [Deploy Discovery](../deploy/discovery_result.md) |

Build thành công chỉ kiểm tra code/build-time; không thay thế E2E hoặc production smoke.

## Tiêu chí hoàn tất

- [x] Lint, type-check và build local đạt.
- [ ] Bật stack rồi chạy E2E local đạt.
- [ ] Ghi CI run của commit được deploy.
- [ ] Ghi production smoke run sau deploy.

## Tài liệu liên quan

- Lệnh chạy: [Frontend Operations](operation.md) và [Test Operations](../tests/operation.md).
- Luồng và bảo mật: [Frontend Architecture](system_architecture_lineage.md).
