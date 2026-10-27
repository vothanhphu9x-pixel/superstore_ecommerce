# Deploy — Discovery Result

## 1. Mô hình triển khai

- FastAPI và Redis chạy trên VPS bằng `deploy/production/compose.yml`.
- Nginx trên VPS kết thúc TLS và chỉ public `/api/*` tới API loopback.
- Next.js frontend được deploy lên Vercel.
- `.github/workflows/production.yml` chạy sau `Quality Gate` thành công trên `main`;
  workflow kiểm tra đúng commit, publish API image theo digest, deploy hai tầng rồi chạy smoke.

Đây là review code ngày 2026-10-27; chưa chạy một release production trong lượt rà soát này.

## 2. Nhóm file deploy

| Đường dẫn | Vai trò |
|---|---|
| `.github/workflows/production.yml` | Điều phối build/publish API, VPS, Vercel và production smoke |
| `deploy/production/compose.yml` | API/Redis production, network, bind mounts, healthcheck và resource limits |
| `app.env.example`, `stack.env.example` | Mẫu cấu hình runtime; secret thật chỉ ở VPS |
| `images.source.env` | Image tag đầu vào để pin digest, hiện dùng Redis |
| `bin/pin-images.sh` | Pull image và ghi digest vào lockfile mới; không ghi đè file có sẵn |
| `bin/compose.sh` | Nạp stack, image lock, release env và gọi Compose |
| `bin/deploy.sh` | Kiểm tra release/image, deploy, readiness/liveness và cập nhật symlink |
| `bin/install-nginx.sh` | Render template, kiểm tra và reload Nginx |
| `nginx/*.template`, `logging.conf` | HTTP bootstrap, TLS proxy, access/error log JSON |
| `certbot/reload-nginx.sh` | Hook kiểm tra cấu hình rồi reload Nginx sau khi renew certificate |
| `tests/smoke_public.py` | Kiểm tra public website, staff CFO, KPI/RBAC và logout sau deploy |

## 3. Ranh giới vận hành

- PR Quality Gate không deploy production. CD chỉ nhận successful `push` run của repo
  hiện tại trên `main`, checkout đúng SHA rồi từ chối nếu `main` đã tiến lên commit khác.
- API image được workflow build/push bằng `GITHUB_TOKEN`, pin bằng digest và truyền cho VPS.
  Không còn yêu cầu publish thủ công mỗi release.
- Vercel project phải có production env `INTERNAL_API_URL`, `API_KEY`, `Frontend_Origin`.
- VPS giữ `/etc/superstore` secrets/config, `/opt/superstore` releases/data/logs,
  Nginx config, TLS certificate và ACME webroot.
- Nginx chỉ mở API cần thiết; `/api/health/ready`, `/docs`, `/openapi.json` và
  `/metrics` không public.
- `deploy.sh` có thể khôi phục container release trước nếu deploy command lỗi.
  Smoke fail sau khi API/Vercel deploy xong không tự rollback; phải kiểm tra workflow/log.
- Workflow chạy `sudo bash` trên script nằm trong thư mục release mà user `deploy` ghi được.
  Allowlist sudoers theo đúng path này chưa tạo ranh giới quyền mạnh; cần harden cơ chế
  đặc quyền trước khi xem VPS là production an toàn.

## 4. Kiểm tra trong lượt rà soát

| Hạng mục | Trạng thái |
|---|---|
| Workflow, Compose, scripts, templates | Đã đối chiếu code |
| VPS, DNS, TLS, GHCR pull | Chưa kiểm tra từ máy chủ |
| Vercel production env/runtime | Chưa kiểm tra |
| Deploy smoke thực tế | Chưa chạy |

Quy trình: [operation.md](operation.md). Luồng file/runtime:
[system_architecture_lineage.md](system_architecture_lineage.md). Xử lý lỗi:
[error_tracing.md](error_tracing.md).
