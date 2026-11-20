# Monitoring — Threshold, SLI/SLO và Error Budget

## 1. Baseline và mốc quyết định

| Mốc            | Điều kiện đủ dữ liệu                             | Quyết định                                                           |
| -------------- | ------------------------------------------------ | -------------------------------------------------------------------- |
| `T0 + 1 ngày`  | Có lịch sử 24 giờ; ≥85% lượt dự kiến có kết quả  | Chọn ngưỡng khả dụng/tài nguyên tạm; chỉ quan sát API latency và 5xx |
| `T0 + 14 ngày` | Có 14 ngày; ≥95% lượt, đủ số mẫu theo từng route | Chọn ngưỡng API từ baseline 14 ngày; rà lại ngưỡng tài nguyên        |
| `T0 + 30 ngày` | Có 30 ngày; ≥95% lượt, kiểm tra chu kỳ ngày/tuần | Chốt lại ngưỡng và lịch rà soát                                      |

Ghi số đo và bằng chứng vào [workbook](monitoring_baseline_results.xlsx). Prometheus
giữ dữ liệu tối đa `30d` **hoặc** `5GB`, giới hạn nào đến trước. Trước mốc 30
ngày, xác nhận đầu cửa sổ vẫn truy vấn được; nếu không, lưu báo cáo định kỳ
hoặc điều chỉnh retention sau khi kiểm tra dung lượng VPS.
[Prometheus storage](https://prometheus.io/docs/prometheus/latest/storage/).

## 2. Chọn ngưỡng cảnh báo

| Tín hiệu      | Sau 1 ngày — tạm thời                                                                                             | Sau 14 ngày                                   | Sau 30 ngày                           |
| ------------- | ----------------------------------------------------------------------------------------------------------------- | --------------------------------------------- | ------------------------------------- |
| Scrape/Redis  | Giữ `up == 0` hoặc `redis_up == 0` trong `2m`                                                                     | Đối chiếu sự cố/false alarm                   | Rà lại sau mỗi sự cố                  |
| Kuma public   | Cảnh báo sau 3 lần check liên tiếp không đạt; interval `60s`                                                      | Kiểm tra downtime/độ trễ từng URL             | Chốt theo lịch sử 30 ngày             |
| Staff Journey | 1 run fail: điều tra; 2 run liên tiếp fail: cảnh báo; staff trễ >120s, public >600s                               | Phân loại lỗi login, API, timeout             | Rà lại false alarm                    |
| API 5xx       | Cùng route: warning ≥3 lỗi/5m, critical ≥5 lỗi/5m; không có `for`; nhắc lại sau 1h nếu vẫn Firing                 | Kiểm tra lại count và tỷ lệ theo traffic thực | Chốt lại theo traffic thực            |
| API P95       | Tạm dùng đỉnh P95 ngày 1 = `3,68s`: warning `>5,52s`, critical `>7,36s`, theo route có ≥20 request/24h; `for: 1h` | Thay bằng ngưỡng route từ baseline 14 ngày    | Chốt lại baseline 30 ngày             |
| CPU/RAM VPS   | Warning ≥60%/15m; critical ≥85%/10m                                                                               | So với P95 và giờ cao điểm                    | Chốt theo xu hướng và capacity review |
| Disk root     | Warning ≥60%/1h; critical ≥85%/10m                                                                                | Xem tốc độ tăng/dung lượng còn lại            | Điều chỉnh theo tốc độ tăng 30 ngày   |
| Redis RAM     | Warning ≥60%/15m; critical ≥85%/5m của `maxmemory=256mb`                                                          | Kiểm tra `noeviction` và peak                 | Chốt theo peak và dung lượng còn lại  |

Ngưỡng trong bảng là **đề xuất**. Chỉ coi rule đã hoạt động khi cấu hình được
nạp trên production và thử được trạng thái Pending → Firing → Resolved.
Ngưỡng **P95** ngày 1 là tạm thời, không suy ra SLO 30 ngày. Rule 5xx dùng
cửa sổ trượt 5 phút: một lỗi đơn lẻ chỉ xuất hiện trong log/dashboard; khi đủ
3 hoặc 5 lỗi trên cùng route, Prometheus Firing ở lần đánh giá tiếp theo và
Alertmanager gửi email sau `group_wait`. Nếu không còn lỗi đủ ngưỡng trong
5 phút gần nhất, alert Resolved; chỉ nhắc lại sau 1 giờ nếu vẫn Firing.
`increase()` có thể cho giá trị lẻ do nội suy giữa các lần scrape, nên ngưỡng
đếm là xấp xỉ. P95 cũng đo cửa sổ 5 phút, khác P95 của toàn bộ 24 giờ.

Newman ghi `newman_last_run_timestamp_seconds` sau mỗi lượt **hoàn tất**, kể cả
FAIL. Vì vậy rule trễ lịch đo thời gian từ lượt hoàn tất gần nhất; FAIL hai lượt
liên tiếp do `SuperstoreNewmanConsecutiveFailures` phát hiện. Nếu runner dừng
trước khi ghi metrics, timestamp cũ sẽ tiếp tục tăng tuổi. Rule thiếu metric
kiểm tra hai chỉ số timestamp và consecutive failures cho **cả public và
staff**; rule textfile kiểm tra lỗi đọc file do Node Exporter báo, không kiểm
tra trực tiếp kết quả journey.

## 3. Phạm vi SLI

```text
Browser → Next.js → FastAPI → Redis/Snowflake
    │                     │
    │                     └─ HTTP Counter/Histogram → API SLI
    └─ Newman Staff Journey theo lịch → SLI login + dashboard
```

| SLI               | Dữ liệu và mẫu số                                                                               | Request tốt                                 | Giới hạn                                                 |
| ----------------- | ----------------------------------------------------------------------------------------------- | ------------------------------------------- | -------------------------------------------------------- |
| API availability  | FastAPI Counter; route đã nhận diện, bỏ `OPTIONS` và `4xx`                                      | `2xx`/`3xx`; `5xx` tiêu thụ budget          | Không đo lỗi Next.js/Vercel trước khi tới FastAPI        |
| Dashboard latency | Histogram của `GET /api/dashboard` và `/api/dashboard/{metric}`; nhãn thường là `/dashboard...` | Request không quá ngưỡng `T`                | Histogram không có nhãn `status`, nên gồm cả `4xx`/`5xx` |
| Staff Journey     | Newman `staff` mỗi phút: login → dashboard → logout                                             | Run PASS; kiểm tra cả coverage và freshness | Synthetic traffic, không đại diện người dùng thật        |

`/metrics` và `/api/health/live|ready` bị loại khỏi HTTP metrics trong
`core/observability.py`; SLI cũng loại các health route cũ. `4xx` không tính là
lỗi máy chủ API, nhưng Newman vẫn FAIL nếu response sai kỳ vọng. Kuma theo dõi
khả năng truy cập public riêng, không thay ba SLI này.

## 4. Công thức và mục tiêu SLO

Với cửa sổ đo `W`:

```text
API availability = 1 − số 5xx / số (2xx + 3xx + 5xx)
Dashboard latency compliance = số dashboard GET ≤ T giây / tổng dashboard GET
Staff Journey success = số run PASS / số run thực tế
Staff Journey coverage = số run thực tế / số run dự kiến

Error budget API = số request hợp lệ × (1 − API SLO target)
Budget còn lại = max(0, error budget − số 5xx)
Burn rate = (số 5xx / số request hợp lệ) / (1 − API SLO target)
```

Staff dự kiến **1.440 run/24h**, public **288 run/24h**. Run bị bỏ lỡ làm giảm
coverage dù các run đã chạy đều PASS. Cửa sổ SLO là **30 ngày trượt**; `T` phải
trùng một bucket Histogram đang có (`0.5`, `1`, `2`, `5`... giây).

Chỉ chốt target, `T` và chính sách error budget sau khi có baseline 14/30 ngày
và xác nhận phạm vi SLI. Các mục tiêu 99,9% hoặc 500 ms trong lộ trình ban
đầu là **ví dụ**, chưa phải cam kết production. Mẫu số bằng 0 hoặc thiếu dữ
liệu thì ghi **N/A**, không ghi PASS/100%.

| Quyết định cần chốt                  | Target / ngưỡng | Chủ sở hữu | Bằng chứng 30 ngày |
| ------------------------------------ | --------------- | ---------- | ------------------ |
| API availability                     | 95%             |            |                    |
| Dashboard latency (`T` và tỷ lệ đạt) | 90%             |            |                    |
| Staff Journey success và coverage    | 90%             |            |                    |

## 5. Ghi kết quả và kích hoạt

1. Chạy `SLI-01`–`SLI-05` trong [Query Library](promql_logql_library.md) ở
   mốc 24 giờ, 14 ngày và 30 ngày; ghi vào sheet **SLI SLO** của
   [workbook](monitoring_baseline_results.xlsx).
2. Xác nhận `up{job="fastapi"}=1`, Newman có hai series `mode="timer"`, run
   đủ coverage và Prometheus còn lịch sử đầu cửa sổ 30 ngày.
3. Ghi target, `T`, chủ sở hữu, ngày áp dụng và bằng chứng vào hàng 15–18.
   Chỉ ghi `Dữ liệu đủ? = Có` khi kiểm tra đủ 30 ngày; Staff Journey cần
   coverage ≥95%. Cập nhật [Discovery Result](discovery_result.md).
4. Error budget và burn rate chỉ đưa lên dashboard sau khi chốt target. Rule
   cảnh báo theo budget thuộc Phase 7 và chỉ bật khi có kết quả production.

Trong workbook, `B16` là API availability target, `B17` là tỷ lệ dashboard
request đạt `T` ở `C17` (giây), `B18` là tỷ lệ Staff Journey PASS. `C16` và
`C18` để trống. Ở mốc ngày 1 và 14, `I6:I7` có thể tham chiếu `=$B$16` sau
khi target được chốt; `J:L` tự tính budget/burn rate cho **từng khoảng đo**, chưa
phải kết luận SLO 30 ngày. Hàng 8 mới là cửa sổ 30 ngày. Nếu đổi `T`, chạy
lại SLI-04 và cập nhật `F6:F8`.

[Prometheus histogram](https://prometheus.io/docs/practices/histograms/) dùng
bucket tích lũy; `increase()` có thể trả số lẻ do nội suy ở ranh giới cửa sổ.
