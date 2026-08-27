# ODOO ERP — SỔ TAY 27 MODELS

### Tài liệu học tập: định nghĩa · mục đích · fields · quan hệ · ví dụ

> **Cách đọc tài liệu này:**
>
> - Mỗi model có: định nghĩa 1 câu → vì sao tồn tại → fields quan trọng → quan hệ → ví dụ dữ liệu thật
> - Ký hiệu: 🔑 = Primary Key · 🔗 = Foreign Key · ⭐ = model cốt lõi phải nắm chắc
> - Quy ước tên: model Odoo dùng dấu chấm (`sale.order`), bảng PostgreSQL dùng gạch dưới (`sale_order`)
> - Thứ tự trình bày = thứ tự dependency = thứ tự build

---

# MODULE 1 — 🧱 FOUNDATION (base)

**Vai trò:** Master data dùng chung. Mọi module khác đều trỏ về đây. Build ĐẦU TIÊN.

---

## 1.1. res.company — Công ty

**Định nghĩa:** Pháp nhân đang vận hành hệ thống — chính là công ty của bạn.

**Vì sao tồn tại:** Odoo hỗ trợ multi-company (1 database chạy nhiều công ty con). Mọi chứng từ đều phải biết nó thuộc công ty nào để tách sổ sách, tách kho, tách báo cáo.

**Fields quan trọng:**

| Field          | Kiểu           | Ý nghĩa                                      |
| -------------- | -------------- | -------------------------------------------- |
| id 🔑          | integer        | Định danh                                    |
| name           | varchar        | Tên công ty (VD: "Công ty TNHH ABC Trading") |
| currency_id 🔗 | → res_currency | Tiền tệ mặc định (VND)                       |
| partner_id 🔗  | → res_partner  | Công ty cũng là 1 partner (có địa chỉ, MST)  |
| parent_id 🔗   | → res_company  | Công ty mẹ (nếu là công ty con)              |

**Quan hệ:** Gốc của tất cả — hầu hết bảng transaction đều có cột `company_id` trỏ về đây.

**Ví dụ:** `(1, 'ABC Trading Co., Ltd', currency=VND)`

---

## 1.2. ⭐ res.partner — Đối tác (QUAN TRỌNG NHẤT HỆ THỐNG)

**Định nghĩa:** MỘT bảng duy nhất chứa TẤT CẢ các bên bạn làm việc cùng: khách hàng, nhà cung cấp, liên hệ cá nhân, và cả chính công ty bạn.

**Vì sao tồn tại:** Thực tế một công ty có thể vừa mua của bạn vừa bán cho bạn. Nếu tách bảng `customer` và `supplier` riêng → phải lưu thông tin họ 2 lần → sửa địa chỉ ở bảng này quên bảng kia → dữ liệu mâu thuẫn. Giải pháp: 1 bảng + cờ phân vai trò.

**Fields quan trọng:**

| Field                      | Kiểu          | Ý nghĩa                                            |
| -------------------------- | ------------- | -------------------------------------------------- |
| id 🔑                      | integer       | Định danh                                          |
| name                       | varchar       | Tên đối tác                                        |
| is_company                 | boolean       | true = công ty, false = cá nhân                    |
| customer_rank              | integer       | > 0 → là KHÁCH HÀNG (số càng cao = mua càng nhiều) |
| supplier_rank              | integer       | > 0 → là NHÀ CUNG CẤP                              |
| parent_id 🔗               | → res_partner | Nếu là contact cá nhân → trỏ về công ty của họ     |
| vat                        | varchar       | Mã số thuế                                         |
| street / city / country_id |               | Địa chỉ                                            |
| email / phone              |               | Liên hệ                                            |

**Cách đọc vai trò:**

| customer_rank | supplier_rank | Nghĩa là                        |
| ------------- | ------------- | ------------------------------- |
| 5             | 0             | Khách hàng thuần                |
| 0             | 3             | Nhà cung cấp thuần              |
| 2             | 4             | Vừa là khách vừa là NCC         |
| 0             | 0             | Chỉ là contact (chưa giao dịch) |

**Quan hệ:**

- `sale_order.partner_id` → đây (với vai trò customer)
- `purchase_order.partner_id` → đây (với vai trò supplier)
- `account_move.partner_id` → đây (đối tượng công nợ)
- `parent_id` → tự trỏ về chính nó (anh Tuấn là contact của công ty XYZ)

**Ví dụ:**

```
(10, 'Công ty XYZ',       is_company=T, customer_rank=5, supplier_rank=0)
(11, 'Nguyễn Văn Tuấn',   is_company=F, parent_id=10)   ← contact của XYZ
(20, 'NCC Kim Long',      is_company=T, customer_rank=0, supplier_rank=8)
```

---

## 1.3. res.users — Người dùng hệ thống

**Định nghĩa:** Tài khoản đăng nhập vào Odoo (nhân viên thao tác hệ thống).

**Vì sao tồn tại:** Phân biệt AI LÀM GÌ. Mỗi đơn hàng ghi lại `user_id` — người tạo. Phục vụ phân quyền và audit.

**Fields quan trọng:**

| Field         | Kiểu          | Ý nghĩa                                |
| ------------- | ------------- | -------------------------------------- |
| id 🔑         | integer       | Định danh                              |
| login         | varchar       | Tên đăng nhập                          |
| partner_id 🔗 | → res_partner | User cũng là 1 partner (có tên, email) |
| company_id 🔗 | → res_company | Thuộc công ty nào                      |

**Quan hệ:** 1 user ↔ 1 partner. Các chứng từ có `user_id`/`create_uid` trỏ về đây.

**Điểm hay:** Ngay cả user cũng là partner → thấy chưa, res.partner đúng nghĩa "1 bảng cho mọi con người/tổ chức".

---

## 1.4. res.currency — Tiền tệ

**Định nghĩa:** Danh mục tiền tệ (VND, USD, EUR) kèm tỷ giá.

**Vì sao tồn tại:** Công ty Trading có thể nhập hàng bằng USD, bán bằng VND. Mọi số tiền trong hệ thống phải biết nó đang ở tiền tệ nào để quy đổi.

**Fields quan trọng:**

| Field  | Kiểu    | Ý nghĩa                            |
| ------ | ------- | ---------------------------------- |
| id 🔑  | integer | Định danh                          |
| name   | varchar | Mã (VND, USD)                      |
| symbol | varchar | Ký hiệu (₫, $)                     |
| rate   | numeric | Tỷ giá so với currency của company |

**Quan hệ:** `res_company`, `sale_order`, `account_move`... đều có `currency_id` trỏ về đây.

---

# MODULE 2 — 📦 PRODUCT (product)

**Vai trò:** Danh mục sản phẩm. Sales, Purchase, Inventory đều trỏ về đây. Điểm khó nhất: phân biệt **template vs variant**.

---

## 2.1. product.category — Nhóm sản phẩm

**Định nghĩa:** Cây phân loại sản phẩm nhiều cấp.

**Vì sao tồn tại:** Để phân tích và quản lý theo nhóm ("doanh thu ngành hàng Điện tử quý này?"). Cấu trúc CÂY qua `parent_id` — giống thư mục máy tính.

**Fields quan trọng:**

| Field        | Kiểu               | Ý nghĩa                    |
| ------------ | ------------------ | -------------------------- |
| id 🔑        | integer            | Định danh                  |
| name         | varchar            | Tên nhóm                   |
| parent_id 🔗 | → product_category | Nhóm cha (NULL = nhóm gốc) |

**Ví dụ cây:**

```
(1, 'All',       parent=NULL)
(2, 'Điện tử',   parent=1)
(3, 'Laptop',    parent=2)
(4, 'Gaming',    parent=3)     ← All > Điện tử > Laptop > Gaming
```

**Liên hệ với bạn:** Đây chính là hierarchy mà nếu đưa vào warehouse dạng nhiều bảng → thành Snowflake Schema; flatten thành 1 bảng dim_product có cột category/sub_category → thành Star Schema (như Superstore của bạn).

---

## 2.2. ⭐ product.template — Sản phẩm mẫu (khái niệm)

**Định nghĩa:** Sản phẩm ở mức KHÁI NIỆM — chưa cụ thể hóa thuộc tính. "Áo thun Basic" là template; chưa nói màu gì size gì.

**Vì sao tồn tại:** Thông tin chung (mô tả, nhóm, chính sách giá) chỉ nên lưu 1 lần cho cả họ sản phẩm, thay vì lặp lại cho từng biến thể màu/size.

**Fields quan trọng:**

| Field          | Kiểu               | Ý nghĩa                                  |
| -------------- | ------------------ | ---------------------------------------- |
| id 🔑          | integer            | Định danh                                |
| name           | varchar            | Tên SP                                   |
| list_price     | numeric            | GIÁ BÁN niêm yết                         |
| standard_price | numeric            | GIÁ VỐN                                  |
| categ_id 🔗    | → product_category | Thuộc nhóm nào                           |
| type           | selection          | 'consu' (hàng hóa) / 'service' (dịch vụ) |
| uom_id 🔗      | → uom_uom          | Đơn vị tính mặc định                     |

**Quan hệ:** 1 template → N variant (product.product).

---

## 2.3. ⭐ product.product — Sản phẩm variant (SKU thật)

**Định nghĩa:** Sản phẩm CỤ THỂ có thể cầm nắm, đếm, bán được. "Áo thun Basic - Đỏ - Size L" là variant. **SKU nằm ở đây.**

**Vì sao tồn tại:** Kho không thể đếm "Áo thun Basic" chung chung — kho đếm từng biến thể cụ thể. Đơn hàng cũng bán biến thể cụ thể.

**Fields quan trọng:**

| Field              | Kiểu               | Ý nghĩa                  |
| ------------------ | ------------------ | ------------------------ |
| id 🔑              | integer            | Định danh                |
| product_tmpl_id 🔗 | → product_template | Thuộc template nào       |
| default_code       | varchar            | **SKU** (mã hàng nội bộ) |
| barcode            | varchar            | Mã vạch                  |

**QUY TẮC VÀNG:** Mọi order line, stock move đều trỏ vào **product.product** (variant), KHÔNG BAO GIỜ trỏ vào template.

**Ví dụ:**

```
Template: (1, 'Áo thun Basic', list_price=150000)
Variants: (101, tmpl=1, sku='AT-DO-L')   ← Đỏ, L
          (102, tmpl=1, sku='AT-DO-M')   ← Đỏ, M
          (103, tmpl=1, sku='AT-XANH-L') ← Xanh, L
```

Tồn kho của 101 = 50 cái, của 102 = 0 cái → phải quản ở mức variant mới biết hết size M.

---

## 2.4. uom.uom — Đơn vị tính

**Định nghĩa:** Đơn vị đo lường (Cái, Thùng, Kg, Lít) + hệ số quy đổi.

**Vì sao tồn tại:** Mua theo THÙNG (24 lon), bán theo LON. Hệ thống phải tự quy đổi: nhập 10 thùng = tồn 240 lon.

**Fields quan trọng:**

| Field          | Kiểu           | Ý nghĩa                                   |
| -------------- | -------------- | ----------------------------------------- |
| id 🔑          | integer        | Định danh                                 |
| name           | varchar        | Tên đơn vị                                |
| category_id 🔗 | → uom_category | Nhóm quy đổi (Đơn vị đếm / Khối lượng...) |
| factor         | numeric        | Hệ số so với đơn vị chuẩn của nhóm        |

**Lưu ý:** Chỉ quy đổi được TRONG CÙNG category (Thùng ↔ Lon được; Kg ↔ Lít không).

---

# MODULE 3 — 🛍️ PURCHASE (purchase)

**Vai trò:** Mua hàng từ NCC — điểm khởi đầu dòng chảy "tiền ra, hàng vào". Cấu trúc đơn giản: đúng 1 cặp Header/Line.

---

## 3.1. purchase.order — Đơn mua hàng (HEADER)

**Định nghĩa:** Chứng từ đặt mua hàng gửi cho nhà cung cấp. Phần HEADER: thông tin chung của cả đơn.

**Vì sao tồn tại:** Cam kết mua chính thức — căn cứ để NCC giao hàng, để kho nhận hàng, để kế toán đối chiếu hóa đơn (3-way match: PO ↔ phiếu nhập ↔ hóa đơn NCC).

**Fields quan trọng:**

| Field                                      | Kiểu           | Ý nghĩa                                     |
| ------------------------------------------ | -------------- | ------------------------------------------- |
| id 🔑                                      | integer        | Định danh                                   |
| name                                       | varchar        | Số PO (VD: P00001)                          |
| partner_id 🔗                              | → res_partner  | NHÀ CUNG CẤP (supplier_rank > 0)            |
| date_order                                 | timestamp      | Ngày đặt                                    |
| state                                      | selection      | draft → sent → **purchase** → done / cancel |
| amount_untaxed / amount_tax / amount_total | numeric        | Tiền trước thuế / thuế / tổng               |
| currency_id 🔗                             | → res_currency | Tiền tệ (nhập hàng có thể là USD)           |

**State machine:**

```
draft (nháp) → sent (đã gửi NCC) → purchase (NCC xác nhận) → done (nhận đủ hàng)
                                                            ↘ cancel
```

**Quan hệ:** 1 PO → N purchase_order_line. Khi confirm → hệ thống TỰ SINH stock_picking (phiếu nhận hàng) bên module Inventory.

---

## 3.2. purchase.order.line — Dòng đơn mua (LINE)

**Định nghĩa:** Chi tiết từng sản phẩm trong đơn mua: SP nào, bao nhiêu, giá nhập bao nhiêu.

**Vì sao tồn tại:** (Xem lại pattern Header/Line) — 1 đơn mua nhiều SP, mỗi SP 1 dòng, tránh lặp thông tin header.

**Fields quan trọng:**

| Field          | Kiểu              | Ý nghĩa                                           |
| -------------- | ----------------- | ------------------------------------------------- |
| id 🔑          | integer           | Định danh                                         |
| order_id 🔗    | → purchase_order  | Thuộc PO nào                                      |
| product_id 🔗  | → product_product | SP variant nào                                    |
| product_qty    | numeric           | Số lượng đặt                                      |
| qty_received   | numeric           | Số lượng ĐÃ NHẬN (so sánh để biết NCC giao thiếu) |
| price_unit     | numeric           | GIÁ NHẬP đơn vị                                   |
| product_uom 🔗 | → uom_uom         | Đơn vị tính                                       |

**Giá trị phân tích:** Đây là nguồn của `fact_purchase` — phân tích chi phí nhập theo NCC, theo SP, độ trễ giao hàng (`qty_received` vs `product_qty`).

---

# MODULE 4 — 🏪 INVENTORY (stock)

**Vai trò:** Quản kho. Module PHỨC TẠP NHẤT vì triết lý: **tồn kho = kết quả của các chuyển động, không phải con số sửa tay.**

---

## 4.1. stock.warehouse — Kho hàng

**Định nghĩa:** Kho VẬT LÝ — một tòa nhà/địa điểm chứa hàng.

**Vì sao tồn tại:** Công ty có thể có nhiều kho (Kho HN, Kho HCM). Báo cáo tồn phải tách được theo kho.

**Fields quan trọng:**

| Field         | Kiểu          | Ý nghĩa           |
| ------------- | ------------- | ----------------- |
| id 🔑         | integer       | Định danh         |
| name          | varchar       | Tên kho           |
| code          | varchar       | Mã ngắn (WH-HCM)  |
| company_id 🔗 | → res_company | Thuộc công ty nào |

**Quan hệ:** 1 warehouse → N stock_location.

---

## 4.2. stock.location — Vị trí lưu trữ

**Định nghĩa:** Vị trí LOGIC trong hệ thống kho — có thể là kệ thật trong kho, hoặc vị trí "ảo" đại diện cho thế giới bên ngoài.

**Vì sao tồn tại:** Đây là thiết kế thông minh nhất của module: để MỌI di chuyển hàng đều mô tả được dưới dạng "từ location A → location B", Odoo tạo cả location ẢO:

| usage     | Nghĩa                   | Ví dụ                              |
| --------- | ----------------------- | ---------------------------------- |
| internal  | Vị trí thật trong kho   | WH-HCM/Kệ-A1                       |
| supplier  | Ảo — "thế giới NCC"     | Nhập hàng = move từ đây → internal |
| customer  | Ảo — "thế giới khách"   | Xuất bán = move từ internal → đây  |
| inventory | Ảo — điều chỉnh kiểm kê | Hàng mất = move từ internal → đây  |

**Fields quan trọng:**

| Field          | Kiểu             | Ý nghĩa                                    |
| -------------- | ---------------- | ------------------------------------------ |
| id 🔑          | integer          | Định danh                                  |
| name           | varchar          | Tên vị trí                                 |
| usage          | selection        | internal / supplier / customer / inventory |
| location_id 🔗 | → stock_location | Vị trí cha (cây phân cấp)                  |

---

## 4.3. stock.picking — Phiếu giao/nhận (HEADER)

**Định nghĩa:** Chứng từ gom một LẦN giao/nhận hàng — header của các move.

**Vì sao tồn tại:** Một lần xe tải đến giao 5 SP = 1 picking chứa 5 move. Nhân viên kho làm việc theo phiếu, không theo từng move lẻ.

**Fields quan trọng:**

| Field              | Kiểu          | Ý nghĩa                                                        |
| ------------------ | ------------- | -------------------------------------------------------------- |
| id 🔑              | integer       | Định danh                                                      |
| name               | varchar       | Số phiếu (WH/IN/00001, WH/OUT/00001)                           |
| partner_id 🔗      | → res_partner | Giao cho ai / nhận từ ai                                       |
| picking_type_id 🔗 |               | Loại: Receipt (nhận) / Delivery (giao) / Internal (chuyển kho) |
| state              | selection     | draft → confirmed → assigned → **done**                        |
| origin             | varchar       | Chứng từ nguồn (số SO/PO sinh ra phiếu này)                    |

**Quan hệ:** Sinh TỰ ĐỘNG khi confirm SO/PO. Cột `origin` là sợi dây truy vết ngược về đơn gốc.

---

## 4.4. ⭐ stock.move — Chuyển động hàng hóa

**Định nghĩa:** MỘT lần MỘT sản phẩm di chuyển từ location này sang location khác. Đơn vị nguyên tử của mọi biến động kho.

**Vì sao tồn tại:** Triết lý "ghi sự kiện, đừng ghi đè". Nhập kho, xuất kho, chuyển kho, kiểm kê điều chỉnh — TẤT CẢ đều là move. Nhờ đó mọi biến động tồn kho đều truy vết được.

**Fields quan trọng:**

| Field               | Kiểu              | Ý nghĩa                                 |
| ------------------- | ----------------- | --------------------------------------- |
| id 🔑               | integer           | Định danh                               |
| picking_id 🔗       | → stock_picking   | Thuộc phiếu nào                         |
| product_id 🔗       | → product_product | SP variant nào                          |
| product_uom_qty     | numeric           | Số lượng                                |
| location_id 🔗      | → stock_location  | Vị trí NGUỒN                            |
| location_dest_id 🔗 | → stock_location  | Vị trí ĐÍCH                             |
| state               | selection         | draft → confirmed → assigned → **done** |
| date                | timestamp         | Thời điểm thực hiện                     |

**Đọc nghiệp vụ qua cặp location:**

```
supplier → internal   = NHẬP HÀNG từ NCC
internal → customer   = XUẤT BÁN cho khách
internal → internal   = CHUYỂN KHO nội bộ
internal → inventory  = HÀNG MẤT/hỏng (kiểm kê)
```

**Giá trị phân tích:** Nguồn của `fact_inventory_movement`. Chỉ move `state='done'` mới tính vào tồn kho.

---

## 4.5. ⭐ stock.quant — Tồn kho hiện tại

**Định nghĩa:** "Ảnh chụp" số lượng THỰC TẾ của 1 SP tại 1 location NGAY LÚC NÀY.

**Vì sao tồn tại:** Về lý thuyết, tồn kho = SUM tất cả move done. Nhưng query tổng hàng triệu move mỗi lần xem tồn thì quá chậm → Odoo duy trì bảng quant như một "bộ đệm kết quả", tự cập nhật mỗi khi move done.

**Fields quan trọng:**

| Field             | Kiểu              | Ý nghĩa                             |
| ----------------- | ----------------- | ----------------------------------- |
| id 🔑             | integer           | Định danh                           |
| product_id 🔗     | → product_product | SP nào                              |
| location_id 🔗    | → stock_location  | Tại vị trí nào                      |
| quantity          | numeric           | Đang có bao nhiêu                   |
| reserved_quantity | numeric           | Đã giữ chỗ cho đơn hàng (chưa xuất) |

**Cặp khái niệm cần nắm:**

- **stock.move** = SỔ NHẬT KÝ (lịch sử, immutable, ghi mãi)
- **stock.quant** = SỐ DƯ (hiện tại, derived, tự tính lại)

→ Giống hệt quan hệ sao kê ↔ số dư tài khoản ngân hàng. Và giống quan hệ **CDC event log ↔ current table** trong pipeline của bạn!

---

# MODULE 5 — 🛒 SALES & CRM (sale / crm)

**Vai trò:** Bán hàng — nguồn doanh thu, nơi sinh `fact_sales`.

---

## 5.1. crm.lead — Lead / Cơ hội bán hàng

**Định nghĩa:** Khách hàng TIỀM NĂNG — người quan tâm nhưng chưa mua.

**Vì sao tồn tại:** Quản pipeline bán hàng TRƯỚC khi có đơn: ai đang quan tâm, ở giai đoạn nào, dự kiến bao nhiêu tiền, xác suất chốt.

**Fields quan trọng:**

| Field            | Kiểu          | Ý nghĩa                                            |
| ---------------- | ------------- | -------------------------------------------------- |
| id 🔑            | integer       | Định danh                                          |
| name             | varchar       | Tên cơ hội ("Công ty XYZ cần 500 laptop")          |
| partner_id 🔗    | → res_partner | Đối tác (có thể NULL nếu lead mới)                 |
| stage_id 🔗      | → crm_stage   | Giai đoạn: New → Qualified → Proposition → **Won** |
| expected_revenue | numeric       | Doanh thu kỳ vọng                                  |
| probability      | numeric       | Xác suất chốt (%)                                  |
| user_id 🔗       | → res_users   | Sale phụ trách                                     |

**Quan hệ:** Lead **Won** → chuyển đổi (convert) thành sale.order. Phân tích funnel: bao nhiêu lead → bao nhiêu đơn (conversion rate).

---

## 5.2. ⭐ sale.order — Đơn bán hàng (HEADER)

**Định nghĩa:** Chứng từ bán hàng — bắt đầu là BÁO GIÁ (quotation), khách đồng ý thì thành ĐƠN HÀNG. Cùng 1 record, chỉ đổi state.

**Vì sao tồn tại:** Trung tâm của nghiệp vụ bán: cam kết với khách về SP, giá, thời hạn. Confirm nó = kích hoạt dây chuyền (xuất kho + hóa đơn).

**Fields quan trọng:**

| Field                                      | Kiểu          | Ý nghĩa                                                     |
| ------------------------------------------ | ------------- | ----------------------------------------------------------- |
| id 🔑                                      | integer       | Định danh                                                   |
| name                                       | varchar       | Số SO (S00001)                                              |
| partner_id 🔗                              | → res_partner | KHÁCH HÀNG (customer_rank > 0)                              |
| date_order                                 | timestamp     | Ngày đặt                                                    |
| state                                      | selection     | **draft** (báo giá) → sent → **sale** (đơn) → done / cancel |
| amount_untaxed / amount_tax / amount_total | numeric       | Tiền hàng / thuế / tổng                                     |
| user_id 🔗                                 | → res_users   | Nhân viên sale                                              |
| invoice_status                             | selection     | no / to invoice / invoiced                                  |

**Điểm tinh tế:** Báo giá và đơn hàng là CÙNG MỘT BẢNG — `state='draft'` là báo giá, `state='sale'` là đơn. Đỡ phải copy dữ liệu giữa 2 bảng.

**Dây chuyền khi Confirm (draft → sale):**

```
1. state đổi thành 'sale'
2. TỰ SINH stock.picking (WH/OUT) + stock.move (internal → customer)
3. Sẵn sàng tạo account.move (hóa đơn) khi giao xong
```

→ 1 cú click = events trên 4-5 bảng. Đây là "chùm CDC event" Debezium của bạn sẽ thấy.

---

## 5.3. ⭐ sale.order.line — Dòng đơn bán (LINE)

**Định nghĩa:** Chi tiết từng SP trong đơn bán: SP, số lượng, đơn giá, chiết khấu.

**Vì sao tồn tại:** Pattern Header/Line. Và với BẠN: đây là bảng quan trọng nhất toàn hệ thống về mặt analytics — **nguồn trực tiếp của fact_sales**.

**Fields quan trọng:**

| Field           | Kiểu              | Ý nghĩa                         |
| --------------- | ----------------- | ------------------------------- |
| id 🔑           | integer           | Định danh                       |
| order_id 🔗     | → sale_order      | Thuộc SO nào                    |
| product_id 🔗   | → product_product | SP variant                      |
| product_uom_qty | numeric           | Số lượng đặt                    |
| qty_delivered   | numeric           | Đã giao                         |
| qty_invoiced    | numeric           | Đã xuất hóa đơn                 |
| price_unit      | numeric           | Đơn giá bán                     |
| discount        | numeric           | % chiết khấu                    |
| price_subtotal  | numeric           | Thành tiền (sau CK, trước thuế) |

**Grain của fact table:** 1 row sale_order_line = 1 row fact_sales. Đếm số đơn phải `COUNT(DISTINCT order_id)` — đúng bài học DISTINCTCOUNT bạn đã gặp ở Superstore.

**Margin analysis:** `price_subtotal` (từ đây) − `standard_price × qty` (từ product) = lợi nhuận gộp từng dòng.

---

# MODULE 6 — 💰 ACCOUNTING (account)

**Vai trò:** Kế toán — điểm HỘI TỤ. Mọi nghiệp vụ đổ về đây thành bút toán Nợ/Có. Đây là thứ làm hệ thống xứng danh "ERP".

---

## 6.1. account.account — Tài khoản kế toán (Chart of Accounts)

**Định nghĩa:** Danh mục "ngăn kéo" phân loại tiền: mỗi tài khoản là 1 ngăn (Tiền mặt, Phải thu, Doanh thu, Chi phí...).

**Vì sao tồn tại:** Kế toán không hỏi "có bao nhiêu tiền" mà hỏi "tiền đang nằm ở dạng nào": tiền mặt? khách nợ? hàng trong kho? Chart of Accounts (COA) là hệ thống ngăn kéo đó. VN dùng hệ thống tài khoản theo Thông tư 200.

**Fields quan trọng:**

| Field        | Kiểu      | Ý nghĩa                                       |
| ------------ | --------- | --------------------------------------------- |
| id 🔑        | integer   | Định danh                                     |
| code         | varchar   | Mã TK ('111', '131', '511')                   |
| name         | varchar   | Tên ('Tiền mặt', 'Phải thu KH', 'Doanh thu')  |
| account_type | selection | asset / liability / equity / income / expense |

**Mã TK Việt Nam thường gặp (TT200):**

```
111 Tiền mặt          131 Phải thu khách hàng
112 Tiền gửi NH       331 Phải trả người bán
156 Hàng hóa          3331 Thuế GTGT phải nộp
511 Doanh thu bán     632 Giá vốn hàng bán
```

---

## 6.2. account.journal — Sổ nhật ký

**Định nghĩa:** Kênh phân loại bút toán theo loại nghiệp vụ: sổ Bán hàng, sổ Mua hàng, sổ Ngân hàng, sổ Tiền mặt.

**Vì sao tồn tại:** Kế toán viên làm việc theo sổ ("hôm nay vào sổ bán hàng những HĐ nào?"). Mỗi journal có bộ đánh số chứng từ riêng (INV/2024/0001, BILL/2024/0001).

**Fields quan trọng:**

| Field | Kiểu      | Ý nghĩa                                 |
| ----- | --------- | --------------------------------------- |
| id 🔑 | integer   | Định danh                               |
| name  | varchar   | Tên sổ                                  |
| type  | selection | sale / purchase / bank / cash / general |
| code  | varchar   | Tiền tố số chứng từ (INV, BILL)         |

---

## 6.3. ⭐ account.move — Bút toán / Hóa đơn (HEADER)

**Định nghĩa:** Header của MỘT chứng từ kế toán. Hóa đơn bán, hóa đơn mua, bút toán điều chỉnh — TẤT CẢ đều là account.move, phân biệt bằng `move_type`.

**Vì sao tồn tại:** Thống nhất mọi chứng từ tài chính về 1 cấu trúc (SAP S/4HANA cũng làm y hệt với bảng ACDOCA — "universal journal"). Đơn giản hóa: 1 bảng, 1 luật cân bằng, mọi nghiệp vụ.

**Fields quan trọng:**

| Field                          | Kiểu              | Ý nghĩa                                                                                            |
| ------------------------------ | ----------------- | -------------------------------------------------------------------------------------------------- |
| id 🔑                          | integer           | Định danh                                                                                          |
| name                           | varchar           | Số chứng từ (INV/2024/0001)                                                                        |
| move_type                      | selection         | **out_invoice** (HĐ bán) / **in_invoice** (HĐ mua) / out_refund / in_refund / **entry** (bút toán) |
| partner_id 🔗                  | → res_partner     | Đối tượng công nợ                                                                                  |
| invoice_date                   | date              | Ngày hóa đơn                                                                                       |
| state                          | selection         | draft → **posted** (đã ghi sổ) → cancel                                                            |
| journal_id 🔗                  | → account_journal | Vào sổ nào                                                                                         |
| amount_total / amount_residual | numeric           | Tổng / CÒN NỢ (chưa thanh toán)                                                                    |

**`amount_residual` là field vàng cho phân tích công nợ:** = 0 là đã thu đủ, > 0 là khách còn nợ → báo cáo aging công nợ (nợ quá 30/60/90 ngày).

---

## 6.4. ⭐⭐ account.move.line — Dòng bút toán (LINE) — TRÁI TIM DOUBLE-ENTRY

**Định nghĩa:** Từng dòng Nợ (debit) / Có (credit) của một bút toán. **LUẬT SẮT: trong 1 move, tổng debit = tổng credit.**

**Vì sao tồn tại:** Nguyên lý kế toán kép 500 năm tuổi: mỗi đồng tiền đi ra từ đâu thì phải đi vào đâu đó. Ghi 2 chiều → tự kiểm tra chéo → không thể "mất tiền không dấu vết".

**Fields quan trọng:**

| Field         | Kiểu              | Ý nghĩa                    |
| ------------- | ----------------- | -------------------------- |
| id 🔑         | integer           | Định danh                  |
| move_id 🔗    | → account_move    | Thuộc bút toán nào         |
| account_id 🔗 | → account_account | Ghi vào TK nào             |
| partner_id 🔗 | → res_partner     | Đối tượng (cho TK công nợ) |
| debit         | numeric           | Số tiền NỢ                 |
| credit        | numeric           | Số tiền CÓ                 |
| date          | date              | Ngày ghi sổ                |

**Ví dụ trọn vẹn — bán hàng 110tr (VAT 10%):**

```
account.move (id=500, INV/2024/0001, out_invoice, partner=XYZ, total=110tr)
  ├── line 1: TK 131 Phải thu KH    debit=110tr   credit=0
  ├── line 2: TK 511 Doanh thu      debit=0       credit=100tr
  └── line 3: TK 3331 Thuế GTGT     debit=0       credit=10tr
                          Σ debit = 110tr = Σ credit ✓ CÂN
```

Đọc thành lời: "Khách XYZ nợ ta 110tr (Nợ 131), vì ta đã bán hàng tạo doanh thu 100tr (Có 511) và thu hộ nhà nước 10tr thuế (Có 3331)."

**Khi generate data:** move nào không cân → dữ liệu "giả" ngay lập tức. Đây là ràng buộc khó nhất và giá trị nhất khi build bộ data 10,000 dòng.

---

## 6.5. account.payment — Thanh toán

**Định nghĩa:** Ghi nhận một lần TIỀN THỰC SỰ di chuyển (khách trả tiền / ta trả NCC).

**Vì sao tồn tại:** Hóa đơn ≠ tiền. Xuất HĐ là ghi nhận NỢ; payment là ghi nhận TIỀN VỀ. Hai sự kiện tách biệt về thời gian (bán tháng 1, thu tiền tháng 3). Payment đối trừ (reconcile) với hóa đơn → `amount_residual` của hóa đơn giảm dần về 0.

**Fields quan trọng:**

| Field         | Kiểu              | Ý nghĩa                        |
| ------------- | ----------------- | ------------------------------ |
| id 🔑         | integer           | Định danh                      |
| partner_id 🔗 | → res_partner     | Ai trả / trả cho ai            |
| amount        | numeric           | Số tiền                        |
| payment_type  | selection         | inbound (thu) / outbound (chi) |
| date          | date              | Ngày thanh toán                |
| journal_id 🔗 | → account_journal | Qua kênh nào (Bank/Cash)       |

**Giá trị phân tích:** So `invoice_date` với payment `date` → DSO (Days Sales Outstanding) — khách trung bình bao lâu mới trả tiền. KPI tài chính quan trọng của Trading company.

---

# MODULE 7 — 👥 HR (hr)

**Vai trò:** Nhân sự. Độc lập với dòng chảy hàng hóa, chỉ chạm Accounting ở chi lương. Build CUỐI.

---

## 7.1. hr.department — Phòng ban

**Định nghĩa:** Đơn vị tổ chức trong công ty, cấu trúc cây.

| Field         | Kiểu            | Ý nghĩa                             |
| ------------- | --------------- | ----------------------------------- |
| id 🔑         | integer         | Định danh                           |
| name          | varchar         | Tên phòng ('Kinh doanh', 'Kho vận') |
| parent_id 🔗  | → hr_department | Phòng cha                           |
| manager_id 🔗 | → hr_employee   | Trưởng phòng                        |

**Điểm thú vị:** `manager_id` trỏ sang hr_employee, mà hr_employee lại có `department_id` trỏ ngược về đây — quan hệ vòng (circular). Khi generate data: tạo department với manager=NULL trước, tạo employee, rồi UPDATE lại manager.

---

## 7.2. hr.job — Chức danh

**Định nghĩa:** Vị trí công việc ('NV Kinh doanh', 'Kế toán trưởng', 'Thủ kho').

| Field            | Kiểu            | Ý nghĩa         |
| ---------------- | --------------- | --------------- |
| id 🔑            | integer         | Định danh       |
| name             | varchar         | Tên chức danh   |
| department_id 🔗 | → hr_department | Thuộc phòng nào |

---

## 7.3. hr.employee — Nhân viên

**Định nghĩa:** Hồ sơ nhân viên — con người thực làm việc trong công ty.

**Vì sao tách khỏi res.users:** Không phải nhân viên nào cũng có tài khoản đăng nhập (công nhân kho không cần login). Employee = hồ sơ nhân sự; User = quyền vào hệ thống. Hai khái niệm khác nhau.

| Field                   | Kiểu            | Ý nghĩa                       |
| ----------------------- | --------------- | ----------------------------- |
| id 🔑                   | integer         | Định danh                     |
| name                    | varchar         | Họ tên                        |
| department_id 🔗        | → hr_department | Phòng ban                     |
| job_id 🔗               | → hr_job        | Chức danh                     |
| user_id 🔗              | → res_users     | Tài khoản login (có thể NULL) |
| work_email / work_phone |                 | Liên hệ công việc             |

---

## 7.4. hr.contract — Hợp đồng lao động

**Định nghĩa:** Hợp đồng ký với nhân viên, chứa MỨC LƯƠNG và thời hạn.

**Vì sao tách khỏi employee:** 1 nhân viên có NHIỀU hợp đồng theo thời gian (thử việc → chính thức → tăng lương gia hạn). Lương nằm ở contract, không nằm ở employee — để giữ được LỊCH SỬ lương.

| Field                 | Kiểu          | Ý nghĩa                             |
| --------------------- | ------------- | ----------------------------------- |
| id 🔑                 | integer       | Định danh                           |
| employee_id 🔗        | → hr_employee | Của nhân viên nào                   |
| wage                  | numeric       | Lương cơ bản                        |
| date_start / date_end | date          | Hiệu lực từ / đến                   |
| state                 | selection     | draft → **open** (hiệu lực) → close |

**Liên hệ với bạn:** Chuỗi contract theo thời gian của 1 employee chính là dữ liệu SCD2 TỰ NHIÊN — mỗi lần tăng lương là 1 record mới với date_start/date_end. Nguồn luyện `dbt snapshot` tuyệt vời.

---

## 7.5. hr.payslip — Phiếu lương

**Định nghĩa:** Bảng lương MỘT KỲ (thường 1 tháng) của 1 nhân viên, tính từ contract.

| Field               | Kiểu          | Ý nghĩa             |
| ------------------- | ------------- | ------------------- |
| id 🔑               | integer       | Định danh           |
| employee_id 🔗      | → hr_employee | Của ai              |
| contract_id 🔗      | → hr_contract | Theo hợp đồng nào   |
| date_from / date_to | date          | Kỳ lương            |
| net_wage            | numeric       | Thực lãnh           |
| state               | selection     | draft → done → paid |

**Chạm Accounting:** Payslip xác nhận → sinh account.move (Nợ 642 Chi phí lương / Có 334 Phải trả NLĐ).

---

# 🗺️ BẢN ĐỒ QUAN HỆ TỔNG THỂ

```
                        ┌─────────────┐
                        │ res.company │
                        └──────┬──────┘
                               │
        ┌──────────────────────┼──────────────────────┐
        ▼                      ▼                      ▼
┌──────────────┐      ┌───────────────┐      ┌──────────────┐
│ ⭐res.partner │      │product.product│      │account.account│
│ (KH+NCC)     │      │ (SKU) ▲       │      │ (COA)        │
└──┬────┬────┬─┘      └───┬───┼───┬───┘      └──────┬───────┘
   │    │    │            │   │   │                 │
   │KH  │NCC │công nợ     │   │   │                 │
   ▼    ▼    ▼            ▼   ▼   ▼                 ▼
┌──────┐┌────────┐   ┌────────────────────┐  ┌────────────┐
│sale. ││purchase│   │ sale.order.line    │  │account.move│
│order ││.order  │   │ purchase.order.line│  │  (HĐ/BT)   │
└──┬───┘└───┬────┘   │ stock.move         │  └─────┬──────┘
   │1:N     │1:N     └────────────────────┘        │1:N
   ▼        ▼                                      ▼
 lines    lines      confirm SO/PO sinh ra:   move.lines
                     stock.picking → moves    (Σnợ = Σcó)
                     → cập nhật stock.quant
```

**Dòng chảy 1 giao dịch trọn vẹn (để ôn):**

```
1. crm.lead (Won)
2. → sale.order (draft→sale)           [Sales]
3. → stock.picking + stock.move        [Inventory] xuất kho
4. → stock.quant giảm                  [Inventory] tồn cập nhật
5. → account.move (out_invoice)        [Accounting] hóa đơn
6. → account.move.line (Nợ131=Có511+Có3331)  double-entry
7. → account.payment (inbound)         [Accounting] khách trả tiền
8. → amount_residual về 0              hết công nợ ✓
```

---

# 📋 CHECKLIST TỰ KIỂM TRA (học xong tick từng câu)

**Foundation:**

- [ ] Vì sao khách hàng và NCC chung 1 bảng? Phân biệt bằng field nào?
- [ ] parent_id trong res.partner dùng làm gì?

**Product:**

- [ ] Template khác Variant chỗ nào? SKU nằm ở đâu?
- [ ] Order line trỏ vào template hay variant? Vì sao?

**Purchase / Sales:**

- [ ] Báo giá và đơn hàng là 1 bảng hay 2 bảng? Phân biệt ra sao?
- [ ] Vì sao đếm số đơn phải COUNT(DISTINCT order_id) trên bảng line?
- [ ] Confirm 1 SO thì những bảng nào bị ghi? (kể ít nhất 4)

**Inventory:**

- [ ] Vì sao không UPDATE thẳng tồn kho mà phải ghi move?
- [ ] Location "ảo" supplier/customer dùng để làm gì?
- [ ] stock.move vs stock.quant — cái nào là nhật ký, cái nào là số dư?

**Accounting:**

- [ ] Luật sắt của account.move.line là gì?
- [ ] Viết bút toán bán hàng 220tr (VAT 10%): TK nào Nợ, TK nào Có, bao nhiêu?
- [ ] amount_residual dùng phân tích gì?
- [ ] Hóa đơn và thanh toán khác nhau chỗ nào?

**HR:**

- [ ] Vì sao lương nằm ở contract mà không nằm ở employee?
- [ ] Employee khác User chỗ nào?

**Tổng hợp:**

- [ ] Vẽ lại dòng chảy 8 bước từ lead đến thu tiền (không nhìn tài liệu)
- [ ] Kể 3 nơi trong Odoo áp dụng triết lý "ghi sự kiện, đừng ghi đè"
- [ ] Thứ tự build 7 module và vì sao phải theo thứ tự đó?

---

_Trả lời trôi chảy hết checklist = đủ nền tảng để bắt đầu build DDL + generate data._
