# Deploy — Discovery Result

## Trạng thái

- **Verified:** đã chạy và có bằng chứng.
- **Failed:** đã chạy nhưng không đạt.
- **Blocked:** chưa thể chạy do bước trước, quyền, dịch vụ hoặc kết nối.
- **Not Run:** chưa có kết quả thực tế trong lượt kiểm tra ghi ở bảng.

## Thông tin lần kiểm tra

- Ngày cập nhật: **2026-11-14**; phạm vi: PR CI → API image/GHCR → VPS → Vercel → production smoke.
- Kết luận: log backup ngày **2026-11-13** cho thấy VPS có release hiện hành và API image pin bằng digest. Lần production smoke gần nhất được cung cấp (**2026-10-28**) dừng ở KPI `502`; chưa có URL/run mới chứng minh toàn bộ luồng CD đã đạt.
- Kết quả backup và restore được theo dõi riêng trong [Backup Discovery Result](backup/discovery_result.md).

## Thành phần cần kiểm soát

```text
Quality Gate trên main → production.yml kiểm tra đúng SHA
  → build/push API image theo digest → deploy.sh + Compose + Nginx trên VPS
  → Vercel deploy Next.js → smoke_public.py → ghi kết quả release
VPS systemd timer → S3 backup → restore drill (nhánh vận hành riêng)
```

| Nhóm file | Vai trò |
|---|---|
| `.github/workflows/quality.yml`, `production.yml` | CI trước CD; CD chỉ nhận successful `push` trên `main` của đúng repository/SHA |
| `deploy/production/compose.yml`, `bin/*.sh` | Runtime API/Redis, pin image, kiểm tra release, deploy và cập nhật `current`/`previous` |
| `nginx/`, `certbot/` | TLS proxy, access/error logs và renew hook |
| `deploy/production/tests/smoke_public.py` | Public health, login CFO/cookie, KPI, RBAC và logout |
| `deploy/production/backup/` | Backup mã hóa S3 và restore drill |

VPS giữ secret trong `/etc/superstore`, release/data/log trong `/opt/superstore`; Next.js chạy trên Vercel. Nginx không public `/metrics`, `/docs`, `/openapi.json` hoặc `/api/health/ready`.

## Checklist kết quả

| Gate | Kỳ vọng | Kết quả | Bằng chứng / lần chạy |
|---|---|---|---|
| DEP-01 — CI/SHA | Quality Gate pass trên `main`; CD checkout đúng commit đã test | Not Run | Cần URL Quality Gate và production workflow cùng SHA cho release mới |
| DEP-02 — API image/VPS | GHCR digest chạy trên VPS và release hiện hành hợp lệ | Verified | Backup journal: `Current release verified` và backup hoàn tất; `backup.sh` kiểm tra image digest trước upload, 2026-11-13 |
| DEP-03 — HTTPS/Nginx | Public health qua HTTPS; cổng API không public trực tiếp | Not Run | Chưa có smoke/network check mới trong lượt này |
| DEP-04 — Vercel | Next.js production là commit tương ứng với API | Not Run | Cần deployment URL/commit của Vercel cho release mới |
| DEP-05 — Smoke | `DEPLOY-01`–`DEPLOY-06` đều pass | Failed | Lần log gần nhất được cung cấp 2026-10-28: KPI trả `502` tại `DEPLOY-04`; cần chạy lại để biết trạng thái hiện tại |
| DEP-06 — Recovery | Khi deploy lỗi, release trước hoạt động lại; smoke fail được xử lý có kiểm soát | Not Run | Chưa diễn tập; smoke fail sau deploy không tự rollback đồng thời VPS và Vercel |
| DEP-07 — Backup | S3 backup và restore local xác minh được | Verified | [Backup Discovery Result](backup/discovery_result.md), log 2026-11-13 và local check 2026-11-14 |

Đây là **kết quả theo bằng chứng gần nhất**, không phải khẳng định production đang ở trạng thái đó tại thời điểm đọc. Chỉ cập nhật gate khi có run URL/SHA hoặc log mới. Allowlist `sudo` gọi script trong release do user `deploy` ghi được; cần rà soát ranh giới đặc quyền trước khi coi đó là kiểm soát quyền mạnh.

## Tiêu chí hoàn tất

- [x] Có release đang chạy trên VPS với API image pin digest tại lần backup được ghi nhận.
- [ ] Có CI/CD run cùng SHA và Vercel deployment tương ứng.
- [ ] Production smoke mới đạt đủ sáu case.
- [ ] Diễn tập recovery/rollback cho cả VPS và Vercel.

## Tài liệu liên quan

- Cấu hình, release và recovery: [Deploy Operations](operation.md).
- Cấu trúc runtime: [Deploy Architecture](system_architecture_lineage.md).
- Truy vết lỗi: [Error Tracing](error_tracing.md).
- Checklist backup: [Backup Discovery Result](backup/discovery_result.md).
