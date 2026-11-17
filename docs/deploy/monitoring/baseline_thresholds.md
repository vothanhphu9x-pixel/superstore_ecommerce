# Monitoring — Baseline & Thresholds

## 1. Mốc bắt đầu và dữ liệu đo

Ngày `T0` là lúc **Kuma và runner collection đã chọn (Newman trên VPS hoặc
Postman Cloud Monitor) chạy theo lịch**, request login trả `200`, `/staff/me`
sau login trả `200`, và các dashboard test pass. Lần `Send` hoặc Newman
`mode="manual"` không tính vào lịch sử theo lịch. Giữ nguyên nơi chạy, tần suất và
query khi so sánh các mốc; ghi ngày thay đổi cấu hình nếu phải điều chỉnh.

| Mốc | Điều kiện đủ dữ liệu | Quyết định |
| --- | --- | --- |
| `T0 + 1 ngày` | Có lịch sử 24 giờ; ≥95% số lượt dự kiến có kết quả | Chọn ngưỡng khả dụng và giới hạn tài nguyên tạm; API latency/5xx chỉ theo dõi |
| `T0 + 14 ngày` | 14 ngày; ≥95% số lượt, có số mẫu theo từng route | Chọn ngưỡng API từ baseline 14 ngày; rà lại giới hạn tài nguyên |
| `T0 + 30 ngày` | 30 ngày; ≥95% số lượt, kiểm tra chu kỳ ngày/tuần | Thay baseline 14 ngày bằng 30 ngày; chốt ngưỡng và lịch rà soát |

Với Newman, mỗi ngày dự kiến Public **288 lượt** (mỗi 5 phút) và Staff Journey
**1.440 lượt** (mỗi phút). Nếu chọn Postman Cloud theo lịch §4 của
[Synthetic Baseline](synthetic_baseline.md), Staff Journey là **24 lượt/ngày**.
Lượt thiếu hoặc fail không được tính là pass. Nếu chưa đủ dữ liệu ở một mốc, tiếp tục dùng ngưỡng
của mốc trước và ghi lý do; không tự nâng ngưỡng để che lỗi. Các phép đo hiện
chỉ phản ánh traffic **idle + synthetic**, chưa đại diện cho tải người dùng thật.

Prometheus hiện giữ tối đa `30d` **hoặc** `5GB`, giới hạn nào đến trước. Trước
mốc 30 ngày, kiểm tra khoảng thời gian thực còn dữ liệu; nếu không đủ, xuất
báo cáo định kỳ hoặc điều chỉnh retention sau khi kiểm tra dung lượng VPS.
[Prometheus storage](https://prometheus.io/docs/prometheus/latest/storage/).

## 2. Chiến lược chọn ngưỡng

| Tín hiệu | Sau 1 ngày — ngưỡng tạm | Sau 14 ngày | Sau 30 ngày |
| --- | --- | --- | --- |
| Scrape/Redis | Giữ `up == 0` hoặc `redis_up == 0` trong `2m` (rule đã viết) | Đối chiếu sự cố và false alarm; chỉ sửa nếu có bằng chứng | Rà lại sau mỗi sự cố |
| Kuma public | Cảnh báo sau 3 lần check liên tiếp không đạt, interval `60s` | Kiểm tra downtime/độ trễ từng URL | Chốt theo lịch sử 30 ngày |
| Staff Journey (Newman/Postman) | 1 run fail: điều tra; 2 run liên tiếp fail: cảnh báo | Giữ, đồng thời phân loại lỗi login, API, timeout | Rà lại với tỷ lệ false alarm thực tế |
| API 5xx | Ghi mọi lỗi theo từng route; chưa đặt tỷ lệ % từ ít mẫu | Khi mỗi route có ≥20 request/ngày, cảnh báo nếu ≥1 lỗi 5xx/24h; ≥3 lỗi/24h là critical | Kiểm tra lại count và tỷ lệ theo traffic thực, không mặc nhiên chấp nhận baseline lỗi |
| API P95 | Ghi thời gian từng URL; chưa tạo alert P95 | Với ≥20 request/route/24h: warning khi P95 24h > `1,5 × P95 baseline 14 ngày`, critical khi > `2 ×`; giữ `for: 2h` | Tính lại P95 baseline 30 ngày, thay **giá trị số** trong rule, kiểm tra nhiễu theo giờ/ngày |
| CPU/RAM VPS | Warning `≥85%/15m`, critical `≥95%/10m` | So với P95 và giờ cao điểm; giảm ngưỡng nếu cần phát hiện sớm | Chốt theo xu hướng, không nâng giới hạn an toàn nếu chưa có capacity review |
| Disk root | Warning `≥80%/1h`, critical `≥90%/10m` | Xem tốc độ tăng và số ngày còn lại đến khi đầy | Điều chỉnh theo tốc độ tăng 30 ngày |
| Redis RAM | Warning `≥80%/15m`, critical `≥90%/5m` của `maxmemory=256mb` | Kiểm tra eviction policy `noeviction` và peak | Chốt theo peak 30 ngày và dung lượng còn lại |

Ký hiệu `≥85%/15m` nghĩa là duy trì mức ≥85% trong 15 phút (`for: 15m`),
không phải trung bình 15 phút. Với số lỗi `5xx/24h`, đếm trên cửa sổ 24 giờ;
không cộng thêm `for` dài vì điều kiện đã bao gồm thời gian quan sát.
Các tỷ lệ và hệ số trên là **chính sách tạm**, không phải số đo production.
P95 của Histogram là ước lượng theo bucket; phải xem `_count` trước khi dùng.
Nếu route chưa đủ 20 request/ngày, giữ alert theo Postman/Kuma và đánh dấu
`INSUFFICIENT_DATA`; không coi query rỗng là `0`. API 5xx dùng **số lỗi** khi
traffic chỉ do synthetic tạo ra, tránh tỷ lệ dao động mạnh vì mẫu nhỏ. Nếu dùng
Newman, lọc `mode="timer"` trong PromQL để bỏ lượt kiểm thử tay.
[Prometheus histograms](https://prometheus.io/docs/practices/histograms/).

## 3. Ghi kết quả và áp dụng

Ở từng mốc, mở Grafana Explore → Prometheus và [Query Library](promql_logql_library.md).
Ghi vào [Discovery Result](discovery_result.md): `T0`, ngày đo, khoảng dữ liệu
thực, số lượt dự kiến/thực tế, request count, P95, 5xx, CPU/RAM/disk/Redis,
ngưỡng cũ → mới và lý do. Chỉ sau khi có số đo mới thay **giá trị số** trong
Prometheus rule, chạy `promtool check/test`, triển khai rồi kiểm tra
`/api/v1/rules`. `for` là thời gian điều kiện phải duy trì trước khi rule Firing.
[Prometheus alerting rules](https://prometheus.io/docs/prometheus/latest/configuration/alerting_rules/).

Hiện repo chỉ có [`availability.yml`](../../../deploy/production/prometheus/rules/availability.yml)
với hai rule scrape/Redis. Các ngưỡng tạm và ngưỡng API trong bảng **chưa được
nạp vào Prometheus**; Alertmanager chưa cài nên chưa gửi email. Không ghi
`ACTIVE` trước khi xác nhận rule đã triển khai và chạy trên VPS.
