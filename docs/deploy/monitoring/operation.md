# Monitoring — Operation

## 0. Phase 0 - Kiểm tra container, /metrics, Prometheus targets, file log và Grafana datasource

### 0.1. Kiểm tra container và cấu hình

```bash
COMPOSE=/opt/superstore/current/deploy/production/bin/compose.sh
sudo bash "$COMPOSE" ps
```

**Mong đợi:** `api`, `redis`, `redis-exporter`, `prometheus`, `node-exporter`,
`alloy`, `loki`, `minio`, `grafana` ở trạng thái `Up`; `api` và `redis` healthy.

Kuma dùng stack riêng; Alertmanager chưa được cài:

```bash
sudo docker ps -a --format '{{.Names}}\t{{.Status}}' |
  grep -Ei 'alertmanager|kuma' || true
```

**Trước Phase 7:** có Uptime Kuma `Up`, chưa có Alertmanager. **Sau Phase 7:**
cả hai phải `Up`. VPS không cài `rg`; dùng `grep` trong các lệnh ở tài liệu này.

### 0.2. Kiểm tra metrics và Prometheus

Gọi route không bị loại khỏi metrics, rồi đọc mẫu FastAPI:

```bash
curl -i -sS http://127.0.0.1:8000/api/staff/me
curl -i -fsS http://127.0.0.1:8000/metrics |
  grep -E '^HTTP/|^[Cc]ontent-[Tt]ype:|^superstore_http_requests_total|^superstore_http_request_duration_seconds_(bucket|sum|count)' |
  head -20
```

**Mong đợi:** request thiếu xác thực có thể trả `401`/`403`; `/metrics` có
Counter và ba loại mẫu Histogram `_bucket`, `_sum`, `_count`. Health và
`/metrics` không làm Counter tăng.

Kiểm tra bốn scrape target:

```bash
curl -i -fsSG http://127.0.0.1:9090/api/v1/query \
  --data-urlencode 'query=up'
```

**Mong đợi:** `fastapi=1`, `redis=1`, `node=1`, `prometheus=1`. `up=1` xác nhận
scrape thành công; nó chưa xác nhận nội dung từng metric đúng.

Kiểm tra Redis và dữ liệu VPS:

```bash
for query in \
  'redis_up' \
  'count(node_cpu_seconds_total{job="node",mode="idle"})' \
  'count(node_memory_MemAvailable_bytes{job="node"})' \
  'count(node_filesystem_avail_bytes{job="node"})' \
  'count(node_network_receive_bytes_total{job="node"})'; do
  printf '%s: ' "$query"
  curl -i -fsSG http://127.0.0.1:9090/api/v1/query \
    --data-urlencode "query=$query"
done
```

**Mong đợi:** `redis_up=1`; các truy vấn Node trả số lớn hơn `0`. Không dùng
`count(node_cpu_seconds_total)` để kết luận số CPU vì metric có nhiều `mode`.

### 0.3. Kiểm tra đường đi của logs

```bash
sudo ls -lh \
  /opt/superstore/logs/api/http.log \
  /opt/superstore/logs/api/application.log \
  /var/log/nginx/superstore-access.log \
  /var/log/nginx/superstore-error.log
sudo bash "$COMPOSE" logs --tail=30 alloy loki grafana
```

**Mong đợi:** các file tồn tại; `superstore-error.log` có thể rỗng. Alloy đọc
`http.log` và `superstore-access.log`.

| Thành phần | Log cần chú ý                    | Kết quả                             |
| ---------- | -------------------------------- | ----------------------------------- |
| Alloy      | `Alloy is running`               | Đã khởi chạy                        |
| Alloy      | `start tailing file ... nginx`   | Đã bắt đầu theo dõi log Nginx       |
| Alloy      | `start tailing file ... fastapi` | Đã bắt đầu theo dõi log API         |
| Loki       | `finished uploading table`       | Đang thực hiện tác vụ quản lý index |
| Grafana    | `status=ok dsName=Prometheus`    | Truy vấn Prometheus thành công      |

Tạo một request mới qua Nginx:

```bash
API_DOMAIN=api.gymtech.id.vn
sudo stat -c '%y %s' /opt/superstore/logs/api/http.log
curl -i -sS "https://$API_DOMAIN/api/staff/me"
sudo stat -c '%y %s' /opt/superstore/logs/api/http.log
```

**Mong đợi:** `401`/`403` vì không gửi thông tin xác thực; request vẫn xuất hiện
trong FastAPI HTTP log và Nginx access log; thời gian sửa file `http.log` tăng.
Không dùng health route vì FastAPI đã loại route này khỏi HTTP log/metrics.

Trên **Mac**, mở tunnel và giữ terminal này chạy:

```bash
ssh -N \
  -L 3001:127.0.0.1:3001 \
  -L 9090:127.0.0.1:9090 \
  -L 3002:127.0.0.1:3002 \
  deploy@YOUR_VPS_IP
```

Mở `http://localhost:3001` → **Grafana Explore**:

- Datasource **Prometheus**: truy vấn `up` → bốn job có giá trị `1`.
- Datasource **Loki**: chọn _Last 15 minutes_, truy vấn `{service="fastapi"}`
  và `{service="nginx"}` → thấy log của request vừa gọi.
- `http://localhost:3002` → Uptime Kuma mở được; kiểm tra monitor public
  health endpoint và lần check gần nhất trong giao diện.

Nếu Loki không có log mới, kiểm tra lại file trên VPS, mount trong Compose,
`config.alloy`, rồi `compose.sh logs alloy loki` theo đúng thứ tự đó.

Nếu **Nginx có log nhưng FastAPI không có**, trước tiên xác nhận request không
phải `/api/health/live`, `/api/health/ready`, `/metrics` hoặc URL bị Nginx chặn.
Sau request `/api/staff/me` ở trên, kiểm tra dòng cuối của file nguồn:

```bash
sudo tail -n 3 /opt/superstore/logs/api/http.log
```

**Mong đợi:** có dòng mới với route `/staff/me` (route nội bộ của FastAPI) và
status `401`/`403`.
Nếu file không có dòng mới, kiểm tra API và `APP_LOG_DIR`; nếu file có dòng mới
nhưng Grafana rỗng, kiểm tra log Alloy/Loki, nhãn `service="fastapi"` và thời
gian truy vấn trong Explore.

### 0.4. Kiểm tra Grafana SMTP và phần chưa cài

Kiểm tra **sự hiện diện** của biến SMTP mà không in giá trị:

```bash
sudo bash "$COMPOSE" exec -T grafana sh -c \
  'test -n "$GF_SMTP_USER" && test -n "$GF_SMTP_PASSWORD" && test -n "$GF_SMTP_FROM_ADDRESS" && echo "SMTP variables present"'
```

**Mong đợi:** `SMTP variables present`. Đây chỉ là kiểm tra cấu hình; SMTP chỉ
đạt **DONE** khi gửi email thử từ Grafana thành công.

## 1. Phase 1 — xác minh metrics

Chạy trên **VPS**. Các lệnh `curl -i` hiển thị HTTP status, headers và JSON;
đọc số ở `data.result[].value[1]`. Mọi truy vấn Prometheus phải trả `200` và
`status: "success"`.

### 1.1. Counter tăng sau request thật

Đọc Counter trước, gọi ba request không bị loại khỏi metrics, chờ ít nhất một
lượt scrape (cấu hình hiện tại là 15 giây), rồi đọc lại:

```bash
curl -i -fsSG http://127.0.0.1:9090/api/v1/query \
  --data-urlencode 'query=sum(superstore_http_requests_total{method="GET",route="/staff/me"})'

for attempt in 1 2 3; do
  curl -i -sS http://127.0.0.1:8000/api/staff/me
done

sleep 20

curl -i -fsSG http://127.0.0.1:9090/api/v1/query \
  --data-urlencode 'query=sum(superstore_http_requests_total{method="GET",route="/staff/me"})'
```

**Mong đợi:** request trả `401`/`403`; giá trị Counter sau lớn hơn trước ít nhất
`3`. Nếu có lưu lượng đồng thời, chênh lệch có thể lớn hơn `3`. Kiểm tra nhãn
`method`, `route`, `status` trực tiếp trong `/metrics`:

```bash
curl -i -fsS http://127.0.0.1:8000/metrics |
  grep -E '^HTTP/|^superstore_http_requests_total\{.*route="/staff/me"'
```

**Mong đợi:** nhãn `route="/staff/me"` và `status` đúng HTTP response; route
động dùng mẫu đường dẫn, không chứa ID cụ thể.

### 1.2. Histogram và đơn vị

```bash
for query in \
  'sum(superstore_http_request_duration_seconds_count{method="GET",route="/staff/me"})' \
  'sum(superstore_http_request_duration_seconds_bucket{method="GET",route="/staff/me",le="+Inf"})' \
  'sum(superstore_http_request_duration_seconds_sum{method="GET",route="/staff/me"})'; do
  printf '\n%s\n' "$query"
  curl -i -fsSG http://127.0.0.1:9090/api/v1/query \
    --data-urlencode "query=$query"
done
```

**Mong đợi:** `_count` bằng bucket `+Inf`; `_sum` lớn hơn `0` và tính bằng
**giây**. Trong `core/observability.py`, thời gian từ `time.perf_counter()`
được đưa thẳng vào Histogram; `http.log` ghi cùng thời gian theo mili giây.

### 1.3. VPS và Redis

```bash
for query in \
  'redis_up{job="redis"}' \
  'redis_memory_used_bytes{job="redis"}' \
  'count(node_cpu_seconds_total{job="node",mode="idle"})' \
  'node_memory_MemAvailable_bytes{job="node"}' \
  'node_filesystem_avail_bytes{job="node",mountpoint="/"}' \
  'rate(node_network_receive_bytes_total{job="node",device!="lo"}[5m])'; do
  printf '\n%s\n' "$query"
  curl -i -fsSG http://127.0.0.1:9090/api/v1/query \
    --data-urlencode "query=$query"
done
```

**Mong đợi:** `redis_up=1`; các truy vấn còn lại có `data.result` không rỗng.
Memory và disk dùng byte; network dùng byte/giây và có thể bằng `0` khi rảnh.
`count(...mode="idle")` đếm CPU được export, khác với đếm tất cả `mode`.
Nếu một truy vấn rỗng, kiểm tra nhãn thực tế của metric trong Prometheus trước
khi kết luận exporter lỗi.

Ghi các giá trị trước/sau, thời gian kiểm tra và kết quả vào
[Discovery Result](discovery_result.md). Không đánh dấu Phase 1 DONE chỉ vì
`up=1` hoặc vì metric có tên trong `/metrics`.

## 2. Phase 2 — đối chiếu log theo request ID

Chạy trên **VPS**, trừ bước Grafana Explore thực hiện trên Mac qua SSH tunnel ở
§0.3. Dùng request không cần API key để không đưa secret vào lệnh kiểm tra.

### 2.1. Nối response với hai file nguồn

```bash
COMPOSE=/opt/superstore/current/deploy/production/bin/compose.sh
curl -i -sS https://api.gymtech.id.vn/api/staff/me
```

Ghi lại `x-request-id` từ response rồi thay giá trị dưới đây:

```bash
REQUEST_ID=PASTE_X_REQUEST_ID_HERE
sudo grep -F "$REQUEST_ID" /opt/superstore/logs/api/http.log | tail -n 1
sudo grep -F "$REQUEST_ID" /var/log/nginx/superstore-access.log | tail -n 1
```

**Mong đợi:** cùng một ID ở cả hai file. FastAPI ghi route `/staff/me`, status
`401`/`403` và `duration_ms`; Nginx ghi route `/api/staff/me`, cùng status và
`duration`. Nếu Nginx có dòng nhưng FastAPI không có, kiểm tra request có đến
upstream hay bị Nginx chặn; các health route không tạo FastAPI HTTP log.

### 2.2. Tìm đúng request trong Loki

Trên Mac, mở Grafana Explore → datasource **Loki** → _Last 15 minutes_. Thay
`REQUEST_ID` bằng ID vừa ghi và chạy hai truy vấn:

```logql
{service="fastapi"} |= "REQUEST_ID"
{service="nginx"} |= "REQUEST_ID"
```

**Mong đợi:** mỗi truy vấn có dòng chứa cùng ID và status như hai file nguồn.
Sau khi deploy cấu hình Alloy mới, có thể lọc hẹp thêm `log_type="http"` hoặc
`log_type="access"`. Các log cũ chưa có nhãn `log_type` vẫn tìm được bằng hai
truy vấn trên.

Nếu file nguồn có dòng nhưng Loki không có, kiểm tra khoảng thời gian của
Explore, log Alloy/Loki và mount file theo thứ tự:

```bash
sudo bash "$COMPOSE" logs --tail=60 alloy loki
sudo docker inspect --format \
  '{{range .Mounts}}{{println .Source "->" .Destination}}{{end}}' \
  "$(sudo bash "$COMPOSE" ps -q alloy)"
```

### 2.3. Kiểm tra hai nguồn log bổ sung

Sau đó gọi health để tạo dòng mới trong **application.log**; route này không
tạo FastAPI `http.log`:

```bash
curl -i -sS http://127.0.0.1:8000/api/health/live
sudo tail -n 3 /opt/superstore/logs/api/application.log
sudo bash "$COMPOSE" logs --tail=30 alloy
```

Trong Grafana Explore, truy vấn `{service="fastapi",log_type="application"}`.
**Mong đợi:** thấy log ứng dụng vừa tạo. Truy vấn
`{service="nginx",log_type="error"}` chỉ có kết quả khi Nginx thực sự ghi lỗi;
file rỗng không phải lỗi kiểm tra.

## 3. Phase 3 — kiểm tra thư viện PromQL và LogQL

Truy vấn dùng lại nằm trong [PromQL & LogQL Query Library](promql_logql_library.md).
Chạy trên **VPS**; `curl -i` hiển thị HTTP status và JSON để phát hiện cả lỗi
cú pháp lẫn kết quả rỗng.

### 3.1. Kiểm tra PromQL

Gọi một route được tính trong metrics, đợi Prometheus scrape, rồi chạy mẫu
truy vấn API, Redis và target:

```bash
for attempt in 1 2 3; do
  curl -i -sS http://127.0.0.1:8000/api/staff/me
done
sleep 20

for query in \
  'sum(rate(superstore_http_requests_total{job="fastapi"}[5m]))' \
  'histogram_quantile(0.95, sum by (le) (rate(superstore_http_request_duration_seconds_bucket{job="fastapi"}[5m])))' \
  'redis_up{job="redis"}' \
  'up{job=~"fastapi|redis|node|prometheus"}'; do
  printf '\n%s\n' "$query"
  curl -i -fsSG http://127.0.0.1:9090/api/v1/query \
    --data-urlencode "query=$query"
done
```

**Mong đợi:** HTTP `200`, JSON `status="success"`; API rate dương sau request,
P95 có giá trị tính bằng giây, `redis_up=1`, bốn target `up=1`. Chạy tiếp các
query VPS/Redis trong thư viện và kiểm tra đơn vị. Query HTTP 5xx có thể rỗng
khi chưa từng có lỗi 5xx; không tạo lỗi production chỉ để có kết quả.

### 3.2. Kiểm tra LogQL

Trên Mac, mở SSH tunnel ở §0.3 rồi vào `http://localhost:3001` → **Explore** →
chọn datasource **Loki**. Dán **từng truy vấn** sau vào ô LogQL và bấm Run query:

```logql
{service="fastapi",log_type="http"} | json | status >= 500
{service="nginx",log_type="access"} | json | status >= 500
{service="nginx",log_type="error"} |~ "(?i)timed out|timeout"
```

Đây là `LOG-03`–`LOG-05` ở mục 3 của [Query Library](promql_logql_library.md).
Chọn khoảng thời gian phù hợp, ví dụ _Last 24 hours_. **Mong đợi:** truy vấn
hợp lệ; kết quả có thể rỗng nếu không xảy ra 5xx/timeout. Để chắc chắn Loki có
log, chạy `{service="fastapi"}` hoặc truy vấn theo `request_id` ở §2.2.

Nếu `log_type` không có kết quả, xác nhận release trên VPS đã chứa
`config.alloy` mới và Alloy đã được tạo lại; các log cũ không có nhãn này.
Ghi từng query ID, giá trị hoặc `NO_DATA`, thời gian và lỗi cú pháp nếu có vào
[Discovery Result](discovery_result.md). Không dùng truy vấn chưa kiểm chứng
để tạo alert ở Phase 4.

## 4. Phase 4 — baseline, ngưỡng và alert rules

### 4.1. Đo baseline trên production

Trước tiên tạo các Kuma monitor và chạy hai collection bằng **Newman timer**
theo [Synthetic Baseline §6–7](synthetic_baseline.md), hoặc dùng Postman Cloud
Monitor. Chỉ bật lịch một trong hai runner để tránh chạy trùng. Public đo
khả dụng; Staff Journey tạo traffic dashboard cho FastAPI metrics. Khi chưa
có người dùng thật, baseline API chỉ phản ánh traffic synthetic.

Chỉ bắt đầu đếm khi Kuma và runner theo lịch đều pass. Qua SSH tunnel ở §0.3,
mở Grafana Explore → **Prometheus** và chạy API-01–05, VPS-01–03, REDIS-02
trong [Query Library](promql_logql_library.md). Ghi số lượt thực tế, số mẫu,
P95, 5xx, mức thường gặp và đỉnh vào [Threshold, SLI/SLO](threshold_sli_slo.md)
theo ba mốc:

1. **Sau 1 ngày:** xem _Last 24 hours_; dùng ngưỡng khả dụng và giới hạn tài
   nguyên tạm, theo dõi API mà chưa suy tỷ lệ lỗi/P95 từ mẫu ít.
2. **Sau 14 ngày:** xem _Last 14 days_; đủ số mẫu mới chọn ngưỡng API theo
   baseline thực và rà lại giới hạn tài nguyên.
3. **Sau 30 ngày:** xem _Last 30 days_; thay baseline 14 ngày bằng số liệu mới,
   kiểm tra traffic theo ngày/tuần và chốt ngưỡng. Nếu retention `5GB` làm mất
   dữ liệu sớm, dùng báo cáo đã lưu hoặc kéo dài quan sát.

Mỗi mốc ghi ngưỡng cũ → mới và bằng chứng. Thiếu dữ liệu thì giữ ngưỡng trước,
không điền `0` hoặc tự đánh dấu đã triển khai.

Ghi vào [file Excel kết quả đo](monitoring_baseline_results.xlsx) theo thứ tự:
điền `T0` và lượt chạy thực tế ở **Lịch chạy**, điền chỉ số tổng quát ở
**Chỉ số chung**, rồi điền request/5xx/P95 của từng route ở **Theo route**.

Với **CPU cao nhất**, dùng `BASE-06` ở chế độ **Instant** tại đúng cuối khoảng
đo; panel CPU VPS chỉ dùng xem diễn biến. `BASE-06` trả tỷ lệ `0–1`, còn panel
hiển thị `%` (ví dụ `0,16` = `16%`).

Ô vàng là ô nhập; ô độ phủ và ngưỡng P95 được tính tự động. Đính kèm link
Grafana/Prometheus/Kuma trong cột **Bằng chứng**.

Trong sheet **Chỉ số chung**, `F` là số đo, `G` là rule đang chạy, `H` là
ngưỡng đề xuất và `I` là quyết định duyệt. Mốc ngày 1 chỉ quan sát API 5xx/P95;
ngưỡng P95 chờ baseline 14 ngày. Nếu ghi **P95 5 phút cao nhất / 24h**, dùng
`API-08` ở chế độ **Instant** tại giờ chốt. `256 MiB` là giới hạn Redis; mức
cảnh báo tạm là `153,6 MiB`, nghiêm trọng `217,6 MiB` theo
[Threshold, SLI/SLO](threshold_sli_slo.md). Ngưỡng đề xuất chưa tự động
trở thành alert trên VPS.

### 4.2. Kiểm tra rule trước khi chạy

Sau khi release chứa `prometheus/rules/availability.yml` đã có trên VPS:

```bash
COMPOSE=/opt/superstore/current/deploy/production/bin/compose.sh
sudo bash "$COMPOSE" config --quiet
sudo bash "$COMPOSE" run --rm --no-deps --entrypoint /bin/promtool \
  prometheus check rules /etc/prometheus/rules/availability.yml
sudo bash "$COMPOSE" run --rm --no-deps --entrypoint /bin/promtool \
  prometheus check config /etc/prometheus/prometheus.yml
```

**Mong đợi:** cả hai lệnh `promtool` trả mã `0`. PR CI còn chạy
`promtool test rules` với dữ liệu giả để kiểm tra trạng thái Pending → Firing →
Inactive; test này không tác động production. Để nạp bind mount và config mới
vào Prometheus:

```bash
sudo bash "$COMPOSE" up -d --force-recreate prometheus
```

Volume `prometheus_data` được giữ lại khi tạo lại container.

### 4.3. Xác nhận rule đã được nạp

```bash
curl -i -fsS 'http://127.0.0.1:9090/api/v1/rules?type=alert'
curl -i -fsS 'http://127.0.0.1:9090/api/v1/alerts'
```

**Mong đợi:** `superstore-availability` có hai rule
`SuperstoreScrapeTargetDown` và `SuperstoreRedisUnavailable`. Khi các service
khỏe, chúng ở trạng thái Inactive. `up=0` nghĩa là Prometheus không scrape
được target; `redis_up=0` với `up{job="redis"}=1` nghĩa là exporter chạy nhưng
không kết nối được Redis. Chỉ thử tạo lỗi trên staging, không dừng service
production để kiểm tra rule.

Ghi kết quả thực vào [Discovery Result](discovery_result.md). Hai rule này chưa
gửi email vì Alertmanager thuộc Phase 7. Các ngưỡng 5xx, P95, CPU, RAM và disk
chỉ thêm sau khi hoàn tất §4.1 và chọn giá trị trong
[Threshold, SLI/SLO](threshold_sli_slo.md).

### 4.4. Lưu bản dashboard

Hai bản JSON đang dùng: [DevOps Operations](dashboard_exports/devops_operations.json)
và [Dev Troubleshooting](dashboard_exports/dev_troubleshooting.json). Chúng là
bản lưu tài liệu, **không tự nạp** từ thư mục `docs`. Khi cần khôi phục, vào
Grafana → Dashboards → New → Import, tải JSON và kiểm tra UID trước khi chọn
**Import (Overwrite)**. Dashboard hiện tại vẫn được Grafana lưu trong volume
`grafana_data`.

## 5. Phase 5 — Grafana dashboard

Trên Mac, mở SSH tunnel ở §0.3 rồi vào `http://localhost:3001`. Hai dashboard
theo vai trò đã có bản export ở §4.4; dashboard Newman được nạp tự động từ
`deploy/production/grafana/dashboards/newman-synthetic.json`.

| Người xem | Dashboard                            | Đọc theo thứ tự                                                                                  |
| --------- | ------------------------------------ | ------------------------------------------------------------------------------------------------ |
| DevOps    | **Superstore - Devops Operations**   | Bốn scrape target → Newman public/staff và giây từ lần cuối → Redis → API 5xx/P95 → CPU/RAM/disk |
| Dev       | **Superstore — Dev Troubleshooting** | Route/status có traffic → 5xx/P95 theo route → FastAPI/Nginx HTTP log → application ERROR        |

use [Query Library](promql_logql_library.md) để truy vấn và vẽ pannel

### 5.1. Điều tra theo dấu hiệu

Chọn đúng khoảng thời gian xảy ra lỗi. Truy vấn trong **Grafana Explore**;
PromQL dùng datasource Prometheus, LogQL dùng Loki. Có thể mở rộng từ các ID
trong [Query Library](promql_logql_library.md).

```text
No data
→ kiểm tra time range/datasource → DevOps: Scrape targets
→ `up{job=~"fastapi|redis|node|prometheus"}`
→ up=0: kiểm tra target tương ứng; tất cả up=1: xem Newman freshness và traffic.

Newman FAIL hoặc lần chạy cuối quá cũ
→ DevOps: Newman public/staff → `newman_last_run_success{mode="timer"}`
→ `time() - newman_last_run_timestamp_seconds{mode="timer"}`
→ xem timer/journal của collection tương ứng.

Dashboard báo 5xx/502
→ DevOps: API 5xx/24h → Dev: API 5xx theo route
→ Loki: `{service="fastapi",log_type="http"} | json | status >= 500`
→ đối chiếu Nginx bằng cùng `x-request-id` (§2.2).

Dashboard chậm
→ DevOps: P95 API → Dev: P95 theo route (API-07)
→ đối chiếu Redis RAM, CPU/RAM/disk VPS (REDIS-02, VPS-01–03).

Redis/target không khỏe
→ DevOps: Redis + Scrape targets (`redis_up{job="redis"}`, `up`)
→ Redis=0 nhưng up=1: exporter không tới Redis; up=0: Prometheus không scrape được.
```

Nếu Newman FAIL nhưng FastAPI 5xx vẫn bằng `0`, kiểm tra thêm Next.js/Vercel:
request có thể chưa đến FastAPI. `No data` khác `0`; xác nhận có traffic bằng
**Request theo route / 24h** trước khi kết luận hệ thống khỏe. Lệnh kiểm tra
timer nằm ở [Synthetic Baseline §6–7](synthetic_baseline.md).

## 6. Phase 6 — SLI, SLO và error budget

Đọc [Threshold, SLI/SLO](threshold_sli_slo.md) trước khi đặt target. Trong
Grafana Explore → Prometheus, chạy `SLI-01`–`SLI-05` ở
[Query Library §5](promql_logql_library.md) với cửa sổ 24 giờ; ghi mẫu số,
availability, lỗi 5xx, latency compliance và Newman PASS/coverage. Lặp lại
ở mốc 14 ngày và 30 ngày khi có đủ lịch sử.

Ghi vào sheet **SLI SLO** của [file kết quả đo](monitoring_baseline_results.xlsx):
`C` = SLI-02 (request hợp lệ), `D` = SLI-03 (5xx), `F` = SLI-04 (tỷ lệ
Dashboard đạt `T`), `G` = SLI-05 (Staff PASS), `M` = bằng chứng. `E` tự tính
availability; `H` lấy Staff coverage từ **Lịch chạy**. Nhập tỷ lệ dạng `0–1`.
Sau đủ 30 ngày, chốt target ở `B16:B18`, `T` (giây) ở `C17`, rồi ghi `Có`
vào `E16:E18` khi đã xác minh đủ dữ liệu. Ngày 1/14 có thể đặt `I6:I7`
`=$B$16` sau khi chốt API target; `J:L` tự tính budget cho từng khoảng đo.

## 7. Phase 7 — chuyển cảnh báo và xử lý sự cố

Alertmanager nằm trong **cùng** `deploy/production/compose.yml` và dùng chung
`/etc/superstore/images.lock.env`. Chuẩn bị cấu hình dưới đây **trước khi
merge/deploy** release có Alertmanager: `deploy.sh` sẽ kiểm tra config, password,
image và readiness. Chưa có email thực nhận thì chưa đánh dấu Phase 7 PASS.

### 7.1. Chuẩn bị trên Mac và VPS

Trên **Mac**, chép file mẫu không chứa mật khẩu lên VPS:

```bash
scp deploy/production/alertmanager/config.yml.example \
  deploy@YOUR_VPS_IP:/tmp/superstore-alertmanager-config.yml
```

Trên **VPS**, cài file, sửa địa chỉ SMTP From/User/To và nhập app password
vào file riêng. Không đưa hai file thật vào Git:

```bash
sudo install -d -m 750 /etc/superstore/alertmanager
sudo install -o root -g 65534 -m 640 \
  /tmp/superstore-alertmanager-config.yml \
  /etc/superstore/alertmanager/config.yml
sudo install -o root -g 65534 -m 640 \
  /dev/null /etc/superstore/alertmanager/smtp_password
sudo nano /etc/superstore/alertmanager/config.yml
sudo nano /etc/superstore/alertmanager/smtp_password
sudo unlink /tmp/superstore-alertmanager-config.yml
```

Kiểm tra file config không còn `example.invalid` và password không rỗng. Thêm
`ALERTMANAGER_IMAGE=quay.io/prometheus/alertmanager:v0.35.0` vào
`/etc/superstore/images.source.env`; [file mẫu](../../../deploy/production/images.source.env.example)
trong repo ghi đủ các image. Pin **toàn bộ** source thành lock ứng viên mới:

```bash
sudo nano /etc/superstore/images.source.env
candidate="/etc/superstore/images.lock.candidate.$(date +%Y%m%d%H%M%S).env"
sudo bash /opt/superstore/current/deploy/production/bin/pin-images.sh \
  /etc/superstore/images.source.env "$candidate"
sudo diff -u /etc/superstore/images.lock.env "$candidate"
```

`diff` cần cho thấy key `ALERTMANAGER_IMAGE` mới. Nếu digest image khác cũng
đổi, kiểm tra trước khi tiếp tục. Sau khi duyệt:

```bash
sudo install -o root -g root -m 600 \
  "$candidate" /etc/superstore/images.lock.env
sudo unlink "$candidate"
```

Release **mới** sẽ copy lock chung vào `releases/<SHA>/images.lock.env`; lock
của release cũ không tự ghi đè. Backup hiện có lưu lock chung và hai file
Alertmanager sau khi chúng được tạo.

### 7.2. Kiểm tra sau deploy

`deploy.sh` chạy `amtool check-config`, khởi động toàn bộ Compose và đợi
Alertmanager ready. Trên VPS kiểm tra thêm:

```bash
COMPOSE=/opt/superstore/current/deploy/production/bin/compose.sh
sudo bash "$COMPOSE" ps alertmanager prometheus
curl -i -fsS http://127.0.0.1:9093/-/ready
curl -i -fsS http://127.0.0.1:9090/api/v1/rules
curl -i -fsS http://127.0.0.1:9090/api/v1/alertmanagers
```

Mong đợi: readiness `200`, hai rule được nạp, đích `alertmanager:9093` trong
`activeAlertmanagers`. Nếu sửa config SMTP **sau deploy**, chạy
`sudo bash "$COMPOSE" up -d --force-recreate alertmanager`, rồi kiểm tra lại.

### 7.3. Thử email và ghi incident

Dùng rule thử có kiểm soát trên staging; không dừng API/Redis production để
kích hoạt cảnh báo. Lưu bằng chứng theo thứ tự: rule `Pending` → `Firing` →
Alertmanager nhận đúng receiver → email nhận được → `Resolved` và email
resolved. Cập nhật [Discovery Result](discovery_result.md). Khi có sự cố thật,
phân loại P1 (diện rộng), P2 (nhiều route), P3 (một route), P4 (lỗi nhỏ);
ghi thời điểm bắt đầu/phát hiện/xác nhận/phục hồi để tính MTTD, MTTA, MTTR.
