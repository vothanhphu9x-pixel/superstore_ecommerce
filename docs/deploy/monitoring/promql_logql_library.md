# Monitoring — PromQL & LogQL Query Library

Các truy vấn dưới đây dùng cho **metrics/log vận hành**, không đo doanh thu hay
đơn hàng. Chạy PromQL trong Grafana Explore → Prometheus hoặc Prometheus trên VPS;
chạy LogQL trong Grafana Explore → Loki. Khoảng nhìn mặc định của rate là **5 phút**.
Trước khi dùng cho dashboard/alert, kiểm tra tên metric và nhãn trên production
theo [Operation §3](operation.md).

## 1. API — PromQL

| ID     | Chỉ số                         | Truy vấn                                                                                                                                                         | Đơn vị       |
| ------ | ------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------ |
| API-01 | Request rate                   | `sum(rate(superstore_http_requests_total{job="fastapi"}[5m]))`                                                                                                   | request/giây |
| API-02 | HTTP 5xx rate                  | `sum(rate(superstore_http_requests_total{job="fastapi",status=~"5.."}[5m]))`                                                                                     | request/giây |
| API-03 | HTTP 5xx percentage            | `100 * (sum(rate(superstore_http_requests_total{job="fastapi",status=~"5.."}[5m])) or vector(0)) / sum(rate(superstore_http_requests_total{job="fastapi"}[5m]))` | %            |
| API-04 | P95 latency                    | `histogram_quantile(0.95, sum by (le) (rate(superstore_http_request_duration_seconds_bucket{job="fastapi"}[5m])))`                                               | giây         |
| API-05 | P99 latency                    | `histogram_quantile(0.99, sum by (le) (rate(superstore_http_request_duration_seconds_bucket{job="fastapi"}[5m])))`                                               | giây         |
| API-06 | Request rate theo route/status | `sum by (route, status) (rate(superstore_http_requests_total{job="fastapi"}[5m]))`                                                                               | request/giây |
| API-07 | P95 theo route                 | `histogram_quantile(0.95, sum by (route, le) (rate(superstore_http_request_duration_seconds_bucket{job="fastapi"}[5m])))`                                        | giây         |
| API-08 | P95 5 phút cao nhất / 24h      | `max_over_time((histogram_quantile(0.95, sum by (le) (rate(superstore_http_request_duration_seconds_bucket{job="fastapi"}[5m]))))[24h:15s])`                     | giây         |

`/metrics`, `/api/health/live` và `/api/health/ready` bị loại khỏi HTTP
Counter/Histogram. Khi không có traffic, rate/quantile có thể không có dữ liệu;
không tự coi đó là API khỏe. Kiểm tra `up{job="fastapi"}` riêng. HTTP 4xx
(ví dụ thiếu API key) không nằm trong 5xx rate.

## 2. VPS, Redis, Prometheus — PromQL

| ID       | Chỉ số            | Truy vấn                                                                                                                     | Đơn vị    |
| -------- | ----------------- | ---------------------------------------------------------------------------------------------------------------------------- | --------- |
| VPS-01   | CPU sử dụng       | `100 * (1 - avg by (instance) (rate(node_cpu_seconds_total{job="node",mode="idle"}[5m])))`                                   | %         |
| VPS-02   | RAM sử dụng       | `100 * (1 - node_memory_MemAvailable_bytes{job="node"} / node_memory_MemTotal_bytes{job="node"})`                            | %         |
| VPS-03   | Disk root sử dụng | `100 * (1 - node_filesystem_avail_bytes{job="node",mountpoint="/"} / node_filesystem_size_bytes{job="node",mountpoint="/"})` | %         |
| VPS-04   | Network nhận      | `sum by (instance) (rate(node_network_receive_bytes_total{job="node",device!="lo"}[5m]))`                                    | byte/giây |
| VPS-05   | Network gửi       | `sum by (instance) (rate(node_network_transmit_bytes_total{job="node",device!="lo"}[5m]))`                                   | byte/giây |
| REDIS-01 | Redis sẵn sàng    | `redis_up{job="redis"}`                                                                                                      | 1/0       |
| REDIS-02 | Redis dùng RAM    | `redis_memory_used_bytes{job="redis"}`                                                                                       | byte      |
| PROM-01  | Scrape target     | `up{job=~"fastapi\|redis\|node\|prometheus"}`                                                                                | 1/0       |
| PROM-02  | Thời gian scrape  | `scrape_duration_seconds{job=~"fastapi\|redis\|node\|prometheus"}`                                                           | giây      |
| PROM-03  | Số mẫu mỗi scrape | `scrape_samples_scraped{job=~"fastapi\|redis\|node\|prometheus"}`                                                            | mẫu       |

VPS-03 phụ thuộc nhãn `mountpoint="/"`; nếu không có kết quả, xem
`node_filesystem_size_bytes{job="node"}` để chọn nhãn mountpoint thật. Network
có thể bằng `0` khi rảnh. `redis_up=1` chỉ xác nhận Redis exporter kết nối được;
PROM-01 xác nhận Prometheus scrape target.

## 3. Logs — LogQL

Các nhãn `log_type` có trong `config.alloy` mới. Trước khi release này chạy
trên VPS, tìm theo `{service="fastapi"}` hoặc `{service="nginx"}` rồi lọc nội
dung; sau deploy dùng truy vấn chính xác bên dưới.

| ID     | Cần tìm                | Truy vấn                                                                  |
| ------ | ---------------------- | ------------------------------------------------------------------------- |
| LOG-01 | Lỗi ứng dụng           | `{service="fastapi",log_type="application"} \|= " ERROR - "`              |
| LOG-02 | Nginx error/warning    | `{service="nginx",log_type="error"}`                                      |
| LOG-03 | FastAPI HTTP 5xx       | `{service="fastapi",log_type="http"} \| json \| status >= 500`            |
| LOG-04 | Nginx HTTP 5xx         | `{service="nginx",log_type="access"} \| json \| status >= 500`            |
| LOG-05 | Nginx upstream timeout | `{service="nginx",log_type="error"} \|~ "(?i)timed out\|timeout"`         |
| LOG-06 | FastAPI timeout        | `{service="fastapi",log_type="application"} \|~ "(?i)timed out\|timeout"` |
| LOG-07 | Nginx 504              | `{service="nginx",log_type="access"} \| json \| status = 504`             |

Để nối một request, thay `REQUEST_ID` bằng `x-request-id` của response:

```logql
{service="fastapi",log_type="http"} |= "REQUEST_ID"
{service="nginx",log_type="access"} |= "REQUEST_ID"
```

FastAPI `application.log` không có `request_id`; dùng HTTP log để nối request.
Một truy vấn log rỗng có thể nghĩa là chưa có sự kiện trong khoảng thời gian,
không đủ để kết luận Alloy/Loki hỏng.

## 4. Baseline — truy vấn để điền bảng threshold

Dùng [bảng kết quả](monitoring_baseline_results.xlsx) trong Grafana Explore →
Prometheus → **Code**, chọn **Instant** và đặt thời điểm kết thúc đúng ngày chốt
`T0 + 1/14/30 ngày`. Các truy vấn dưới đây dùng `[24h]`; đổi thành `[14d]`
hoặc `[30d]` cho chỉ số **cả kỳ**. Riêng chỉ số ghi `/24h` luôn lấy 24 giờ
trước ngày chốt. Ô Excel định dạng `%` nhận tỷ lệ **0–1**: `0.85` hiển thị
`85%`, không nhập `85`. `increase()` có thể trả số lẻ do nội suy ở ranh giới
scrape; làm tròn số lượt để ghi báo cáo.

### 4.1. Lịch chạy và chỉ số chung

| ID      | Ô cần điền                      | Truy vấn                                                                                                                                       | Đơn vị                       |
| ------- | ------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------- |
| BASE-01 | Lịch chạy: public/staff thực tế | `round(increase(newman_runs_total{mode="timer"}[24h]))`                                                                                        | lượt, theo `collection`      |
| BASE-02 | Tỷ lệ run PASS                  | `1 - increase(newman_runs_failed_total{mode="timer"}[24h]) / increase(newman_runs_total{mode="timer"}[24h])`                                   | tỷ lệ 0–1, theo `collection` |
| BASE-03 | Giây từ lần chạy cuối           | `time() - newman_last_run_timestamp_seconds{mode="timer"}`                                                                                     | giây, theo `collection`      |
| BASE-04 | Thời gian run cao nhất          | `max_over_time(newman_last_run_duration_seconds{mode="timer"}[24h])`                                                                           | giây, theo `collection`      |
| BASE-05 | Lỗi 5xx / 24h toàn API          | `round(sum(increase(superstore_http_requests_total{job="fastapi",status=~"5.."}[24h])) or vector(0))`                                          | lỗi                          |
| BASE-06 | CPU VPS cao nhất / 24h          | `max_over_time((1 - avg by (instance) (rate(node_cpu_seconds_total{job="node",mode="idle"}[5m])))[24h:15s])`                                   | tỷ lệ 0–1                    |
| BASE-07 | RAM VPS cao nhất                | `max_over_time((1 - node_memory_MemAvailable_bytes{job="node"} / node_memory_MemTotal_bytes{job="node"})[24h:15s])`                            | tỷ lệ 0–1                    |
| BASE-08 | Disk root cao nhất              | `max_over_time((1 - node_filesystem_avail_bytes{job="node",mountpoint="/"} / node_filesystem_size_bytes{job="node",mountpoint="/"})[24h:15s])` | tỷ lệ 0–1                    |
| BASE-09 | Redis RAM cao nhất              | `max_over_time(redis_memory_used_bytes{job="redis"}[24h]) / 1024 / 1024`                                                                       | MiB                          |
| BASE-10 | Giới hạn Redis đang cấu hình    | `redis_memory_max_bytes{job="redis"} / 1024 / 1024`                                                                                            | MiB; dự kiến `256`           |
| BASE-11 | Số scrape target UP             | `sum(up{job=~"fastapi\|redis\|node\|prometheus"})`                                                                                             | 0–4                          |

`P95 5 phút` tại giờ chốt dùng **API-04**; đỉnh của các P95 5 phút trong 24 giờ
dùng **API-08** ở chế độ **Instant** tại giờ chốt. API-08 lấy mẫu mỗi `15s`;
đồ thị dùng bước `auto` có thể hiển thị đỉnh khác do thời điểm lấy mẫu. Đây
không phải P95 của toàn bộ request trong 24 giờ; chỉ số đó dùng **ROUTE-03**
theo từng route. `Kết nối Redis` dùng **REDIS-01**. BASE-03,
REDIS-01 và BASE-11 là trạng thái **tại lúc đo**, không phải tỷ lệ cả kỳ.
BASE-06 lấy đỉnh của CPU trung bình `rate[5m]` trong 24 giờ; bước `15s` khớp
chu kỳ scrape của Prometheus và giảm nguy cơ bỏ lỡ đỉnh giữa hai mốc 5 phút.
Chạy **Instant tại đúng cuối khoảng đo**; nếu so với panel CPU VPS (đơn vị `%`),
nhân kết quả BASE-06 với `100`. Chạy BASE-06 dạng Range sẽ cho đường _đỉnh
24 giờ trượt_, có thể bao gồm dữ liệu trước khoảng đang hiển thị.
Kuma chưa được Prometheus của dự án scrape: lấy uptime của monitor
`website-api`/`api-live` từ Kuma, không thay bằng tỷ lệ Newman PASS. Nếu
BASE-02 hoặc P95 không có mẫu thì ghi `N/A`, không ghi `0`. BASE-05 bằng `0`
chỉ đáng tin khi `up{job="fastapi"}=1` và API có request trong khoảng đo.

Redis `maxmemory=256mb` bằng **256 MiB** là giới hạn cấu hình, không phải
ngưỡng cảnh báo: mức 80% = **204.8 MiB**, 90% = **230.4 MiB**. So BASE-09
với BASE-10 trước khi đề xuất ngưỡng.

### 4.2. Theo route — số mẫu và P95

| ID       | Ô cần điền              | Truy vấn                                                                                                                       | Đơn vị                                                   |
| -------- | ----------------------- | ------------------------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------- |
| ROUTE-01 | Request / 24h           | `round(sum by (route) (increase(superstore_http_requests_total{job="fastapi"}[24h])))`                                         | request theo route                                       |
| ROUTE-02 | 5xx / 24h               | `round(sum by (route) (increase(superstore_http_requests_total{job="fastapi",status=~"5.."}[24h])))`                           | lỗi theo route                                           |
| ROUTE-03 | P95 / 24h               | `histogram_quantile(0.95, sum by (route, le) (increase(superstore_http_request_duration_seconds_bucket{job="fastapi"}[24h])))` | giây theo route                                          |
| ROUTE-04 | P95 baseline 14/30 ngày | `histogram_quantile(0.95, sum by (route, le) (increase(superstore_http_request_duration_seconds_bucket{job="fastapi"}[14d])))` | giây theo route; đổi `[14d]` thành `[30d]` ở mốc 30 ngày |

Lấy tên `route` đúng như ROUTE-01 trả về: middleware có thể ghi
`/dashboard/{metric}` dù URL ngoài là `/api/dashboard/{metric}`. Không tự
thêm/bỏ tiền tố hoặc gộp các route khác nhau. ROUTE-02 không có dòng cho một route chỉ được ghi
`0` khi ROUTE-01 xác nhận route đó có request và target FastAPI được scrape.
Chỉ đề xuất P95 theo route từ ngày 14 nếu ROUTE-01 có ít nhất **20 request/24h**.
P95 baseline 14/30 ngày đo toàn bộ request trong kỳ, khác với P95 5 phút của
API-04. Đối chiếu công thức cảnh báo `1.5 × baseline` và nghiêm trọng
`2 × baseline` trong sheet **Theo route**.

## 5. SLI — truy vấn cho Phase 6

Chạy dạng **Instant**. Thay `[24h]` bằng `[14d]` hoặc `[30d]` khi đủ dữ liệu;
giữ cùng một cửa sổ ở tử và mẫu. Kết quả dạng tỷ lệ **0–1**. Phạm vi và cách
đọc error budget ở [Threshold, SLI/SLO](threshold_sli_slo.md).

| ID     | Chỉ số                                         | Truy vấn                                                                                                                                                                                                                                                                                                   |
| ------ | ---------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| SLI-01 | API availability                               | `1 - (sum(increase(superstore_http_requests_total{job="fastapi",method!="OPTIONS",route!="unmatched",route!~"/health.*",status=~"5.."}[24h])) or vector(0)) / sum(increase(superstore_http_requests_total{job="fastapi",method!="OPTIONS",route!="unmatched",route!~"/health.*",status=~"[235].."}[24h]))` |
| SLI-02 | Số request hợp lệ                              | `sum(increase(superstore_http_requests_total{job="fastapi",method!="OPTIONS",route!="unmatched",route!~"/health.*",status=~"[235].."}[24h]))`                                                                                                                                                              |
| SLI-03 | Số lỗi tiêu thụ budget                         | `sum(increase(superstore_http_requests_total{job="fastapi",method!="OPTIONS",route!="unmatched",route!~"/health.*",status=~"5.."}[24h])) or vector(0)`                                                                                                                                                     |
| SLI-04 | Dashboard GET dưới 0,5 giây — **mốc minh họa** | `sum(increase(superstore_http_request_duration_seconds_bucket{job="fastapi",method="GET",route=~"/dashboard.*",le="0.5"}[24h])) / sum(increase(superstore_http_request_duration_seconds_count{job="fastapi",method="GET",route=~"/dashboard.*"}[24h]))`                                                    |
| SLI-05 | Staff Journey PASS / run thực tế               | `1 - increase(newman_runs_failed_total{mode="timer",collection="staff"}[24h]) / increase(newman_runs_total{mode="timer",collection="staff"}[24h])`                                                                                                                                                         |

Nhãn `route` của FastAPI thường là `/dashboard/{metric}` dù URL là
`/api/dashboard/{metric}`; xác nhận bằng ROUTE-01 trên production. SLI-04 chỉ
đo đúng bucket `le="0.5"`; khi chốt ngưỡng `T` khác, thay bằng
bucket tương ứng đã xác nhận trên Prometheus. Kiểm tra coverage bằng BASE-01
so với số run dự kiến và freshness bằng BASE-03. SLI-01 không bao phủ lỗi
Next.js/Vercel; SLI-04 hiện tính mọi status vì Histogram chưa có nhãn `status`.
Không có mẫu số thì kết quả rỗng là **N/A**, không phải 100%.
