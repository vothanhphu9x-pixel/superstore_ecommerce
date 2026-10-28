# Deploy Operations

## 1. Cách release hoạt động

`.github/workflows/production.yml` chạy sau khi `Quality Gate` thành công với một
commit được push lên `main` của repository hiện tại. Workflow xác nhận đúng SHA đã
test, tự build/push API image lên GHCR theo digest, deploy API lên VPS, deploy
Next.js lên Vercel, rồi chạy production smoke.

Không publish API image thủ công cho mỗi lần release. VPS/Nginx/TLS và các file
secret là cấu hình khởi tạo một lần; GitHub Actions xử lý các release tiếp theo.

## 2. Cấu hình GitHub Environment `production`

Trong GitHub → Settings → Environments → `production`, khai báo:

| Loại | Tên | Giá trị |
|---|---|---|
| Variable | `VPS_HOST` | Hostname hoặc IPv4 VPS |
| Variable | `VPS_PORT` | Cổng SSH, thường là `22` |
| Variable | `VPS_USER` | User deploy, thường là `deploy` |
| Variable | `VERCEL_ORG_ID` | `orgId` của project Vercel |
| Variable | `VERCEL_PROJECT_ID` | `projectId` của frontend Vercel |
| Variable | `FRONTEND_ORIGIN` | HTTPS origin frontend, không thêm path |
| Secret | `VPS_SSH_KEY` | Private key riêng cho GitHub Actions |
| Secret | `VPS_KNOWN_HOSTS` | Host key VPS đã xác minh |
| Secret | `VERCEL_TOKEN` | Token deploy Vercel |
| Secret | `MONITOR_EMAIL` | Email account CFO dành riêng cho smoke |
| Secret | `MONITOR_PASSWORD` | Password của account CFO đó |

Nếu muốn người duyệt release thủ công, bật required reviewers trong Environment.
Workflow cần `contents: read`, `packages: write` chỉ ở bước publish; GitHub tự cấp
`GITHUB_TOKEN`, không cần PAT để build/push.

## 3. Cấu hình production trên Vercel

Trong Vercel Project Settings → Environment Variables → Production, khai báo:

```dotenv
INTERNAL_API_URL=https://api.your-domain.com
API_KEY=<cùng giá trị với API_KEY trên VPS>
Frontend_Origin=https://www.your-domain.com
```

Thay origin bằng domain frontend thật. `Frontend_Origin` phải khớp chính xác request
Origin; các biến này chỉ được dùng ở Next.js server, không đặt tiền tố `NEXT_PUBLIC_`.

## 4. Chuẩn bị VPS lần đầu

Hướng dẫn dưới đây giả định Ubuntu 24.04, `amd64`, user `deploy`, DNS `A` trỏ tới
VPS và firewall chỉ mở SSH, HTTP/HTTPS. Không chiếm cổng 80/443 nếu VPS đang chạy
website khác.

Tạo DNS record `A` cho `api.your-domain.com` trỏ tới IPv4 công khai của VPS. Chỉ
tạo `AAAA` nếu IPv6 VPS hoạt động; mở đúng cổng SSH, 80 và 443 ở cả firewall VPS
và nhà cung cấp cloud.

### 4.1. SSH deploy

Thiết lập một lần cho user `deploy` và GitHub Actions.

**1. Tạo key riêng trên Mac** (nếu chưa có):

```bash
ssh-keygen -t ed25519 \
  -C "github-actions-superstore-deploy" \
  -f ~/.ssh/superstore_github_actions \
  -N ""
```

Tạo `~/.ssh/superstore_github_actions` (private) và
`~/.ssh/superstore_github_actions.pub` (public). Passphrase để trống để runner dùng
key tự động. Không dùng key này cho tài khoản cá nhân.

**2. Cài public key và quyền deploy trên VPS.** Thêm public key vào
`/home/deploy/.ssh/authorized_keys` (ví dụ dùng `ssh-copy-id` từ Mac):

```bash
ssh-copy-id -i ~/.ssh/superstore_github_actions.pub deploy@IP_VPS
```

Rule `sudoers` cần khớp lệnh mà workflow gọi (`sudo -n /usr/bin/bash ...`). Trên
VPS, tạo `/etc/sudoers.d/superstore-deploy` bằng `visudo`:

```bash
sudo visudo -f /etc/sudoers.d/superstore-deploy
```

Nội dung đã cấu hình:

```sudoers
deploy ALL=(root) NOPASSWD: /usr/bin/bash /opt/superstore/releases/*/deploy/production/bin/deploy.sh *
```

Kiểm tra cú pháp trên VPS:

```bash
sudo visudo -c
```

**3. Xác minh host key trước khi lưu secret.** Trên VPS, lấy fingerprint trực tiếp:

```bash
sudo ssh-keygen -lf /etc/ssh/ssh_host_rsa_key.pub
```

Trên Mac, lấy host key và so sánh phần `SHA256:...` với fingerprint từ VPS:

```bash
ssh-keyscan -t rsa IP_VPS > /tmp/superstore_known_hosts
ssh-keygen -lf /tmp/superstore_known_hosts
```

Chỉ khi fingerprint khớp chính xác, dùng toàn bộ dòng sau làm GitHub Environment
`production` secret `VPS_KNOWN_HOSTS`:

```bash
cat /tmp/superstore_known_hosts
```

**4. Lưu secrets và thử SSH.** Trong GitHub → Settings → Environments →
`production`, lưu toàn bộ private key vào secret `VPS_SSH_KEY`:

```bash
cat ~/.ssh/superstore_github_actions
```

Sau đó thử đăng nhập từ Mac:

```bash
ssh -i ~/.ssh/superstore_github_actions \
  -o IdentitiesOnly=yes \
  deploy@IP_VPS
```

`VPS_SSH_KEY` là private key; VPS chỉ nhận public key. `VPS_KNOWN_HOSTS` là host
key đã xác minh; workflow bật `StrictHostKeyChecking=yes` và xóa các file key tạm
sau job. Không commit hoặc gửi key thật.

**Lưu ý quyền:** rule hiện tại cho phép `deploy` chạy script nằm trong release
directory bằng quyền root. Vì `deploy` có thể ghi release đó, đây chưa phải ranh
giới đặc quyền an toàn nếu tài khoản `deploy` bị chiếm. Nên chuyển sang root-owned
wrapper/thiết kế đặc quyền đã được rà soát trước khi coi đây là cấu hình least
privilege.

### 4.2. Cài Docker, Nginx và Certbot

Trên VPS:

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl gettext-base nginx snapd
```

Cài Docker Engine và Compose plugin từ repository chính thức của Docker theo
[hướng dẫn Ubuntu](https://docs.docker.com/engine/install/ubuntu/), rồi:

```bash
sudo systemctl enable --now docker nginx
sudo nginx -t
sudo snap install --classic certbot
```

Mở cổng 80/443 tại firewall VPS và nhà cung cấp cloud; cho phép đúng SSH port
trước khi bật firewall.

### 4.3. Chuyển bộ bootstrap lên VPS

Lần đầu cần có template/script để tạo config Nginx và Redis image lock trước khi
CD deploy đầu tiên. Tại root repository, khai báo địa chỉ SSH của VPS rồi dùng
commit đã commit vào Git:

Trước đó, trên VPS tạo vùng bootstrap/release có thể ghi cho `deploy`:

```bash
sudo install -d -o deploy -g deploy -m 750 \
  /opt/superstore/bootstrap \
  /opt/superstore/releases
```

```bash
VPS_HOST=your-vps.example.com
VPS_PORT=22
VPS_USER=deploy
  SSH_KEY="$HOME/.ssh/superstore_github_actions"
RELEASE_SHA=$(git rev-parse HEAD)
git archive --format=tar "$RELEASE_SHA" deploy/production \
  | ssh -i "$SSH_KEY" -p "$VPS_PORT" "$VPS_USER@$VPS_HOST" \
      "mkdir -p '/opt/superstore/bootstrap/$RELEASE_SHA' && \
       tar -xf - -C '/opt/superstore/bootstrap/$RELEASE_SHA'"
```

Trên VPS, đặt biến theo SHA vừa chuyển và tạo thư mục cấu hình:

```bash
RELEASE_SHA=PASTE_THE_FULL_40_CHARACTER_SHA
BOOTSTRAP="/opt/superstore/bootstrap/$RELEASE_SHA/deploy/production"

sudo install -d -m 750 /etc/superstore/snowflake
sudo install -d -o deploy -g deploy -m 750 \
  /opt/superstore/releases
sudo install -d -m 750 \
  /opt/superstore/data/staff \
  /opt/superstore/logs/api \
  /var/www/certbot/.well-known/acme-challenge

sudo test -e /etc/superstore/app.env || \
  sudo install -m 600 "$BOOTSTRAP/app.env.example" /etc/superstore/app.env
sudo test -e /etc/superstore/stack.env || \
  sudo install -m 600 "$BOOTSTRAP/stack.env.example" /etc/superstore/stack.env
```

Sửa `/etc/superstore/app.env` và `/etc/superstore/stack.env` bằng editor trên VPS.
`API_DOMAIN` chỉ là hostname, ví dụ `api.your-domain.com`. Trong `app.env`, đặt
`API_KEY`, `STAFF_JWT_SECRET` (ít nhất 32 ký tự), email domain và Snowflake
credentials; không để giá trị `CHANGE_ME`.

```bash
sudo nano /etc/superstore/app.env
sudo nano /etc/superstore/stack.env
```

Snowflake config keys mà API hiện đọc:

```dotenv
SNOWFLAKE_ACCOUNT=...
SNOWFLAKE_USER=SUPERSTORE_API_USER
SNOWFLAKE_PASSWORD=...
SNOWFLAKE_DATABASE=SUPERSTORE_DB
SNOWFLAKE_GOLD_SCHEMA=ANALYTIC_LAYER_GOLD_LAYER
SNOWFLAKE_MART_SCHEMA=ANALYTIC_LAYER_MART_LAYER
SNOWFLAKE_WAREHOUSE=COMPUTE_WH
SNOWFLAKE_ROLE=ANALYTICS_READONLY
```

### 4.4. Pin Redis image một lần

`images.source.env` khai báo Redis image tag ban đầu. Script pull image và ghi digest
vào file mới; output đã tồn tại thì script từ chối ghi đè:

```bash
sudo bash "$BOOTSTRAP/bin/pin-images.sh" \
  "$BOOTSTRAP/images.source.env" \
  /etc/superstore/images.lock.env
```

Lockfile chỉ cần `REDIS_IMAGE=...@sha256:...`; API image digest được CD tạo và
ghi vào `release.env` mỗi release. Nếu GHCR package private, đăng nhập Docker dưới
root bằng token chỉ có quyền đọc package; Docker pull của deploy chạy qua `sudo`:

```bash
sudo docker login ghcr.io -u YOUR_GITHUB_USERNAME
```

Nhập token ở prompt password; không đặt token trong command/file Git.

### 4.5. Cài Nginx và cấp TLS

DNS `A` phải trỏ tới VPS. Cài cấu hình HTTP bootstrap:

```bash
sudo bash "$BOOTSTRAP/bin/install-nginx.sh" bootstrap
```

Cấp certificate bằng ACME webroot:

```bash
API_DOMAIN=$(sudo sed -n 's/^API_DOMAIN=//p' /etc/superstore/stack.env)
sudo /snap/bin/certbot certonly --webroot \
  --webroot-path /var/www/certbot \
  --domain "$API_DOMAIN"
```

Sau khi certificate tồn tại, chuyển sang cấu hình TLS:

```bash
sudo bash "$BOOTSTRAP/bin/install-nginx.sh" https
sudo nginx -t
sudo systemctl reload nginx
```

`certbot/reload-nginx.sh` là deploy hook để kiểm tra config và reload Nginx sau
renewal. Cài hook:

```bash
sudo install -D -m 755 \
  "$BOOTSTRAP/certbot/reload-nginx.sh" \
  /etc/letsencrypt/renewal-hooks/deploy/20-superstore-reload-nginx.sh
sudo /snap/bin/certbot renew --dry-run --run-deploy-hooks
```

## 5. Chạy release tự động

Sau khi bootstrap VPS, cấu hình GitHub Environment và Vercel xong:

1. Merge thay đổi vào `main` hoặc push commit được phép lên `main`.
2. Chờ workflow `Quality Gate` thành công.
3. `Superstore Production` tự kiểm tra SHA, publish API image theo digest, deploy API,
   deploy frontend Vercel và chạy production smoke.
4. Mở workflow run để xem commit SHA, từng job và kết quả smoke.

Production smoke yêu cầu `MONITOR_EMAIL` là staff account đang active với role `cfo`,
và `MONITOR_PASSWORD` khớp account đó trong SQLite production. Volume staff mới sẽ
trống: lần deploy đầu có thể triển khai API/frontend thành công nhưng smoke fail ở
bước login. Sau khi API đã chạy, tạo admin và monitor CFO theo Mục 6; sau đó push
một commit mới qua Quality Gate để CD chạy lại với account đã có. Những release sau
đó có thể smoke xanh ngay nếu account còn hoạt động.

CD bỏ qua pull request, workflow thất bại, branch khác `main`, repository khác hoặc
commit đã cũ so với `main`. Không dùng lệnh build/push image thủ công cho release thường.

## 6. Tạo và quản lý staff production

Chỉ tạo account sau khi API deploy thành công. Email cần nằm trong
`INTERNAL_EMAIL_DOMAINS` của `/etc/superstore/app.env`. Tạo admin:

```bash
sudo bash /opt/superstore/current/deploy/production/bin/compose.sh exec api \
  python -m scripts.manage_staff add admin@yourcompany.com \
  --name "Production Admin" --role admin
```

Tạo riêng CFO monitor account mà `smoke_public.py` dùng. Nhập cùng password hai
lần trong CLI, rồi lưu đúng email/password ở GitHub Environment secrets
`MONITOR_EMAIL` và `MONITOR_PASSWORD`:

```bash
sudo bash /opt/superstore/current/deploy/production/bin/compose.sh exec api \
  python -m scripts.manage_staff add cfo-monitor@yourcompany.com \
  --name "Production Monitor" --role cfo
```

Liệt kê để xác nhận email, role và active state:

```bash
sudo bash /opt/superstore/current/deploy/production/bin/compose.sh exec api \
  python -m scripts.manage_staff list
```

Role/password/active commands:

```bash
sudo bash /opt/superstore/current/deploy/production/bin/compose.sh exec api \
  python -m scripts.manage_staff role user@yourcompany.com cfo
sudo bash /opt/superstore/current/deploy/production/bin/compose.sh exec api \
  python -m scripts.manage_staff password user@yourcompany.com
sudo bash /opt/superstore/current/deploy/production/bin/compose.sh exec api \
  python -m scripts.manage_staff disable user@yourcompany.com
sudo bash /opt/superstore/current/deploy/production/bin/compose.sh exec api \
  python -m scripts.manage_staff enable user@yourcompany.com
```

CLI hỏi password tương tác. Tài khoản staff được lưu trong
`/opt/superstore/data/staff/internal_users.db`, không nằm trong Git.

## 7. Xác minh release

Public API liveness phải trả `200`, `status=ok` và SHA release:

```bash
curl -i https://api.your-domain.com/api/health/live
```

HTTP phải redirect `308` sang HTTPS:

```bash
curl -I http://api.your-domain.com/api/health/live
```

Từ VPS, readiness nội bộ phải có `status=ready`, `staff_store=true`, `redis=true`:

```bash
curl -i http://127.0.0.1:8000/api/health/ready
```

Public `/api/health/ready`, `/metrics`, `/docs`, `/openapi.json` phải trả `404`.
Port `8000` không được truy cập từ Internet. Frontend smoke tự chạy trong CD;
case hiện tại là `DEPLOY-01`–`DEPLOY-06`.

## 8. Logs và khôi phục

```bash
# API / Redis container logs
sudo bash /opt/superstore/current/deploy/production/bin/compose.sh \
  logs --tail=100 api redis

# API structured HTTP và application logs
sudo tail -n 100 /opt/superstore/logs/api/http.log
sudo tail -n 100 /opt/superstore/logs/api/application.log

# Nginx logs
sudo tail -n 100 /var/log/nginx/superstore-access.log
sudo tail -n 100 /var/log/nginx/superstore-error.log
```

`deploy.sh` tự khôi phục API container trước nếu chính lệnh deploy thất bại. Nếu
Vercel deploy hoặc smoke fail sau đó, không có rollback hai tầng tự động; xem
[Deploy Error Tracing](error_tracing.md), xác định đúng release trước khi khôi phục.

Workflow đang để lại `release.tar.gz` sau khi giải nén tại release directory. File
này không được Compose sử dụng; sau khi xác nhận release ổn định, có thể xóa archive
của đúng release để tiết kiệm dung lượng, giữ lại thư mục đã giải nén.

## 9. Tài liệu liên quan

- Thành phần và trạng thái: [discovery_result.md](discovery_result.md)
- Luồng request và filesystem: [system_architecture_lineage.md](system_architecture_lineage.md)
- Xử lý lỗi theo workflow stage: [error_tracing.md](error_tracing.md)
- Backend: [API Operations](../API/operation.md)
- Frontend: [Frontend Operations](../frontend/operation.md)
