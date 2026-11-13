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

| Loại     | Tên                 | Giá trị                                |
| -------- | ------------------- | -------------------------------------- |
| Variable | `VPS_HOST`          | Hostname hoặc IPv4 VPS                 |
| Variable | `VPS_PORT`          | Cổng SSH, thường là `22`               |
| Variable | `VPS_USER`          | User deploy, thường là `deploy`        |
| Variable | `VERCEL_ORG_ID`     | `orgId` của project Vercel             |
| Variable | `VERCEL_PROJECT_ID` | `projectId` của frontend Vercel        |
| Variable | `FRONTEND_ORIGIN`   | HTTPS origin frontend, không thêm path |
| Secret   | `VPS_SSH_KEY`       | Private key riêng cho GitHub Actions   |
| Secret   | `VPS_KNOWN_HOSTS`   | Host key VPS đã xác minh               |
| Secret   | `VERCEL_TOKEN`      | Token deploy Vercel                    |
| Secret   | `MONITOR_EMAIL`     | Email account CFO dành riêng cho smoke |
| Secret   | `MONITOR_PASSWORD`  | Password của account CFO đó            |

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

Trước đó, trên VPS tạo vùng release có thể ghi cho `deploy`:

```bash
sudo install -d -o deploy -g deploy -m 750 \
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
      "mkdir -p '/opt/superstore/releases/$RELEASE_SHA' && \
       tar -xf - -C '/opt/superstore/releases/$RELEASE_SHA'"
```

Trên VPS, đặt biến theo SHA vừa chuyển và tạo thư mục cấu hình:

```bash
RELEASE_SHA=PASTE_THE_FULL_40_CHARACTER_SHA
RELEASE="/opt/superstore/releases/$RELEASE_SHA"
CONFIG_DIR="$RELEASE/deploy/production"

# Tạo release directory
sudo install -d -o deploy -g deploy -m 750 "$RELEASE"

sudo install -d -m 750 /etc/superstore/snowflake

sudo install -d -m 750 \
  /opt/superstore/data/staff \
  /opt/superstore/logs/api
sudo install -d -m 755 /var/www/certbot/.well-known/acme-challenge

sudo test -e /etc/superstore/app.env || \
  sudo install -m 600 "$CONFIG_DIR/app.env.example" /etc/superstore/app.env
sudo test -e /etc/superstore/stack.env || \
  sudo install -m 600 "$CONFIG_DIR/stack.env.example" /etc/superstore/stack.env
sudo test -e /etc/superstore/images.source.env || \
  sudo install -m 600 "$CONFIG_DIR/images.source.env" /etc/superstore/images.source.env
sudo test -e /etc/superstore/grafana.env || \
  sudo install -m 600 "$CONFIG_DIR/grafana.env.example" /etc/superstore/grafana.env

sudo chown root:root /etc/superstore/grafana.env
sudo chmod 600 /etc/superstore/grafana.env
```

Sửa `/etc/superstore/app.env` và `/etc/superstore/stack.env` bằng editor trên VPS.
`API_DOMAIN` chỉ là hostname, ví dụ `api.your-domain.com`. Trong `app.env`, đặt
`API_KEY`, `STAFF_JWT_SECRET` (ít nhất 32 ký tự), email domain và Snowflake
credentials; không để giá trị `CHANGE_ME`.

```bash
sudo nano /etc/superstore/app.env
sudo nano /etc/superstore/stack.env
sudo nano /etc/superstore/images.source.env
sudo nano /etc/superstore/grafana.env
```

Snowflake config keys mà API hiện đọc:

```dotenv
# app.env
APP_NAME=
APP_ENV=production
LOG_LEVEL=

API_KEY=

STAFF_JWT_SECRET=
STAFF_SESSION_TTL_HOURS=8
STAFF_COOKIE_SECURE=true
STAFF_DB_PATH=
INTERNAL_EMAIL_DOMAINS=
AUTH_RATE_LIMIT_PER_MINUTE=10
TRUST_PROXY_HEADERS=false

CACHE_ENABLED=true
REDIS_URL=
CACHE_TTL_SECONDS=900
CACHE_KEY_PREFIX=

LOG_FILE=
APP_LOG_DIR=

SNOWFLAKE_ACCOUNT=
SNOWFLAKE_USER=
SNOWFLAKE_PASSWORD=
SNOWFLAKE_DATABASE=
SNOWFLAKE_GOLD_SCHEMA=
SNOWFLAKE_MART_SCHEMA=
SNOWFLAKE_WAREHOUSE=
SNOWFLAKE_ROLE=
SNOWFLAKE_MAX_ROWS=1000
SNOWFLAKE_QUERY_TIMEOUT=30

# stack.env
API_DOMAIN=
MINIO_ROOT_USER=
MINIO_ROOT_PASSWORD=

# grafana
GF_SECURITY_ADMIN_USER=
GF_SECURITY_ADMIN_PASSWORD=
GF_AUTH_ANONYMOUS_ENABLED=
GF_USERS_ALLOW_SIGN_UP=
```

Tạo bucket loki-logs trong MinIO.

```
ssh -N \
  -L 3001:127.0.0.1:9001 \
  deploy@YOUR_VPS

# access
open localhost:9090 -> create loki-logs
```

### 4.4. Pin image hạ tầng một lần

`images.source.env` khai báo tag của các image hạ tầng. Script pull image và ghi digest
vào file mới; output đã tồn tại thì script từ chối ghi đè:

```bash
sudo bash "$CONFIG_DIR/bin/pin-images.sh" \
  /etc/superstore/images.source.env \
  /etc/superstore/images.lock.env
```

Lockfile cần đủ các biến `*_IMAGE` mà Compose sử dụng; API image digest được CD tạo và
ghi vào `release.env` mỗi release. Nếu GHCR package private, đăng nhập Docker dưới
root bằng token chỉ có quyền đọc package; Docker pull của deploy chạy qua `sudo`:

```bash
sudo docker login ghcr.io -u YOUR_GITHUB_USERNAME
```

Nhập token ở prompt password; không đặt token trong command/file Git.

### 4.5. Cài Nginx và cấp TLS

DNS `A` phải trỏ tới VPS. Cài cấu hình HTTP bootstrap:

```bash
sudo bash "$CONFIG_DIR/bin/install-nginx.sh" bootstrap
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
sudo bash "$CONFIG_DIR/bin/install-nginx.sh" https
sudo nginx -t
sudo systemctl reload nginx
```

`certbot/reload-nginx.sh` là deploy hook để kiểm tra config và reload Nginx sau
renewal. Cài hook:

```bash
sudo install -D -m 755 \
  "$CONFIG_DIR/certbot/reload-nginx.sh" \
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

## 9. Connect Grafana, Prometheus & Minio By SSH tunnel

SSH tunnel không triển khai hay khởi chạy Grafana và Prometheus. Nó chỉ tạo đường truyền bảo mật từ máy Mac đến hai port localhost trên VPS:

```
ssh -N \
  -L 3001:127.0.0.1:3001 \
  -L 9090:127.0.0.1:9090 \
  -L 9001:127.0.0.1:9001 \
  deploy@YOUR_VPS
```

| Máy Mac (Local)  | VPS (Host)       | Dịch vụ       |
| ---------------- | ---------------- | ------------- |
| `localhost:3001` | `127.0.0.1:3001` | Grafana       |
| `localhost:9090` | `127.0.0.1:9090` | Prometheus    |
| `localhost:9000` | `127.0.0.1:9000` | MinIO API     |
| `localhost:9001` | `127.0.0.1:9001` | MinIO Console |

Một lưu ý: Trước khi kiểm tra 4 Targets ở trạng thái UP, phải bảo đảm FastAPI đã expose /metrics, Redis Exporter và Node Exporter hoạt động, đồng thời Prometheus có thể truy cập chúng qua Docker network

## 10. Cài Uptime Kuma

```
# tạo thư mục, tải image và lấy diges
mkdir -p ~/superstore-kuma
cd ~/superstore-kuma

docker pull louislam/uptime-kuma:2.5.5
docker image inspect \
  --format '{{index .RepoDigests 0}}' \
  louislam/uptime-kuma:2.5.5

# .env
KUMA_IMAGE=louislam/uptime-kuma@sha256:THAY_BANG_DIGEST_THAT

# neu thue vps for kuma
ssh -N -L 3002:127.0.0.1:3002 USER@MONITOR_HOST
```

| Máy Mac (Local)  | VPS (Host)       | Dịch vụ |
| ---------------- | ---------------- | ------- |
| `localhost:3002` | `127.0.0.1:3002` | KUMA    |

## 11. postman

## 12. Backup

Luồng: Mac giữ **age private key** → VPS sao lưu tự động mỗi ngày → S3 giữ file
đã mã hóa → Mac tải và kiểm tra bản khôi phục → khi có sự cố, dựng VPS và deploy
đúng release. Backup chỉ gồm staff SQLite, cấu hình VPS và metadata release;
không gồm dữ liệu Snowflake/MinIO/Redis, logs, certificate hay source/image
của release.

### 12.1. Chuẩn bị trước khi cài

Commit/push `deploy/production/backup/` và `RAG_CHATBOT/scripts/backup_staff.py`,
đợi Quality Gate/CD deploy API image chứa script mới. Trên Mac, tạo key **một
lần** và giữ private key ngoài VPS/Git:

```bash
brew install age awscli
mkdir -p "$HOME/.config/superstore"
chmod 700 "$HOME/.config/superstore"
age-keygen -o "$HOME/.config/superstore/superstore-backup.agekey"
chmod 600 "$HOME/.config/superstore/superstore-backup.agekey"
age-keygen -y "$HOME/.config/superstore/superstore-backup.agekey"
```

Dòng `age1...` cuối cùng là **public recipient** để điền vào VPS. Sao lưu
private key ở nơi an toàn khác; mất key thì không giải mã được backup. Trên AWS.

chuẩn bị bucket và IAM user đúng tên `superstore-vps-backup-writer` với quyền
upload **và tải lại** object trong prefix backup; script kiểm tra tên IAM này.
Không cấp quyền xóa object cho backup writer. Tài khoản restore trên Mac cần
quyền liệt kê bucket và đọc object. Repo không tạo bucket, Object Lock
hay retention policy: cấu hình và xác minh các phần đó riêng trên AWS trước khi
coi backup có khả năng chống xóa.

### 12.2. Cài backup tự động trên VPS

Script yêu cầu API production đang chạy, staff DB, `current` release, các file
cấu hình trong `/etc/superstore`, Nginx config và SSH `authorized_keys`; thiếu file nào thì
backup sẽ dừng và báo đường dẫn. Cài công cụ và tạo file cấu hình root-only:

```bash
sudo apt-get update
sudo apt-get install -y age curl unzip
AWS_CLI_TMP=$(mktemp -d)
curl -fsSL https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip \
  -o "$AWS_CLI_TMP/awscliv2.zip"
unzip -q "$AWS_CLI_TMP/awscliv2.zip" -d "$AWS_CLI_TMP"
sudo "$AWS_CLI_TMP/aws/install"
aws --version
sudo test -e /etc/superstore/backup.env || \
  sudo install -o root -g root -m 600 \
    /opt/superstore/current/deploy/production/backup/backup.env.example \
    /etc/superstore/backup.env
sudo nano /etc/superstore/backup.env
sudo chown root:root /etc/superstore/backup.env
sudo chmod 600 /etc/superstore/backup.env
```

Ví dụ AWS CLI trên dành cho VPS `amd64` như mục 4; với ARM64, dùng bản
`awscli-exe-linux-aarch64.zip` từ [AWS CLI installation guide](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html).
Thư mục `$AWS_CLI_TMP` chỉ chứa bộ cài tạm, có thể xóa sau khi `aws --version`
thành công.

Điền các biến `AWS_DEFAULT_REGION`, `AWS_ACCESS_KEY_ID`,
`AWS_SECRET_ACCESS_KEY`, `SUPERSTORE_BACKUP_BUCKET`,
`SUPERSTORE_BACKUP_PREFIX=superstore-vps` và `SUPERSTORE_AGE_RECIPIENT=age1...`.
Chỉ public recipient nằm trên VPS; không đặt age private key ở đây. Sau mỗi lần
thay `backup.sh` hoặc systemd unit trong release, chạy lại installer vì systemd
dùng **bản copy** đã cài:

```bash
sudo bash /opt/superstore/current/deploy/production/backup/install.sh
sudo systemctl start superstore-backup.service
sudo journalctl -u superstore-backup.service -n 100 --no-pager
systemctl list-timers superstore-backup.timer
```

Journal cần có `Backup completed: s3://...`. Timer chạy hằng ngày lúc **03:15
theo giờ VPS**, có thể trễ ngẫu nhiên tối đa 15 phút; `Persistent=true` cho
phép chạy bù sau khi VPS bật lại. Kiểm tra timezone bằng `timedatectl`.
Mỗi lượt script chụp SQLite nhất quán, mã hóa bằng age, upload `.age` và
`.sha256`, tải lại để kiểm tra checksum. Bản trên S3 được giữ; file tạm trên VPS
được dọn khi script kết thúc bình thường.

### 12.3. Tải về Mac và diễn tập khôi phục

Trên Mac cài công cụ, đăng nhập AWS bằng **principal chỉ đọc** rồi liệt kê
object. Chọn **key của file `.tar.gz.age`**, không chọn file `.sha256`:

```bash
aws configure --profile superstore-restore
export AWS_PROFILE=superstore-restore
export SUPERSTORE_BACKUP_BUCKET=YOUR_BUCKET_NAME
export AGE_IDENTITY_FILE="$HOME/.config/superstore/superstore-backup.agekey"
aws s3 ls "s3://$SUPERSTORE_BACKUP_BUCKET/superstore-vps/" --recursive
```

Tại root repository, đặt `OBJECT_KEY` bằng đường dẫn object **bên trong
bucket**, rồi chạy:

```bash
umask 077
mkdir -p "$HOME/superstore-restore-drill"
OBJECT_KEY='superstore-vps/VPS_HOSTNAME/YYYYMMDDTHHMMSSZ/superstore-...tar.gz.age'
bash deploy/production/backup/restore-local.sh \
  "$OBJECT_KEY" \
  "$HOME/superstore-restore-drill"
```

Script tải cả checksum, so SHA-256, giải mã, giải nén vào thư mục `restore-*`
mới và chạy SQLite `integrity_check`. Ghi lại đường dẫn in sau
`Restore artifact verified at:` rồi kiểm tra manifest và staff DB tại đó:

```bash
RESTORE_DIR="$HOME/superstore-restore-drill/restore-THAY_BANG_TEN_THUC_TE"
cat "$RESTORE_DIR/metadata/backup-manifest.env"
test -s "$RESTORE_DIR/data/staff/internal_users.db"
```

Thư mục restore chứa secret và database **đã giải mã**; giữ ngoài repo, giới
hạn quyền truy cập và xóa sau khi diễn tập xong. Chỉ có dòng `Backup completed`
trên VPS chưa đủ: cần diễn tập tải/giải mã định kỳ để xác nhận khả năng phục hồi.

### 12.4. Khôi phục khi VPS gặp sự cố

**Trên Mac:** hoàn thành mục 12.3. Đọc commit và GHCR digest từ manifest, kiểm tra
commit còn trong Git, rồi chuyển source/config/SQLite qua SSH:

```bash
RELEASE_SHA=$(sed -n 's/^release_sha=//p' \
  "$RESTORE_DIR/metadata/backup-manifest.env")
API_IMAGE=$(sed -n 's/^api_image=//p' \
  "$RESTORE_DIR/metadata/backup-manifest.env")
git fetch origin
git cat-file -e "$RELEASE_SHA^{commit}"
printf 'Release: %s\nImage: %s\n' "$RELEASE_SHA" "$API_IMAGE"

VPS_HOST=NEW_VPS_IP
VPS_PORT=22
SSH_KEY="$HOME/.ssh/superstore_github_actions"
ssh -i "$SSH_KEY" -p "$VPS_PORT" deploy@"$VPS_HOST" \
  'umask 077; mkdir -p ~/restore-upload'
scp -i "$SSH_KEY" -P "$VPS_PORT" -r "$RESTORE_DIR/etc/superstore" \
  "$RESTORE_DIR/data/staff/internal_users.db" \
  deploy@"$VPS_HOST":restore-upload/
git archive "$RELEASE_SHA" deploy/production \
  | ssh -i "$SSH_KEY" -p "$VPS_PORT" deploy@"$VPS_HOST" \
      "mkdir -p '/opt/superstore/releases/$RELEASE_SHA' && \
       tar -xf - -C '/opt/superstore/releases/$RELEASE_SHA'"
```

`api_image` là GHCR digest; nếu rỗng hoặc image không còn trên GHCR, cần
khôi phục image trước. Bản giải mã chuyển qua SSH nằm tạm trong home của
`deploy`; không lưu trong repo. VPS mới cần hoàn thành Docker, Nginx, Certbot,
DNS, SSH và thư mục release do `deploy` sở hữu theo mục 4 **trước** các lệnh trên.

**Trên VPS mới:** cài lại cấu hình đã kiểm tra và staff DB **trước khi chạy API**:

```bash
sudo install -d -m 750 /etc/superstore
for name in app.env stack.env grafana.env images.lock.env images.source.env; do
  sudo install -o root -g root -m 600 \
    "/home/deploy/restore-upload/superstore/$name" \
    "/etc/superstore/$name"
done
sudo install -d -o 10001 -g 10001 -m 750 /opt/superstore/data/staff
sudo install -o 10001 -g 10001 -m 600 \
  /home/deploy/restore-upload/internal_users.db \
  /opt/superstore/data/staff/internal_users.db
```

Nếu backup có `etc/superstore/snowflake/`, khôi phục riêng thư mục đó với quyền
đọc phù hợp cho API user `10001`. Kiểm tra domain và secret trong các file
`.env` trước khi dùng. Certificate không nằm trong backup. Cài lại Nginx và
Certbot theo mục 4.2, rồi tạo certificate và HTTPS config từ source release:

```bash
RELEASE_SHA=PASTE_40_CHARACTER_SHA
NGINX_INSTALLER="/opt/superstore/releases/$RELEASE_SHA/deploy/production/bin/install-nginx.sh"
sudo install -d -m 755 /var/www/certbot/.well-known/acme-challenge
sudo bash "$NGINX_INSTALLER" bootstrap
API_DOMAIN=$(sudo sed -n 's/^API_DOMAIN=//p' /etc/superstore/stack.env)
sudo /snap/bin/certbot certonly --webroot \
  --webroot-path /var/www/certbot \
  --domain "$API_DOMAIN"
sudo bash "$NGINX_INSTALLER" https
```

Nếu GHCR private, đăng nhập GHCR cho Docker root như mục 4.4. Với **digest đã
lấy trên Mac**, chạy trên VPS:

```bash
API_IMAGE='ghcr.io/owner/repository-api@sha256:PASTE_DIGEST'
sudo bash "/opt/superstore/releases/$RELEASE_SHA/deploy/production/bin/deploy.sh" \
  "$RELEASE_SHA" "$API_IMAGE"
```

`deploy.sh` kéo image, kiểm tra readiness/HTTPS rồi cập nhật symlink `current`.
Tạo lại các bucket MinIO cần cho monitoring nếu dùng, vì dữ liệu MinIO không
nằm trong backup.
Kiểm tra `/api/health/ready`, staff login, dashboard và production smoke theo
mục 7. Sau khi xác nhận, xóa bản giải mã trong `restore-upload` trên VPS. Tạo
lại `/etc/superstore/backup.env` (không có trong artifact), cài timer theo mục
12.2 và chạy backup mới. Bản backup gần nhất là mốc phục hồi: thay đổi staff
sau mốc đó cần tạo lại.

Nếu chỉ khôi phục staff DB trên **VPS cũ**, stop API trước khi cài file đã
chuyển vào `/home/deploy/restore-upload/`, rồi chạy lại:

```bash
sudo bash /opt/superstore/current/deploy/production/bin/compose.sh stop api
sudo install -o 10001 -g 10001 -m 600 \
  /home/deploy/restore-upload/internal_users.db \
  /opt/superstore/data/staff/internal_users.db
sudo bash /opt/superstore/current/deploy/production/bin/compose.sh \
  up -d --wait api
curl -i http://127.0.0.1:8000/api/health/ready
```

Không thay SQLite khi API còn đang ghi.

Không tự chép đè `authorized_keys`, sudoers hoặc Nginx config từ artifact lên
VPS mới: rà soát chúng với IP/domain và quyền của VPS mới trước. Backup và
restore script không tự thay dữ liệu production.

## 13. Tài liệu liên quan

- Thành phần và trạng thái: [discovery_result.md](discovery_result.md)
- Luồng request và filesystem: [system_architecture_lineage.md](system_architecture_lineage.md)
- Xử lý lỗi theo workflow stage: [error_tracing.md](error_tracing.md)
- Thực hành kiểm tra FastAPI, VPS và Snowflake: [fastapi_vps_check.md](fastapi_vps_check.md)
- Kiến trúc monitoring: [monitoring/system_architecture_lineage.md](monitoring/system_architecture_lineage.md)
- Backend: [API Operations](../API/operation.md)
- Frontend: [Frontend Operations](../frontend/operation.md)
