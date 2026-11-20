# Monitoring — Discovery Result

## 1. Quy ước và phạm vi

| Trạng thái | Ý nghĩa                                               |
| ---------- | ----------------------------------------------------- |
| DONE       | Đã kiểm tra và có kết quả phù hợp                     |
| VERIFY     | Có cấu hình hoặc dịch vụ nhưng chưa kiểm thử đầu cuối |
| MISSING    | Chưa triển khai                                       |
| BROKEN     | Đã kiểm tra và có lỗi                                 |

**Phạm vi:** Phase 0 — audit production Monitoring; Phase 1–8 bổ sung checklist
kiểm chứng. Kết quả Phase 0 dựa trên log VPS người vận hành cung cấp ngày
**2026-11-14** và cấu hình trong repo. Kuma đang chạy, log Nginx và FastAPI đã
được tìm thấy trong Loki, Alertmanager chưa cài. Đây là bằng chứng của lượt
audit, không phải health check liên tục.

## 2. Kết quả Phase 0

| Thành phần         | Kết quả | Bằng chứng / giới hạn                                                                                                                        |
| ------------------ | ------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| FastAPI metrics    | DONE    | `/metrics` có HTTP Counter và Histogram; middleware tạo nhãn method/route/status                                                             |
| Prometheus         | DONE    | Bốn target `fastapi`, `redis`, `node`, `prometheus` đã trả `up=1` trong lượt kiểm tra                                                        |
| Redis Exporter     | DONE    | Prometheus trả `redis_up=1`                                                                                                                  |
| Node Exporter      | DONE    | Prometheus có `node_cpu_seconds_total`; truy vấn `count(...)` trả `16` chuỗi, không phải số CPU                                              |
| FastAPI HTTP file  | DONE    | Request `GET /api/staff/me` trả `403`; `http.log` tăng từ 160160 lên 160441 byte, có dòng route `/staff/me` lúc 16:03:53 UTC ngày 2026-11-14 |
| Alloy              | DONE    | Đã bắt đầu tail cả hai file; đường FastAPI → Loki được xác nhận bằng request mới                                                             |
| Loki/MinIO         | DONE    | Loki upload index thành công; Grafana Explore có log Nginx                                                                                   |
| Grafana datasource | DONE    | Truy vấn Prometheus `status=ok`; Explore Loki có log Nginx                                                                                   |
| FastAPI → Loki     | DONE    | `http.log` có dòng mới và truy vấn `{service="fastapi"}` hiện log                                                                            |
| Uptime Kuma        | DONE    | Người vận hành xác nhận container đang chạy; monitor public endpoint và lịch sử check chưa có bằng chứng lưu trong audit này                 |
| Grafana notifications | VERIFY | Ngày 20/11: Grafana VPS còn bốn rule do Grafana quản lý và contact point `Admin IT`; release mới tắt Grafana Alerting/SMTP nhưng chưa deploy, không xóa rule trước khi Prometheus nạp đủ rule thay thế |
| Alert rules        | VERIFY  | Hai rule target/Redis đã thêm trong repo; chưa có bằng chứng Prometheus production nạp rule                                                  |
| Alertmanager       | MISSING | Trong audit 14/11 chưa cài; repo hiện có Compose/config mẫu, chưa có bằng chứng chạy hoặc gửi email trên VPS                                 |

Trong release đã kiểm tra, Alloy đọc `http.log` và Nginx access log. Repo đã
thêm `application.log` và Nginx error log cho release kế tiếp; Docker
stdout/stderr vẫn xem trực tiếp bằng Compose.

Postman Monitor có trong sơ đồ mục tiêu nhưng không thuộc checklist Phase 0;
chưa có bằng chứng để kết luận trạng thái triển khai của dịch vụ bên ngoài này.

## 3. Phase 1 — metrics

| Kiểm tra                                  | Trạng thái | Bằng chứng hiện có / còn cần                                                                     |
| ----------------------------------------- | ---------- | ------------------------------------------------------------------------------------------------ |
| Counter tăng sau request thật             | Done       | Đã thấy Counter trong `/metrics`; cần đo giá trị Prometheus trước/sau ba request `/api/staff/me` |
| Nhãn `method`, `route`, `status`          | Done       | Code khai báo ba nhãn; cần đối chiếu nhãn thực tế với HTTP response và route mẫu                 |
| Histogram `_count`, bucket `+Inf`, `_sum` | Done       | Code ghi duration bằng giây; cần đối chiếu giá trị thật và kiểm tra `_count` bằng bucket `+Inf`  |
| VPS CPU/RAM/disk/network                  | Done       | Node Exporter trả chuỗi CPU; cần kiểm tra thêm RAM, disk, network và đơn vị                      |
| Redis                                     | Done       | `redis_up=1` đã xác nhận kết nối; cần kiểm tra metric bộ nhớ Redis                               |

Chưa có kết quả chạy các lệnh Phase 1 trên VPS trong lượt này. Điền số liệu,
thời gian và trạng thái DONE/BROKEN sau khi chạy [Operation §1](operation.md).

## 4. Phase 2 — logs

| Kiểm tra                                                                 | Trạng thái | Bằng chứng hiện có / còn cần                                                                    |
| ------------------------------------------------------------------------ | ---------- | ----------------------------------------------------------------------------------------------- |
| Cùng `x-request-id` trong response, FastAPI `http.log`, Nginx access log | Done       | Hai file đã có log; cần đối chiếu cùng một request mới                                          |
| Cùng ID trong Loki/Grafana                                               | Done       | Đã thấy log FastAPI và Nginx riêng lẻ; cần tìm cùng ID ở cả hai stream                          |
| Alloy control 4 file                                                     | Done       | config.alloy add 4 file: http.log, application.log, superstore-access.log, superstore-error.log |

Docker stdout/stderr **không ingest thêm**: API đã ghi log ra console và file;
người vận hành xem bằng `compose.sh logs` để tránh bản sao trùng trong Loki.
Giữ Phase 2 ở trạng thái VERIFY tới khi có kết quả [Operation §2](operation.md)
trên VPS sau deploy.

## 5. Phase 3 — thư viện PromQL và LogQL

[Query Library](promql_logql_library.md) có truy vấn API rate/5xx/P95/P99,
VPS, Redis, scrape target và log lỗi/5xx/timeout. Tên metric FastAPI được đối
chiếu với `core/observability.py`; nhãn `log_type` khớp `config.alloy` mới.

| Nhóm                        | Trạng thái | Cần kiểm chứng trên production                                                       |
| --------------------------- | ---------- | ------------------------------------------------------------------------------------ |
| API PromQL                  | Done       | Query trả `status=success`, rate tăng sau request; P95/P99 có giá trị và đơn vị giây |
| VPS/Redis/Prometheus PromQL | Done       | Metric/nhãn thực tế khớp, nhất là `mountpoint="/"`; Redis và bốn target có dữ liệu   |
| LogQL trên hai log hiện có  | Done       | Truy vấn hợp lệ; đối chiếu kết quả với log theo `request_id`                         |
| LogQL `log_type` mới        | Done       | Chỉ kiểm chứng sau khi release chứa `config.alloy` mới đã chạy trên VPS              |

Không dùng query Phase 3 cho dashboard hoặc alert trước khi chạy
[Operation §3](operation.md) và ghi lại kết quả thật.

## 6. Phase 4 — baseline, threshold và alert rules

[Threshold, SLI/SLO](threshold_sli_slo.md) quy định ba lần quyết định:
**sau 1 ngày, 14 ngày và 30 ngày** kể từ `T0` (runner theo lịch pass từ login
đến dashboard). Chưa có chuỗi số đo production được lưu để xác nhận ngưỡng
5xx, P95, CPU, RAM, disk hoặc Redis memory.

| Kiểm tra                          | Trạng thái | Cần xác nhận                                                                                                        |
| --------------------------------- | ---------- | ------------------------------------------------------------------------------------------------------------------- |
| Hai URL public health             | DONE       | GET ngày 2026-11-15 10:27 UTC: API và website đều `200`, JSON đúng; đây là một lần kiểm tra, chưa phải baseline     |
| Uptime Kuma monitor cụ thể        | Done       | Xác nhận lịch sử check và uptime ở cả ba mốc                                                                        |
| Newman runner + Grafana dashboard | DONE       | Hai service chạy PASS ngày 2026-11-17; bản export dashboard có trong `docs`, cần theo dõi dữ liệu mới               |
| Newman timer hoặc Postman         | Done       | Chọn một runner; xác nhận lượt **theo lịch** login `200`, `/staff/me` `200`, dashboard pass; lượt chạy tay không đủ |
| Baseline 1 ngày                   | Done       | Ghi `T0`, 24 giờ dữ liệu, số lượt thực và giới hạn tài nguyên tạm                                                   |
| Baseline 14 ngày                  | VERIFY     | Ghi độ phủ, số mẫu/route, P95, 5xx và ngưỡng cũ → mới                                                               |
| Baseline 30 ngày                  | VERIFY     | Xác nhận dữ liệu còn đủ trong Prometheus (`30d` hoặc `5GB`), chốt ngưỡng                                            |
| Dashboard: Devops & Dev           | Done       | Monitoring data                                                                                                     |
| Ngưỡng 5xx/P95/tài nguyên         | Done       | Công thức và ngưỡng tạm đã chọn trong tài liệu; cần số đo thật, rule và xác nhận đã nạp                             |
| Rule target/Redis                 | Done       | PR CI chạy `promtool check/test`; cần xác nhận Prometheus `/api/v1/rules` sau deploy                                |
| Chuyển tiếp email                 | VERIFY     | Alertmanager đã nhận rule thử ngày 19/11; cần email Firing/Resolved thực nhận sau khi sửa `smtp_from`               |

Không đánh dấu DONE chỉ vì rule tồn tại trong repo. Xem lệnh kiểm tra tại
[Operation §4](operation.md).

## 7. Phase 5 — dashboard theo vai trò

| Kiểm tra                         | Trạng thái | Bằng chứng / việc còn lại                                                                |
| -------------------------------- | ---------- | ---------------------------------------------------------------------------------------- |
| DevOps Operations                | DONE       | Đã có bản export JSON; kiểm tra URL/panel trên Grafana theo [Operation §5](operation.md) |
| DevOps alert overview            | VERIFY     | Bản export mới có panel đếm/bảng Firing và năm scrape target; cần import vào Grafana VPS rồi đối chiếu với `ALERTS`/`up` |
| Dev Troubleshooting              | DONE       | Đã có bản export JSON; đối chiếu log mới và `request_id` trên production                 |
| Newman Synthetic                 | DONE       | JSON được provision từ release; kiểm tra hai series `mode="timer"` và freshness          |
| Đồng bộ export với bản đang chạy | VERIFY     | Export lại sau mỗi lần sửa dashboard trong Grafana                                       |

Hai dashboard DevOps/Dev hiện là công cụ vận hành; không phải SLO dashboard.

## 8. Phase 6 — SLI, SLO và error budget

| Kiểm tra                                     | Trạng thái | Bằng chứng / việc còn lại                                                                |
| -------------------------------------------- | ---------- | ---------------------------------------------------------------------------------------- |
| Định nghĩa API, latency và Staff Journey SLI | DONE       | [Threshold, SLI/SLO](threshold_sli_slo.md) và metric trong `core/observability.py`       |
| Đo SLI 24 giờ, 14 ngày, 30 ngày              | Done       | Chạy `SLI-01`–`SLI-05` trên production, ghi vào sheet **SLI SLO** và lưu bằng chứng      |
| Độ phủ và freshness Newman                   | Done       | Đối chiếu run thực tế với 1.440 staff/288 public mỗi 24 giờ                              |
| Retention đủ 30 ngày                         | Done       | Prometheus giới hạn 30 ngày **hoặc** 5 GB; xác nhận dữ liệu đầu cửa sổ còn truy vấn được |
| SLO target và latency threshold              | Done       | Chốt từ baseline đủ kỳ, ghi chủ sở hữu và ngày áp dụng; chưa dùng mục tiêu ví dụ         |
| Error budget, burn rate và SLO dashboard     | Done       | Chỉ tính/dựng sau khi target được chốt; chưa có alert production                         |

## 9. Phase 7 — Alert Delivery và Incident Response

| Kiểm tra                              | Trạng thái | Bằng chứng / việc còn lại                                                                                                                  |
| ------------------------------------- | ---------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| Alertmanager, route và receiver       | Done       | Log 19/11: service chạy và nhận `AlertDeliveryDrill` ở `ops-email`                                                                         |
| Prometheus gửi alert tới Alertmanager | DONE       | Alertmanager log đã ghi alert từ Prometheus; cần lưu thêm `/api/v1/alertmanagers`                                                          |
| Bốn chuỗi Newman timer                | Done       | Cần xác nhận timestamp và consecutive failures cho `public`/`staff` đều có trong Prometheus; thiếu chuỗi 10m mới kích hoạt `MetricMissing` |
| Node Exporter textfile                | Done       | Cần xác nhận `node_textfile_scrape_error{job="node"}=0`; giá trị 0 không chứng minh bốn chuỗi Newman có mặt                                |
| Pending → Firing → email nhận được    | Done       | Log 19/11: gửi email lỗi vì `smtp_from` thiếu địa chỉ hợp lệ; chưa có bằng chứng sau khi sửa                                               |
| Resolved và chống gửi trùng           | Done       | Chưa có email resolved và kết quả kiểm tra `repeat_interval`                                                                               |
| Phân loại P1–P4, timeline/postmortem  | Done       | Hướng dẫn ngắn ở [Operation §7](operation.md); chưa có incident thật để áp dụng                                                            |

Source mới có 19 rule trong `availability.yml`, `resources.yml`, `synthetic.yml`
và `api.yml`; Makefile/PR CI kiểm tra cú pháp và dữ liệu giả. **Chưa xác nhận**
19 rule đã được nạp trên VPS hoặc email Firing/Resolved đã đến. Truy vấn
Prometheus VPS ngày 20/11 chỉ thấy nhóm `superstore-availability` và nhóm thử
`alert-delivery-drill`; các nhóm tài nguyên, API và synthetic chưa nạp.
`deploy.sh` của release mới chặn deploy nếu thiếu một trong bốn nhóm. Sau deploy,
ghi lại release SHA, `/api/v1/rules`, các metric nguồn và email thực nhận;
đừng thay bằng kết quả `promtool` local.
Hai rule `MetricMissing` và `TextfileError` đo **thiếu dữ liệu ở Prometheus**
và **lỗi đọc textfile ở Node Exporter**; chúng không kiểm tra kết quả Newman.
Lượt FAIL có ghi metrics vẫn cập nhật timestamp, còn lượt dừng trước khi ghi
giữ timestamp cũ và có thể kích hoạt rule trễ lịch.

## 10. Phase 8 — End-to-End Validation

[Báo cáo Phase 8](../../tests/end_to_end_validation.md) theo dõi request → metrics/logs →
rule → Alertmanager/email → phục hồi. Các phép kiểm production chỉ đọc dữ liệu
hoặc gửi request nhỏ; lỗi API, Redis và exporter có chủ đích cần
staging riêng. Repo chưa có Compose staging, vì vậy chưa thể đánh dấu các ca
tạo lỗi là PASS.

| Nhóm                       | Trạng thái | Bằng chứng còn cần                                                        |
| -------------------------- | ---------- | ------------------------------------------------------------------------- |
| Request → metrics/logs     | Done       | Counter/Histogram trước/sau và cùng request ID trong Loki                 |
| Synthetic/Kuma → dashboard | Done       | Lượt timer mới, trạng thái monitor, giá trị panel cùng thời điểm          |
| Fault injection staging    | MISSING    | Stack staging, nguồn tạo `503` và chuỗi Redis/exporter/API lỗi → phục hồi |
| Alert delivery và resolved | Done       | Email Firing/Resolved thực nhận, receiver và thời gian gửi                |
