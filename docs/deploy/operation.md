# GHCR — Publish backend image thủ công

## 1. Commit code và publish image lần đầu

Thực hiện trên máy phát triển, tại thư mục gốc repository. Quy trình này đóng gói code đã commit thành Docker image và đẩy image lên GitHub Container Registry (GHCR). VPS sẽ tải image theo digest để chạy đúng phiên bản.

### 1.1. Kiểm tra và commit

Đảm bảo các thay đổi muốn phát hành đã được commit. `git archive HEAD` chỉ lấy code của commit hiện tại, không lấy thay đổi chưa commit.

```bash
git status --short
git diff --check
git diff --cached --check
```

Stage các file triển khai và Dockerfile đang có trong repository:

```bash
git add deploy/production RAG_CHATBOT/Dockerfile
```

Kiểm tra nội dung chuẩn bị commit:

```bash
git diff --cached --stat
git diff --cached
```

Không commit `.env` chứa secret, private key, database hoặc dữ liệu runtime.

```bash
git commit -m "feat: add production deployment configuration"
```

### 1.2. Đăng nhập GHCR

Tạo GitHub Personal Access Token (classic) với quyền `write:packages`. Không cấp `delete:packages` nếu chỉ cần publish image. Nếu repository thuộc organization yêu cầu SSO, authorize token cho organization đó. Xem [GitHub Container Registry authentication](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry).

```bash
docker login ghcr.io -u YOUR_GITHUB_USERNAME
```

Nhập token tại prompt password. Không đặt token trực tiếp trong command hoặc file Git.

### 1.3. Khai báo thông tin image

Chạy trong cùng Terminal với các bước build bên dưới. Thay owner và repository bằng giá trị GitHub của bạn. Tên image phải viết thường.

```bash
GITHUB_OWNER=your-owner
GITHUB_REPO=your-repository
RELEASE_SHA=$(git rev-parse HEAD)
IMAGE="ghcr.io/${GITHUB_OWNER}/${GITHUB_REPO}-api"
```

`RELEASE_SHA` là mã commit đầy đủ 40 ký tự. Đây là commit sẽ được đóng gói và cũng là mã release VPS nhận.

### 1.4. Build từ đúng source đã commit

Tạo source archive chỉ chứa thư mục ứng dụng. Docker build context cũng chính là thư mục này.

```bash
build_dir=$(mktemp -d)

git archive HEAD RAG_CHATBOT \
  | tar -x -C "$build_dir"
```

Repo hiện dùng `RAG_CHATBOT/Dockerfile`; không dùng `Dockerfile.production`.

Build và publish cho VPS `amd64`:

```bash
docker buildx build \
  --platform linux/amd64 \
  -f "$build_dir/RAG_CHATBOT/Dockerfile" \
  --label "org.opencontainers.image.source=https://github.com/$GITHUB_OWNER/$GITHUB_REPO" \
  --label "org.opencontainers.image.revision=$RELEASE_SHA" \
  -t "$IMAGE:$RELEASE_SHA" \
  --push \
  "$build_dir/RAG_CHATBOT"
```

Nếu VPS dùng ARM64, đổi platform thành `linux/arm64`. Không đổi platform tùy ý: image phải tương thích CPU của VPS.

### 1.5. Lấy digest của image

Sau khi push thành công, xem thông tin image:

```bash
docker buildx imagetools inspect "$IMAGE:$RELEASE_SHA"
```

Lưu lại commit SHA và digest cấp cao nhất được hiển thị cho tag vừa push:

```text
Commit SHA: 40 ký tự
Image: ghcr.io/owner/repository-api@sha256:...
```

Dùng digest khi deploy, không dùng tag `latest`. Script [deploy.sh](../../deploy/production/bin/deploy.sh) nhận `COMMIT_SHA` và image dạng `ghcr.io/...@sha256:...`.

Trong GitHub Packages, kiểm tra package đã được liên kết với repository để quyền truy cập package kế thừa đúng từ repository/workflow.

### Lưu ý trước khi triển khai VPS

Lệnh archive ở trên chỉ tạo source context để build image. VPS vẫn cần release directory chứa cả `deploy/production/` và source của commit đó, vì `deploy.sh` gọi các script Compose từ release directory.

Hiện file cấu hình là `deploy/production/compose.yml`; `compose.sh` dùng tên này, nhưng bước kiểm tra đầu `deploy.sh` đang tìm `compose.yaml`. Cần đồng bộ hai tên trong code triển khai trước khi chạy deploy trên VPS.

## 2. Chuẩn bị VPS, DNS và tài khoản

### 2.1. Kiểm tra VPS

Đăng nhập bằng tài khoản quản trị VPS:

```bash
ssh YOUR_ADMIN_USER@YOUR_VPS_IP
```

Kiểm tra hệ điều hành, kiến trúc CPU và các cổng đang được sử dụng:

```bash
cat /etc/os-release
dpkg --print-architecture
sudo ss -lntp
```

Hướng dẫn này giả định VPS dùng Ubuntu 24.04 và `amd64`. Nếu cổng 80/443 đang thuộc website khác, không tự dừng dịch vụ đó.

### 2.2. Cấu hình DNS

Tại nhà cung cấp DNS, tạo bản ghi trỏ hostname API tới địa chỉ IPv4 công khai của VPS:

```text
Type: A
Name: api
Value: PUBLIC_IPV4_CỦA_VPS
```

Chỉ tạo bản ghi `AAAA` nếu IPv6 của VPS đã hoạt động và có thể nhận kết nối. Nếu dùng Cloudflare, ban đầu đặt record API ở chế độ **DNS only** để kiểm tra trực tiếp Nginx và Certbot.

```bash
dig +short A api.yourdomain.com
dig +short AAAA api.yourdomain.com
```

Kết quả bản ghi `A` phải trỏ tới `PUBLIC_IPV4_CỦA_VPS`; nếu dùng `AAAA`, địa chỉ IPv6 cũng phải đúng.

### 2.3. Mở firewall

Cài UFW trên VPS:

```bash
sudo apt-get update
sudo apt-get install -y ufw
```

Trước khi bật firewall, xác nhận cổng SSH thực tế. Ví dụ dưới đây giả định SSH dùng cổng 22:

```bash
sudo ss -lntp
```

Cho phép SSH và cổng web cần cho HTTP/TLS, sau đó bật UFW:

```bash
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
sudo ufw status
```

**Nếu SSH dùng cổng khác, thay `22` bằng đúng cổng đó trước khi chạy `ufw enable`; nếu không, bạn có thể mất kết nối SSH.** Nếu nhà cung cấp VPS có firewall riêng, cũng cần mở các cổng tương ứng ở đó.

### 2.4. Tạo user `deploy`

Nếu user chưa tồn tại:

```bash
sudo adduser deploy
sudo usermod -aG sudo deploy
```

Trên **máy phát triển**, kiểm tra SSH key hiện có:

```bash
ls -la ~/.ssh
```

Một cặp Ed25519 thường gồm hai file cùng tên; ví dụ:

```text
id_ed25519_superstore       private key — giữ trên máy bạn, không gửi lên VPS
id_ed25519_superstore.pub   public key — được phép thêm vào VPS
```

Nếu chưa có cặp key riêng cho VPS này, tạo một cặp trên máy phát triển:

```bash
ssh-keygen -t ed25519 \
  -C "superstore-vps-deploy" \
  -f ~/.ssh/id_ed25519_superstore
```

Lệnh tạo cả private key `~/.ssh/id_ed25519_superstore` và public key `~/.ssh/id_ed25519_superstore.pub`. Đặt passphrase nếu được yêu cầu. Không mở, sao chép hoặc gửi private key.

Tạo thư mục SSH cho user `deploy` trên VPS:

```bash
sudo install -d \
  -m 700 \
  -o deploy \
  -g deploy \
  /home/deploy/.ssh
```

Trên VPS, mở file chứa các public key được phép đăng nhập:

```bash
sudo nano /home/deploy/.ssh/authorized_keys
```

Trên máy phát triển, lấy nội dung **public key** để dán vào `authorized_keys`:

```bash
cat ~/.ssh/id_ed25519_superstore.pub
```

Mỗi public key phải nằm trên một dòng. Sau khi lưu file trên VPS, đặt đúng quyền:

```bash
sudo chown deploy:deploy /home/deploy/.ssh/authorized_keys
sudo chmod 600 /home/deploy/.ssh/authorized_keys
```

Mở terminal mới trên máy phát triển để thử đăng nhập:

```bash
ssh -i ~/.ssh/id_ed25519_superstore deploy@YOUR_VPS_IP
```

Giữ phiên quản trị VPS hiện tại cho đến khi đăng nhập bằng user `deploy` thành công.

## 3. Cài Docker, Nginx và Certbot

Thực hiện trên VPS bằng tài khoản có quyền `sudo`.

### 3.1. Cài công cụ cần thiết

```bash
sudo apt-get update
sudo apt-get install -y \
  ca-certificates \
  curl \
  git \
  jq \
  gettext-base \
  dnsutils \
  python3 \
  nginx \
  snapd
```

### 3.2. Cài Docker Engine từ repository chính thức

Thêm key và repository Docker:

```bash
sudo install -m 0755 -d /etc/apt/keyrings

sudo curl -fsSL \
  https://download.docker.com/linux/ubuntu/gpg \
  -o /etc/apt/keyrings/docker.asc

sudo chmod a+r /etc/apt/keyrings/docker.asc
```

Tạo file repository:

```bash
sudo nano /etc/apt/sources.list.d/docker.sources
```

Với Ubuntu 24.04 `amd64`, nội dung là:

```text
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: noble
Components: stable
Architectures: amd64
Signed-By: /etc/apt/keyrings/docker.asc
```

Nếu VPS là ARM64, đổi `Architectures: amd64` thành `Architectures: arm64`.

Cài Docker Engine và Compose plugin:

```bash
sudo apt-get update
sudo apt-get install -y \
  docker-ce \
  docker-ce-cli \
  containerd.io \
  docker-buildx-plugin \
  docker-compose-plugin
```

Bật Docker và kiểm tra phiên bản:

```bash
sudo systemctl enable --now docker
sudo docker version
sudo docker compose version
```

Đây là cách cài Docker CE từ repository chính thức. Không cài thêm `docker.io` song song. Xem [Docker Engine trên Ubuntu](https://docs.docker.com/engine/install/ubuntu/).

### 3.3. Khởi động Nginx

```bash
sudo systemctl enable --now nginx
sudo nginx -t
```

### 3.4. Cài Certbot

Trên VPS mới chưa cài Certbot từ nguồn khác:

```bash
sudo snap install --classic certbot
sudo /snap/bin/certbot --version
```

## 4. Chuyển release lên VPS

Thực hiện trên máy phát triển. Dùng đúng commit SHA đã dùng để build image:

```bash
RELEASE_SHA=$(git rev-parse HEAD)
```

Tạo archive chỉ gồm cấu hình deploy đã commit, không mang theo `.env` local:

```bash
git archive \
  --format=tar.gz \
  --output="/tmp/superstore-release-$RELEASE_SHA.tar.gz" \
  "$RELEASE_SHA" \
  deploy/production
```

Tạo thư mục release và chép archive lên VPS:

```bash
ssh deploy@YOUR_VPS_IP \
  "mkdir -p /opt/superstore/releases/$RELEASE_SHA"

scp \
  "/tmp/superstore-release-$RELEASE_SHA.tar.gz" \
  "deploy@YOUR_VPS_IP:/opt/superstore/releases/$RELEASE_SHA/release.tar.gz"

ssh deploy@YOUR_VPS_IP \
  "tar -xzf /opt/superstore/releases/$RELEASE_SHA/release.tar.gz -C /opt/superstore/releases/$RELEASE_SHA && rm /opt/superstore/releases/$RELEASE_SHA/release.tar.gz"
```

Sau khi xác nhận đã giải nén thành công, có thể xóa archive tạm trên máy phát triển:

```bash
rm "/tmp/superstore-release-$RELEASE_SHA.tar.gz"
```

## 5. Cấu hình runtime trên VPS

Đăng nhập bằng `deploy`, rồi xác định release:

```bash
RELEASE_SHA=YOUR_FULL_40_CHARACTER_COMMIT_SHA
cd "/opt/superstore/releases/$RELEASE_SHA/deploy/production"
```

### 5.1. Tạo file môi trường lần đầu

Chỉ copy nếu file chưa tồn tại; không ghi đè cấu hình/secret đang dùng:

```bash
sudo test -e /etc/superstore/app.env || \
  sudo install -m 600 app.env.example /etc/superstore/app.env

sudo test -e /etc/superstore/stack.env || \
  sudo install -m 600 stack.env.example /etc/superstore/stack.env
```

Sửa cấu hình ứng dụng và nhập secret thật:

```bash
sudo nano /etc/superstore/app.env
```

Tạo riêng hai secret, không dùng chung giá trị:

```bash
openssl rand -hex 32
openssl rand -hex 32
```

Gán lần lượt vào `API_KEY` và `STAFF_JWT_SECRET`. Điền thêm `INTERNAL_EMAIL_DOMAINS` và các biến Snowflake mà adapter của dự án đang hỗ trợ. Không đưa `STAFF_JWT_SECRET` lên frontend.

Đặt domain API trong stack config:

```bash
sudo nano /etc/superstore/stack.env
```

```dotenv
API_DOMAIN=api.your-domain.com
```

Không thêm scheme (`https://`) hoặc path vào `API_DOMAIN`.

Nếu Snowflake dùng private key, đặt file dưới `/etc/superstore/snowflake/`; container mount thư mục này read-only tại `/run/secrets/snowflake`. Đảm bảo adapter thực sự được cấu hình để đọc đúng file và UID container có quyền đọc.

### 5.2. Pin image digest

Nếu GHCR package private, đăng nhập bằng quyền chỉ đọc package:

```bash
sudo docker login ghcr.io -u YOUR_GITHUB_USERNAME
```

Không dùng token có quyền publish/delete trên VPS. Tạo file nguồn image list trên VPS:

```bash
sudo nano /etc/superstore/images.sources.env
```

Khai báo image/tag cần pin, thay bằng tag đã publish/chọn cho release:

```dotenv
API_IMAGE=ghcr.io/YOUR_OWNER/YOUR_REPOSITORY-api:YOUR_RELEASE_TAG
REDIS_IMAGE=redis:YOUR_APPROVED_TAG
```

Tạo lockfile chung; script pull image và đổi tag thành digest:

```bash
sudo bash bin/pin-images.sh \
  /etc/superstore/images.sources.env \
  /etc/superstore/images.lock.env
```

`pin-images.sh` từ chối ghi đè lockfile đã tồn tại. Không xóa lockfile đang dùng chỉ để chạy lại lệnh; cần quy trình thay đổi image có chủ đích.

## 6. Cấu hình Nginx và cấp chứng chỉ

Tạo thư mục nhận file xác minh ACME. Các token bên trong chỉ tồn tại tạm thời trong lúc xác minh:

```bash
sudo install -d -m 755 \
  /var/www/certbot/.well-known/acme-challenge
```

Cài cấu hình bootstrap HTTP:

```bash
sudo bash bin/install-nginx.sh bootstrap
```

Sau khi DNS `A` trỏ đúng VPS và cổng 80 truy cập được, cấp chứng chỉ bằng webroot:

```bash
sudo /snap/bin/certbot certonly \
  --webroot \
  --webroot-path /var/www/certbot \
  --domain "$(sudo sed -n 's/^API_DOMAIN=//p' /etc/superstore/stack.env)"
```

Khi chứng chỉ đã tồn tại, cài cấu hình HTTPS:

```bash
sudo bash bin/install-nginx.sh https
sudo nginx -t
sudo systemctl status nginx --no-pager
```

## 7. Triển khai backend

Trước khi chạy, xác nhận release SHA và image digest đã khớp với bản đã publish. Lệnh deploy cần chạy bằng `sudo` vì script quản lý Docker và cấu hình hệ thống:

```bash
sudo bash "/opt/superstore/releases/$RELEASE_SHA/deploy/production/bin/deploy.sh" \
  "$RELEASE_SHA" \
  "ghcr.io/YOUR_OWNER/YOUR_REPOSITORY-api@sha256:YOUR_IMAGE_DIGEST"
```

Script kiểm tra cấu hình, kéo image, chạy API/Redis, đợi health check và kiểm tra HTTPS. Nếu bước deploy lỗi, nó cố gắng khôi phục release trước đó. Kiểm tra public liveness:

```bash
curl --fail "https://$(sudo sed -n 's/^API_DOMAIN=//p' /etc/superstore/stack.env)/api/health/live"
```

Readiness (`/api/health/ready`) chỉ kiểm tra được nội bộ; xem mục 9.2.

> **Kiểm tra trước khi chạy:** `deploy.sh` hiện tìm `compose.yaml`, trong khi file trong repo là `compose.yml`. Cần đồng bộ tên này trong code trước; nếu không, deploy sẽ dừng ở bước kiểm tra release.

## 8. Tạo và quản lý staff production

Chỉ tạo staff sau khi backend đã deploy thành công. Account được lưu bền vững trong `/opt/superstore/data/staff/internal_users.db`. Đảm bảo domain email nằm trong `INTERNAL_EMAIL_DOMAINS` của `/etc/superstore/app.env`.

Đặt đường dẫn Compose script của release hiện hành:

```bash
COMPOSE_SCRIPT="/opt/superstore/releases/$RELEASE_SHA/deploy/production/bin/compose.sh"
```

### 8.1. Tạo admin

Mật khẩu được CLI hỏi tương tác, không ghi vào command history:

```bash
sudo bash "$COMPOSE_SCRIPT" exec api \
  python -m scripts.manage_staff add admin@company.com \
  --name "Production Admin" \
  --role admin
```

Nếu email đã tồn tại, lệnh báo lỗi thay vì ghi đè. Chỉ thêm `--replace` khi chủ đích cập nhật account đó.

### 8.2. Liệt kê và các lệnh quản lý

Kiểm tra account vừa tạo; xác nhận email, role `admin` và `ACTIVE=True`:

```bash
sudo bash "$COMPOSE_SCRIPT" exec api \
  python -m scripts.manage_staff list
```

Các lệnh khác của `scripts.manage_staff`:

```bash
# Tạo staff: role hợp lệ gồm admin, analyst, ceo, cfo, sales, marketing, warehouse, plant
sudo bash "$COMPOSE_SCRIPT" exec api \
  python -m scripts.manage_staff add user@company.com \
  --name "Staff Name" --role marketing

# Đổi role
sudo bash "$COMPOSE_SCRIPT" exec api \
  python -m scripts.manage_staff role user@company.com cfo

# Đổi password (CLI hỏi password hai lần)
sudo bash "$COMPOSE_SCRIPT" exec api \
  python -m scripts.manage_staff password user@company.com

# Tạm khóa / kích hoạt lại staff
sudo bash "$COMPOSE_SCRIPT" exec api \
  python -m scripts.manage_staff disable user@company.com
sudo bash "$COMPOSE_SCRIPT" exec api \
  python -m scripts.manage_staff enable user@company.com
```

Không xóa trực tiếp SQLite đang được container mount.

## 9. Kiểm tra production và xem log

Thay `api.your-domain.com` bằng domain thật. Kiểm tra public chạy từ máy có thể truy cập Internet; readiness nội bộ và log chạy trên VPS.

### 9.1. Liveness và HTTP → HTTPS

```bash
curl -i \
  https://api.your-domain.com/api/health/live
```

Kỳ vọng `200` và JSON có `status: "ok"`, `release` là commit SHA đã deploy:

```json
{
  "status": "ok",
  "release": "COMMIT_SHA_DA_DEPLOY"
}
```

HTTP phải chuyển hướng sang HTTPS:

```bash
curl -I \
  http://api.your-domain.com/api/health/live
```

Kỳ vọng `308` và header `Location` trỏ tới URL HTTPS tương ứng.

### 9.2. Xác nhận các endpoint nội bộ bị chặn

Các URL sau phải trả `404` khi gọi qua domain public:

```bash
curl -i https://api.your-domain.com/metrics
curl -i https://api.your-domain.com/api/health/ready
curl -i https://api.your-domain.com/docs
curl -i https://api.your-domain.com/openapi.json
```

Readiness chỉ kiểm tra từ VPS qua cổng loopback của API:

```bash
curl -i \
  http://127.0.0.1:8000/api/health/ready
```

Kỳ vọng `200` và các giá trị `status: "ready"`, `staff_store: true`, `redis: true`.

Không có API key/session hợp lệ thì staff endpoint phải từ chối (`401` hoặc `403`):

```bash
curl -i \
  https://api.your-domain.com/api/staff/me
```

### 9.3. Xác nhận API port không public

Chạy từ máy bên ngoài VPS. Kết nối tới port `8000` phải thất bại vì API chỉ bind vào `127.0.0.1`:

```bash
curl \
  --connect-timeout 5 \
  http://YOUR_VPS_IP:8000/api/health/live
```

### 9.4. Xem log trên VPS

```bash
sudo tail -n 30 /opt/superstore/logs/api/http.log
sudo tail -n 30 /var/log/nginx/superstore-access.log
sudo tail -n 30 /var/log/nginx/superstore-error.log
```
