# Monitoring — System Architecture & Lineage

![Kiến trúc Monitoring mục tiêu](monitoring.png)

Hình trên là **kiến trúc mục tiêu**. [Discovery Result](discovery_result.md)
ghi trạng thái đã kiểm chứng; không suy ra mọi ô trong hình đã chạy trên production.

## 1. Luồng đang có

```mermaid
flowchart LR
    API[FastAPI /metrics] --> P[Prometheus]
    N[Newman timers: Public mỗi 5 phút, Staff mỗi phút] --> F[Prometheus text files]
    F --> NE[Node Exporter: VPS + synthetic]
    NE --> P
    RE[Redis Exporter: Redis] --> P
    P --> G[Grafana Explore]
    P -. sau deploy: Phase 4 .-> AR[Alert rules: scrape và Redis]
    AR -. Phase 7 .-> AM[Alertmanager: chưa cài]

    AH[FastAPI http.log] --> A[Alloy]
    NG[Nginx access log] --> A
    APP[FastAPI application.log: sau deploy] -.-> A
    NELOG[Nginx error log: sau deploy] -.-> A
    A --> L[Loki]
    L --> M[MinIO: loki-logs]
    L --> G

    K[Uptime Kuma: stack riêng] --> PUB[Public health endpoint]
```

| Nhánh        | Nguồn → đích                                                  | Dùng để làm gì                                               |
| ------------ | ------------------------------------------------------------- | ------------------------------------------------------------ |
| Metrics      | FastAPI, Node Exporter, Redis Exporter → Prometheus → Grafana | Đếm request, đo thời gian xử lý, theo dõi VPS và Redis       |
| Logs         | `http.log`, Nginx access log → Alloy → Loki/MinIO → Grafana   | Tìm request theo thời gian, route, status và request ID      |
| Logs bổ sung | `application.log`, Nginx error log → Alloy                    | Cấu hình đã có trong repo; cần deploy và kiểm chứng trên VPS |
| Availability | Uptime Kuma → public health endpoint                          | Phát hiện endpoint không truy cập được từ bên ngoài          |
| Synthetic    | Newman → Node Exporter text files → Prometheus → Grafana       | Kiểm tra luồng staff, ghi pass/fail và thời gian từng request |

Prometheus còn scrape chính nó. `prometheus.yml` khai báo bốn job: `fastapi`,
`redis`, `node`, `prometheus`. Grafana có hai datasource Prometheus và Loki;
repo đã có dashboard Newman trong mã nguồn; cần deploy, chạy timer và xác nhận
dữ liệu thật trên Grafana.

Phase 3 có [thư viện PromQL/LogQL](promql_logql_library.md) để dùng lại cho
dashboard và alert. Query chỉ được xác nhận sau khi chạy trên production theo
[Operation §3](operation.md). Phase 4 đã chuẩn bị rule cho target/Redis;
[Baseline & Thresholds](baseline_thresholds.md) ghi những ngưỡng còn cần đo.

## 2. Dữ liệu được thu thập

| Nguồn                   | Cấu hình                                   | Lưu ý                                                                                                                                            |
| ----------------------- | ------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| FastAPI metrics         | `core/observability.py` → `/metrics`       | Counter `superstore_http_requests_total{method,route,status}`; Histogram `superstore_http_request_duration_seconds{method,route}` tính bằng giây |
| FastAPI HTTP log        | `/opt/superstore/logs/api/http.log`        | JSON: request ID, method, route, status và `duration_ms`                                                                                         |
| Nginx access log        | `/var/log/nginx/superstore-access.log`     | JSON: request ID từ upstream, method, route, status và duration                                                                                   |
| FastAPI application log | `/opt/superstore/logs/api/application.log` | Hoạt động của FastAPI: xử lý request, thông báo ứng dụng, lỗi Python                                                                             |
| Nginx error log         | `/var/log/nginx/superstore-error.log`      | Lỗi Nginx: kết nối backend thất bại, timeout, lỗi proxy                                                                                          |
| Docker stdout/stderr    | `compose.sh logs`                          | Xem trực tiếp bằng Compose; **chưa được Alloy thu thập**                                                                                         |

FastAPI loại `/metrics`, `/api/health/live` và `/api/health/ready` khỏi HTTP
Counter/Histogram và `http.log`. Khi kiểm tra log hoặc Counter tăng, hãy gọi
một route khác, chẳng hạn `/api/staff/me`.

Phase 2 đối chiếu `x-request-id` trong response với `request_id` ở FastAPI
`http.log`, Nginx access log và hai stream Loki. Hai log bổ sung phục vụ điều
tra lỗi; application log không có `request_id` nên không dùng để nối từng
request. Docker stdout/stderr xem qua Compose, tránh ingest trùng log file.

Prometheus giữ dữ liệu tối đa **30 ngày hoặc 5 GB**; Loki đặt retention **14
ngày** và dùng bucket MinIO `loki-logs`. Các cổng API, Prometheus, Grafana và
Uptime Kuma chỉ bind `127.0.0.1` trên VPS; mở giao diện quản trị qua SSH tunnel.
Loki Compactor đánh dấu log quá hạn rồi xóa các chunk tương ứng trong MinIO
sau `retention_delete_delay: 2h`; không đặt thêm lifecycle xóa toàn bucket.

## 3. Chưa hoàn thiện

| Thành phần                           | Trạng thái hiện biết                                                         |
| ------------------------------------ | ---------------------------------------------------------------------------- |
| Prometheus alert rules               | Có hai rule trong repo; cần deploy và xác nhận Prometheus đã nạp              |
| Alertmanager                         | Chưa có trong production stack; chưa có đường gửi email từ Prometheus        |
| Grafana SMTP                         | Đã sửa cách nạp biến từ `grafana.env`; cần gửi email thử để xác nhận         |
| Newman synthetic timer               | Có code, CI và dashboard trong repo; cần cài timer và kiểm chứng trên VPS   |
| Postman Cloud Monitor                | Tùy chọn thay Newman; không bật song song nếu muốn tránh traffic trùng      |
| Uptime Kuma monitor cụ thể           | Kuma đang chạy; cấu hình và lịch sử check public endpoint cần xác minh riêng |

## 4. File và cách kiểm tra

| File                                                                | Vai trò                                               |
| ------------------------------------------------------------------- | ----------------------------------------------------- |
| `deploy/production/compose.yml`, `prometheus.yml`                   | Container, network, scrape targets, retention metrics |
| `deploy/production/prometheus/rules/availability.yml`              | Rule phát hiện target/Redis không sẵn sàng              |
| `deploy/production/config.alloy`, `loki.yml`                        | Chọn bốn file log sau deploy; chuyển tiếp và lưu log  |
| `deploy/production/grafana/provisioning/datasources/superstore.yml` | Khai báo datasource Prometheus/Loki                   |
| `deploy/production/newman/`, `grafana/dashboards/`                  | Chạy collection theo lịch và hiển thị synthetic       |
| [PromQL & LogQL Query Library](promql_logql_library.md)            | Truy vấn Phase 3; chờ xác minh trên production        |
| [Baseline & Thresholds](baseline_thresholds.md)                    | Phép đo và ngưỡng cần chốt ở Phase 4                  |
| [Synthetic Baseline](synthetic_baseline.md)                         | Tạo Postman/Kuma monitor và đo public health         |
| `deploy/kuma/docker-compose.yml`                                    | Uptime Kuma ở stack riêng                             |
| [Operation](operation.md)                                           | Lệnh kiểm tra Phase 0–4 và kết quả mong đợi            |
| [Discovery Result](discovery_result.md)                             | Bằng chứng, trạng thái DONE/VERIFY/MISSING/BROKEN     |

Không dùng HTTP metrics để suy ra doanh thu hoặc số đơn hàng; các chỉ số kinh
doanh lấy từ Snowflake/dbt.
