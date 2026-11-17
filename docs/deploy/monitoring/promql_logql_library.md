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

| ID     | Cần tìm                | Truy vấn                                                            |
| ------ | ---------------------- | ------------------------------------------------------------------- |
| LOG-01 | Lỗi ứng dụng           | `{service="fastapi",log_type="application"} \|= " ERROR - "`        |
| LOG-02 | Nginx error/warning    | `{service="nginx",log_type="error"}`                               |
| LOG-03 | FastAPI HTTP 5xx       | `{service="fastapi",log_type="http"} \| json \| status >= 500`      |
| LOG-04 | Nginx HTTP 5xx         | `{service="nginx",log_type="access"} \| json \| status >= 500`     |
| LOG-05 | Nginx upstream timeout | `{service="nginx",log_type="error"} \|~ "(?i)timed out\|timeout"`  |
| LOG-06 | FastAPI timeout        | `{service="fastapi",log_type="application"} \|~ "(?i)timed out\|timeout"` |
| LOG-07 | Nginx 504              | `{service="nginx",log_type="access"} \| json \| status = 504`      |

Để nối một request, thay `REQUEST_ID` bằng `x-request-id` của response:

```logql
{service="fastapi",log_type="http"} |= "REQUEST_ID"
{service="nginx",log_type="access"} |= "REQUEST_ID"
```

FastAPI `application.log` không có `request_id`; dùng HTTP log để nối request.
Một truy vấn log rỗng có thể nghĩa là chưa có sự kiện trong khoảng thời gian,
không đủ để kết luận Alloy/Loki hỏng.
