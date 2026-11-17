# Backup — Discovery Result

## Trạng thái

- **Verified:** đã chạy và có bằng chứng.
- **Failed:** đã chạy nhưng không đạt.
- **Blocked:** chưa thể chạy do thiếu quyền, dịch vụ hoặc kết nối.
- **Not Run:** chưa có kết quả thực tế; đọc code không được tính là pass.

## Thông tin lần kiểm tra

- Ngày cập nhật: **2026-11-14**.
- Phạm vi: VPS → SQLite snapshot → mã hóa age → S3 → restore trên Mac.
- Kết luận: **backup thủ công và restore local đã đạt**; lịch chạy tự động và khôi phục VPS mới chưa được xác minh.
- Bằng chứng runtime VPS bên dưới lấy từ log ngày **2026-11-13** do người dùng cung cấp. Bằng chứng local được kiểm tra ngày **2026-11-14**.

## Thành phần cần kiểm soát

```text
VPS: systemd timer → backup.sh → staff SQLite + cấu hình + release metadata
                              → .tar.gz.age + .sha256 → S3
Mac: S3 → restore-local.sh + age private key → restore-*/ → integrity_check
```

Backup không chứa dữ liệu Snowflake, MinIO, Redis, logs, certificate hoặc toàn bộ source/image release. Private key và bản restore đã giải mã nằm trong hai thư mục local bị Git ignore; không đính kèm chúng làm bằng chứng.

## Checklist kết quả

| Gate | Kỳ vọng | Kết quả | Bằng chứng / lần chạy |
|---|---|---|---|
| B01 — Script | Ba script backup/restore không lỗi cú pháp | Verified | `bash -n` trên Mac, 2026-11-14 |
| B02 — Timer | Timer được bật và có lịch chạy tiếp theo | Verified | `systemctl list-timers superstore-backup.timer` trong log 2026-11-13 |
| B03 — AWS writer | Backup chạy với IAM user `superstore-vps-backup-writer` | Verified | Journal: `AWS identity verified`, 2026-11-13 08:01 UTC |
| B04 — SQLite snapshot | Snapshot được tạo và `integrity_check` đạt | Verified | Journal: `SQLite snapshot created and verified`, 2026-11-13 08:01 UTC |
| B05 — Release | Release SHA hiện hành được kiểm tra | Verified | Journal: `Current release verified`, 2026-11-13 08:01 UTC |
| B06 — S3 | Upload file `.tar.gz.age` và kiểm tra lại SHA-256 | Verified | Journal: `Remote SHA-256 verification successful` và `Backup completed`, 2026-11-13 08:01 UTC |
| B07 — Khóa giải mã | Private key parse được, quyền file `600` | Verified | Kiểm tra local, 2026-11-14; không in nội dung key |
| B08 — Restore local | Có thư mục `restore-*`, manifest đủ trường và SQLite nguyên vẹn | Verified | Restore ngày 2026-11-14; `PRAGMA integrity_check = ok` kiểm tra local |
| B09 — Git | Private key và bản giải mã không bị Git theo dõi | Verified | `git check-ignore -v` và `git status --ignored`, 2026-11-14 |
| B10 — Lịch tự động | Một lượt chạy **do timer kích hoạt** hoàn tất | Not Run | Mới thấy lượt chạy thủ công; cần journal của lượt theo lịch |
| B11 — IAM restore | Restore dùng đúng principal chỉ đọc `superstore-back-up-restore` | Not Run | Cần `aws sts get-caller-identity --profile superstore-restore` và log restore cùng lượt |
| B12 — S3 retention | Object Lock/retention đang áp dụng cho object backup | Not Run | Cần kiểm tra cấu hình bucket và object trên AWS |
| B13 — Dọn file tạm | `work.*` trên VPS không còn sau lượt thành công | Not Run | Cần kiểm tra trên VPS sau backup; script có `trap` nhưng chưa có bằng chứng filesystem |
| B14 — Khôi phục VPS | Staff DB, cấu hình và đúng release hoạt động trên VPS thử nghiệm | Not Run | Cần restore drill trên VPS staging/máy tạm và smoke sau khôi phục |

Khi chạy lại, cập nhật **ngày, kết quả và bằng chứng của từng gate**. Không giữ `Verified` của lượt cũ để mô tả trạng thái hiện tại nếu cấu hình hoặc môi trường đã đổi.

## Tiêu chí hoàn tất

- [x] Backup thủ công tạo object đã mã hóa trên S3 và xác minh checksum.
- [x] Restore local giải mã được và staff SQLite đạt integrity check.
- [ ] Có một lượt backup tự động do timer kích hoạt thành công.
- [ ] Xác minh IAM restore, retention và dọn file tạm trên VPS.
- [ ] Diễn tập dựng VPS mới từ artifact và kiểm tra API/staff sau restore.

## Tài liệu liên quan

- Lệnh vận hành: [Backup trong Deploy Operations](../operation.md#12-backup).
- Luồng file: [Backup Architecture](system_architecture_lineage.md).
