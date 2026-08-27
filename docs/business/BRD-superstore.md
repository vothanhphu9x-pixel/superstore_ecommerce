# BRD — TÀI LIỆU YÊU CẦU KINH DOANH

## Superstore ERP & Data Platform

### Business Requirements Document · Phiên bản 1.0 · 2026

---

## 1. Thông tin dự án

| Thuộc tính    | Giá trị                                    |
| ------------- | ------------------------------------------ |
| Tên dự án     | Superstore ERP & Data Platform             |
| Phiên bản     | 1.0                                        |
| Ngày tạo      | 2026                                       |
| Người tạo     | BA/Data Analyst — IT & Data Dept.          |
| Đối tượng đọc | Ban lãnh đạo, trưởng phòng, đội triển khai |
| Trạng thái    | Đã duyệt                                   |

**Mô tả ngắn:** Dự án này triển khai hệ thống ERP (Enterprise Resource Planning — Hoạch định nguồn lực doanh nghiệp) trên nền Odoo 18 Community tích hợp toàn bộ hoạt động kinh doanh của Superstore Inc. — bao gồm bán hàng, marketing, mua hàng, kho vận, sản xuất, kế toán, nhân sự — đồng thời xây dựng nền tảng dữ liệu (data platform) phục vụ phân tích và báo cáo quản trị.

---

## 2. Bối cảnh & Vấn đề kinh doanh

Superstore Inc. là công ty phân phối và sản xuất nội thất văn phòng tại Mỹ, hoạt động qua 4 kho vùng và 1 nhà máy. Trong giai đoạn tăng trưởng từ $15M lên $28,7M doanh thu (2021–2026), công ty gặp phải một loạt vấn đề vận hành do thiếu hệ thống quản lý tích hợp:

**Vấn đề 1 — Dữ liệu phân mảnh:** mỗi phòng dùng bảng tính Excel riêng → không có "single source of truth" (nguồn thông tin duy nhất tin cậy). Số liệu tồn kho, đơn hàng, công nợ thường xuyên không khớp giữa phòng ban.

**Vấn đề 2 — Thiếu khả năng phân tích:** ban lãnh đạo ra quyết định dựa trên báo cáo tổng hợp thủ công, chậm 5–7 ngày sau thực tế. Không thể phân tích nhanh "ngành hàng nào đang lỗ?" hay "kho nào giao trễ nhiều nhất?"

**Vấn đề 3 — Quy trình mua hàng & kho yếu:** thiếu 3-way match (đối chiếu 3 chứng từ trước khi thanh toán), dẫn đến thanh toán nhầm/thừa cho nhà cung cấp. Tồn kho không chính xác gây thiếu hàng hoặc tồn đọng vốn.

**Vấn đề 4 — Không theo dõi được hiệu quả marketing:** chi tiêu quảng cáo $X/tháng nhưng không biết kênh nào tạo ra đơn hàng, ROAS (Return on Ad Spend — doanh thu trên chi phí quảng cáo) bao nhiêu.

**Vấn đề 5 — Sản xuất không có kế hoạch chính xác:** lập kế hoạch sản xuất bằng cảm tính → thường xuyên thiếu nguyên vật liệu giữa chừng hoặc sản xuất dư gây tồn kho.

---

## 3. Mục tiêu kinh doanh (Business Objectives)

| Mã    | Mục tiêu                                                                         | Đo bằng                                                | Thời hạn |
| ----- | -------------------------------------------------------------------------------- | ------------------------------------------------------ | -------- |
| BO-01 | Có một nguồn dữ liệu duy nhất (single source of truth) cho toàn công ty          | Không còn báo cáo mâu thuẫn giữa phòng ban             | Đợt 0–1  |
| BO-02 | Theo dõi dòng chảy đơn hàng từ đầu đến cuối (Order-to-Cash) trong thời gian thực | Dashboard O2C refresh hằng ngày                        | Đợt 3    |
| BO-03 | Kiểm soát tồn kho chính xác theo từng kho, từng SKU                              | Sai lệch kiểm kê < 2%                                  | Đợt 2    |
| BO-04 | Thực hiện 3-way match tự động trong quy trình mua hàng                           | 100% hóa đơn NCC qua 3-way match trước thanh toán      | Đợt 2    |
| BO-05 | Đo lường hiệu quả marketing theo kênh (ROAS, CAC)                                | Báo cáo ROAS/CAC hằng tháng có sẵn                     | Đợt 3    |
| BO-06 | Lập và theo dõi kế hoạch sản xuất tự động dựa trên BOM                           | Tỷ lệ đạt kế hoạch sản xuất ≥ 95%                      | Đợt 2    |
| BO-07 | Quản lý công nợ khách hàng và nhà cung cấp tự động                               | DSO < 38 ngày; không quá hạn NCC                       | Đợt 2    |
| BO-08 | Xây dựng nền tảng dữ liệu (data platform) phục vụ phân tích chiến lược           | Dashboard Power BI cho ban lãnh đạo, refresh hàng ngày | Đợt 4–5  |

---

## 4. Bản đồ Stakeholder (Stakeholder Map)

| Nhóm                   | Đại diện                      | Vai trò trong dự án                                      | Mức quan tâm |
| ---------------------- | ----------------------------- | -------------------------------------------------------- | ------------ |
| **Chủ sở hữu**         | CEO Michael Tran              | Sponsor chính, phê duyệt ngân sách, quyết định cuối      | Rất cao      |
| **Tài chính**          | CFO Sarah Whitman             | Yêu cầu báo cáo tài chính US GAAP, phê duyệt P&L mô hình | Rất cao      |
| **Kinh doanh**         | Sales Director David Okafor   | Định nghĩa quy trình bán, nhận diện yêu cầu CRM          | Cao          |
| **Marketing**          | Anna Kowalski                 | Định nghĩa tracking chiến dịch, UTM, ROAS                | Cao          |
| **Kho vận**            | James Park                    | Quy trình nhận/xuất/chuyển kho, 4 location               | Cao          |
| **Sản xuất**           | Plant Manager Elena Rodriguez | BOM, routing, work center, kế hoạch sản xuất             | Cao          |
| **Mua hàng**           | Priya Sharma                  | Quy trình RFQ → PO → 3-way match                         | Cao          |
| **Kế toán**            | Robert Hayes                  | Chart of accounts, journal, đóng sổ tháng                | Cao          |
| **Nhân sự**            | HR Generalist                 | Hồ sơ nhân viên, hợp đồng                                | Trung bình   |
| **IT/Data**            | Data Analyst (bạn)            | Triển khai, pipeline, BI — người thực thi chính          | Rất cao      |
| **Nhân viên vận hành** | 45 nhân viên                  | Người dùng cuối hàng ngày                                | Trung bình   |

---

## 5. Phạm vi dự án (Scope)

### 5.1. Trong phạm vi (In-scope)

- Triển khai Odoo 18 Community cho 8 phòng ban: Sales/CRM, Marketing, Purchasing, Warehouse (4 kho), Manufacturing, Accounting, HR, Data Ops
- 3 value stream chính: Order-to-Cash (O2C), Procure-to-Pay (P2P), Plan-to-Produce
- Dataset Superstore (2023–2026, scale ×50) + live simulator 2027 làm nguồn dữ liệu
- Digital marketing: UTM tracking trong Odoo + external ad-spend data (multi-source)
- Data platform: CDC Debezium → Kafka → MinIO → dbt → Snowflake → Power BI
- Bộ tài liệu BA đầy đủ (BRD, FRD ×8, SRS, Use Cases) bằng tiếng Việt
- RAG chatbot cho knowledge base nội bộ (dùng Qdrant + LLM)

### 5.2. Ngoài phạm vi (Out-scope)

- Website thương mại điện tử (e-commerce frontend)
- Tích hợp trực tiếp với hệ thống bên ngoài (API hãng vận chuyển, cổng thanh toán)
- Payroll chi tiết (thuế thu nhập, bảo hiểm — chỉ đến mức hợp đồng + lương cơ bản)
- Module Enterprise (Studio, Quality, Subscriptions) — dùng bản Community
- Đào tạo nhân viên cuối (end-user training) — ngoài phạm vi tài liệu kỹ thuật

---

## 6. Yêu cầu chức năng cấp cao (High-level Functional Requirements)

| Mã         | Mô tả                                                                         | Phòng ban     | Trace về |
| ---------- | ----------------------------------------------------------------------------- | ------------- | -------- |
| FR-GEN-01  | Hệ thống phải hoạt động với currency USD, country = US, multiple warehouses   | Tất cả        | BO-01    |
| FR-GEN-02  | Mọi chứng từ phải có chuỗi audit (ai tạo, ai sửa, khi nào)                    | Tất cả        | BO-01    |
| FR-SAL-01  | Hệ thống quản lý lead → opportunity → quotation → sales order trong một luồng | Sales/CRM     | BO-02    |
| FR-SAL-02  | Hỗ trợ chiết khấu theo bậc sản lượng B2B (5/10/15/20%)                        | Sales         | BO-02    |
| FR-SAL-03  | Đơn > $10K phải có Sales Director approval trước khi confirm                  | Sales         | BO-02    |
| FR-MKT-01  | Mọi lead và SO phải gắn được UTM campaign/source/medium                       | Marketing     | BO-05    |
| FR-MKT-02  | Hệ thống nhận và lưu external ad-spend data theo ngày, chiến dịch, kênh       | Marketing     | BO-05    |
| FR-PUR-01  | Quy trình mua: yêu cầu → RFQ → PO → goods receipt → 3-way match → thanh toán  | Purchasing    | BO-04    |
| FR-PUR-02  | Đơn mua > $5.000 phải có ít nhất 2 RFQ                                        | Purchasing    | BO-04    |
| FR-WH-01   | Hệ thống quản lý 4 kho độc lập với tồn kho riêng từng SKU từng kho            | Warehouse     | BO-03    |
| FR-WH-02   | Hỗ trợ chuyển kho liên vùng (inter-warehouse transfer)                        | Warehouse     | BO-03    |
| FR-MFG-01  | BOM đa cấp (2–3 cấp) cho dòng Furniture; routing qua 3 work center            | Manufacturing | BO-06    |
| FR-MFG-02  | Lệnh sản xuất (MO) sinh ra tự động từ kế hoạch hoặc đơn hàng thiếu tồn        | Manufacturing | BO-06    |
| FR-ACC-01  | Hóa đơn bán/mua được ghi sổ theo double-entry (Nợ = Có)                       | Accounting    | BO-07    |
| FR-ACC-02  | Quản lý công nợ phải thu (AR) và phải trả (AP) với cảnh báo quá hạn           | Accounting    | BO-07    |
| FR-HR-01   | Hồ sơ nhân viên với phòng ban, chức danh, hợp đồng, mức lương                 | HR            | BO-01    |
| FR-DATA-01 | CDC pipeline: Debezium → Kafka → MinIO → dbt → Snowflake                      | Data Ops      | BO-08    |
| FR-DATA-02 | Dashboard Power BI phân tích Sales/Inventory/Finance/Manufacturing/Marketing  | Data Ops      | BO-08    |

---

## 7. Yêu cầu phi chức năng (Non-functional Requirements)

- **Hiệu năng:** web server Odoo response < 2 giây cho thao tác thông thường; batch import 10.000 records < 5 phút
- **Độ sẵn sàng:** môi trường dev (MacBook) uptime khi cần; môi trường prod (VPS) target 99% trong giờ hành chính
- **Bảo mật:** phân quyền theo phòng ban (user chỉ thấy menu của phòng mình); admin login bảo vệ password mạnh
- **Dữ liệu:** backup database hằng ngày; logs lưu tối thiểu 90 ngày
- **Khả năng mở rộng:** schema database và pipeline thiết kế để thêm nguồn dữ liệu mới (marketing API, ERP module mới)

---

## 8. Tiêu chí thành công (Success Criteria)

| Tiêu chí                                                     | Đo bằng                 | Mục tiêu            |
| ------------------------------------------------------------ | ----------------------- | ------------------- |
| Toàn bộ 8 phòng ban vận hành trên Odoo                       | % phòng ban đã go-live  | 100%                |
| Tồn kho ERP khớp kiểm kê thực tế                             | Sai lệch %              | < 2%                |
| Báo cáo ban lãnh đạo từ Power BI                             | Độ trễ dữ liệu          | < 24 giờ            |
| Không còn mâu thuẫn số liệu giữa phòng                       | Số incident báo cáo sai | 0/tháng sau 3 tháng |
| Chatbot nội bộ trả lời được câu hỏi về chính sách, quy trình | Độ chính xác trả lời    | ≥ 80% câu hỏi test  |

---

## 9. Rủi ro & Biện pháp giảm thiểu

| Rủi ro                                               | Xác suất | Tác động   | Biện pháp                                                            |
| ---------------------------------------------------- | -------- | ---------- | -------------------------------------------------------------------- |
| Full MRP (work center/routing) phức tạp quá → sa lầy | Cao      | Trung bình | Giới hạn 3 work center, 2–3 công đoạn/sản phẩm, 3 sản phẩm mẫu       |
| Pipeline CDC lỗi khi schema Odoo thay đổi            | Thấp     | Cao        | dbt schema tests + alerts; không upgrade Odoo khi đang chạy pipeline |

---

## 10. Tài liệu liên quan

- Hồ sơ công ty: `superstore-ho-so-cong-ty-vi.md`
- Master Plan: `master-plan-superstore-erp-v2.md`
- FRD-01 Sales & CRM: `FRD-01-sales-crm.md`
- FRD-02 Marketing: `FRD-02-marketing.md`
- FRD-03 Purchasing: `FRD-03-purchasing.md`
- FRD-04 Warehouse: `FRD-04-warehouse.md`
- FRD-05 Manufacturing: `FRD-05-manufacturing.md`
- FRD-06 Accounting: `FRD-06-accounting.md`
- FRD-07 HR: `FRD-07-hr.md`
- FRD-08 Data Ops: `FRD-08-data-ops.md`
- SRS: `SRS-superstore.md`
- Use Cases: `UC-superstore.md`
