# DATA DICTIONARY — SUPERSTORE ERP

## Danh mục dữ liệu đầy đủ · Tên bảng · Tên cột · Kiểu dữ liệu · Mô tả

> **Cột Key:** PK = Primary Key · FK = Foreign Key · UQ = Unique · — = Thường

---

## Tầng 1 — Foundation

### `res_currency` &nbsp;·&nbsp; `res.currency`

> Tiền tệ. Phải có USD trước khi tạo bất kỳ giao dịch nào

| Cột      | Odoo Type | DB Type      | Nullable | Key | FK Trỏ về | Mô tả                                               |
| -------- | --------- | ------------ | -------- | --- | --------- | --------------------------------------------------- |
| `id`     | Integer   | `integer`    | NO       | PK  | —         | Định danh tự tăng                                   |
| `name`   | Char(3)   | `varchar(3)` | NO       | UQ  | —         | Mã ISO tiền tệ (USD, VND, EUR)                      |
| `symbol` | Char      | `varchar`    | YES      | —   | —         | Ký hiệu hiển thị ($, ₫, €)                          |
| `rate`   | Float (computed) | `—`     | —      | —   | —         | ⚠️ KHÔNG có cột `rate` thật trong DB — tỷ giá là time-series, lưu ở bảng riêng `res_currency_rate` (1 dòng/tiền tệ/ngày). `rate` ở ORM đọc rate mới nhất từ bảng đó |
| `active` | Boolean   | `boolean`    | NO       | —   | —         | false = ẩn khỏi UI nhưng giữ lịch sử                |

### `res_company` &nbsp;·&nbsp; `res.company`

> Pháp nhân. PHẢI đặt country=US và currency=USD trước mọi thao tác khác

| Cột           | Odoo Type | DB Type   | Nullable | Key | FK Trỏ về      | Mô tả                                            |
| ------------- | --------- | --------- | -------- | --- | -------------- | ------------------------------------------------ |
| `id`          | Integer   | `integer` | NO       | PK  | —              | Định danh tự tăng                                |
| `name`        | Char      | `varchar` | NO       | —   | —              | Tên công ty pháp nhân (Superstore Inc.)          |
| `currency_id` | Many2one  | `integer` | NO       | FK  | `res_currency` | ⭐ Tiền tệ mặc định — PHẢI là USD                |
| `partner_id`  | Many2one  | `integer` | YES      | FK  | `res_partner`  | Công ty cũng là 1 partner (địa chỉ, MST)         |
| `country_id`  | Many2one (related) | `—` | —      | —   | `res_country`  | ⚠️ KHÔNG có cột `country_id` thật trên `res_company` — đọc qua `partner_id.country_id` (company cũng là 1 partner). Cột thật trên bảng này chỉ có `account_fiscal_country_id` (quốc gia cho mục đích thuế/CoA) |
| `email`       | Char      | `varchar` | YES      | —   | —              | Email liên hệ doanh nghiệp                       |
| `phone`       | Char      | `varchar` | YES      | —   | —              | Số điện thoại công ty                            |
| `vat`         | Char (related) | `—`  | —        | —   | —              | ⚠️ KHÔNG có cột `vat` thật trên `res_company` — đọc qua `partner_id.vat`. Raw SQL phải JOIN `res_partner` qua `partner_id` |
| `logo`        | Binary (related) | `—` | —       | —   | —              | ⚠️ KHÔNG có cột `logo` thật — cột thật là `logo_web` (`bytea`); `logo` ở ORM là field liên quan/tương thích ngược |
| `security_lead` | Float   | `float8`  | NO       | —   | —              | ⭐ "Sales Safety Days" — số ngày kéo `scheduled_date` của phiếu kho SỚM HƠN ngày hứa giao khách (`date_order + customer_lead`), để kho có buffer chuẩn bị. Set = **2 ngày** (2026-07-22, cập nhật từ 1 ngày). Xem công thức đầy đủ ở `stock_picking.scheduled_date` |

### `res_partner` &nbsp;·&nbsp; `res.partner`

> ⭐ TRUNG TÂM: Khách hàng + NCC + Contact + Nhân viên chung 1 bảng. Phân biệt bằng customer_rank / supplier_rank

| Cột              | Odoo Type | DB Type     | Nullable | Key | FK Trỏ về           | Mô tả                                                                                                                                   |
| ---------------- | --------- | ----------- | -------- | --- | ------------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| `id`             | Integer   | `integer`   | NO       | PK  | —                   | Định danh tự tăng                                                                                                                       |
| `name`           | Char      | `varchar`   | NO       | —   | —                   | Tên tổ chức hoặc cá nhân                                                                                                                |
| `is_company`     | Boolean   | `boolean`   | NO       | —   | —                   | true = doanh nghiệp / false = cá nhân                                                                                                   |
| `customer_rank`  | Integer   | `integer`   | NO       | —   | —                   | ⭐ >0 = Khách hàng. Tự tăng khi SO được tạo                                                                                             |
| `supplier_rank`  | Integer   | `integer`   | NO       | —   | —                   | ⭐ >0 = Nhà cung cấp. Tự tăng khi PO được tạo                                                                                           |
| `parent_id`      | Many2one  | `integer`   | YES      | FK  | `res_partner`       | Công ty mẹ (contact trỏ về công ty — self-reference)                                                                                    |
| `commercial_partner_id` | Many2one | `integer` | YES   | FK  | `res_partner`       | Đối tác thương mại gốc; dùng gom contact/địa chỉ con khi tính doanh thu, CLV và retention                                                   |
| `company_id`     | Many2one  | `integer`   | YES      | FK  | `res_company`       | Pháp nhân sở hữu bản ghi này                                                                                                            |
| `email`          | Char      | `varchar`   | YES      | —   | —                   | Email liên hệ chính                                                                                                                     |
| `phone`          | Char      | `varchar`   | YES      | —   | —                   | Số điện thoại — 3% khách hàng bị NULL (imperfection có chủ đích, `missing_phone`)                                                       |
| `mobile`         | Char      | `varchar`   | YES      | —   | —                   | Số di động                                                                                                                              |
| `street`         | Char      | `varchar`   | YES      | —   | —                   | Địa chỉ dòng 1                                                                                                                          |
| `street2`        | Char      | `varchar`   | YES      | —   | —                   | Địa chỉ dòng 2 (tòa nhà, phòng...)                                                                                                      |
| `city`           | Char      | `varchar`   | YES      | —   | —                   | Thành phố                                                                                                                               |
| `state_id`       | Many2one  | `integer`   | YES      | FK  | `res_country_state` | Bang (CA, NY, TX...)                                                                                                                    |
| `zip`            | Char      | `varchar`   | YES      | —   | —                   | Mã bưu điện — 2% bị NULL (imperfection có chủ đích)                                                                                     |
| `country_id`     | Many2one  | `integer`   | YES      | FK  | `res_country`       | Quốc gia (US cho toàn bộ Superstore)                                                                                                    |
| `vat`            | Char      | `varchar`   | YES      | —   | —                   | Mã số thuế / EIN của đối tác                                                                                                            |
| `ref`            | Char      | `varchar`   | YES      | —   | —                   | External ID — dùng lưu rfm:champion, rfm:loyal...                                                                                       |
| `comment`        | Text      | `text`      | YES      | —   | —                   | Ghi chú — lưu Segment: Consumer/Corporate/Home Office                                                                                   |
| `autopost_bills` | Selection | `varchar`   | NO       | —   | —                   | always\|ask\|never — tự động duyệt bill của NCC này. Mặc định `'ask'` — BẮT BUỘC set khi insert thẳng SQL vì không có default ở tầng DB |
| `active`         | Boolean   | `boolean`   | NO       | —   | —                   | false = đã archive, ẩn UI nhưng giữ lịch sử giao dịch                                                                                   |
| `create_date`    | Datetime  | `timestamp` | YES      | —   | —                   | Ngày tạo (Odoo tự điền)                                                                                                                 |
| `write_date`     | Datetime  | `timestamp` | YES      | —   | —                   | ⭐ Ngày sửa cuối — nguồn SCD2 dim_customer, CDC trigger                                                                                 |
| `create_uid`     | Many2one  | `integer`   | YES      | FK  | `res_users`         | User tạo bản ghi (audit)                                                                                                                |
| `write_uid`      | Many2one  | `integer`   | YES      | FK  | `res_users`         | User sửa lần cuối (audit)                                                                                                               |

### `res_users` &nbsp;·&nbsp; `res.users`

> Tài khoản đăng nhập. Mọi chứng từ ghi create_uid/write_uid để audit trail

| Cột          | Odoo Type | DB Type   | Nullable | Key | FK Trỏ về     | Mô tả                                  |
| ------------ | --------- | --------- | -------- | --- | ------------- | -------------------------------------- |
| `id`         | Integer   | `integer` | NO       | PK  | —             | Định danh tự tăng                      |
| `name`       | Char (delegated) | `—` | —      | —   | —             | ⚠️ KHÔNG có cột `name` thật trên `res_users` — `res.users` delegate field này cho `res.partner` qua `partner_id` (Odoo `_inherits`). Raw SQL phải JOIN `res_partner` |
| `login`      | Char      | `varchar` | NO       | UQ  | —             | Username (admin, sales_rep_1...)       |
| `password`   | Char      | `varchar` | YES      | —   | —             | Bcrypt hash — không đọc được trực tiếp |
| `partner_id` | Many2one  | `integer` | NO       | FK  | `res_partner` | User cũng là partner — có tên, email   |
| `company_id` | Many2one  | `integer` | YES      | FK  | `res_company` | Pháp nhân mặc định khi đăng nhập       |
| `active`     | Boolean   | `boolean` | NO       | —   | —             | false = tài khoản bị khóa              |

---

## Tầng 2 — Product

### `uom_uom` &nbsp;·&nbsp; `uom.uom`

> Đơn vị tính và hệ số quy đổi. Mua thùng (24 cái) bán từng cái — tự quy đổi

| Cột           | Odoo Type | DB Type   | Nullable | Key | FK Trỏ về      | Mô tả                                          |
| ------------- | --------- | --------- | -------- | --- | -------------- | ---------------------------------------------- |
| `id`          | Integer   | `integer` | NO       | PK  | —              | Định danh tự tăng                              |
| `name`        | Char      | `varchar` | NO       | —   | —              | Tên đơn vị (Piece, Box, kg, liter)             |
| `category_id` | Many2one  | `integer` | NO       | FK  | `uom_category` | Nhóm quy đổi — chỉ quy đổi trong cùng category |
| `factor`      | Float     | `float8`  | NO       | —   | —              | Hệ số: 1 Box = 24 Piece → factor = 24          |
| `rounding`    | Float     | `float8`  | NO       | —   | —              | Làm tròn số lượng (0.01 = 2 chữ số thập phân)  |
| `active`      | Boolean   | `boolean` | NO       | —   | —              | false = ẩn khỏi danh sách                      |

### `product_category` &nbsp;·&nbsp; `product.category`

> Phân loại sản phẩm dạng cây phân cấp. Ảnh hưởng tài khoản kế toán và báo cáo

| Cột             | Odoo Type | DB Type   | Nullable | Key | FK Trỏ về          | Mô tả                                                  |
| --------------- | --------- | --------- | -------- | --- | ------------------ | ------------------------------------------------------ |
| `id`            | Integer   | `integer` | NO       | PK  | —                  | Định danh tự tăng                                      |
| `name`          | Char      | `varchar` | NO       | —   | —                  | Tên nhóm (Furniture, Technology, Tables, Chairs...)    |
| `parent_id`     | Many2one  | `integer` | YES      | FK  | `product_category` | Nhóm cha — NULL = gốc (All). Cây: All>Furniture>Tables |
| `complete_name` | Char      | `varchar` | YES      | —   | —                  | Computed: đường dẫn đầy đủ All / Furniture / Tables    |

### `product_template` &nbsp;·&nbsp; `product.template`

> SP mức KHÁI NIỆM — tên, giá, nhóm. 1 template = N variants. Giá bán lưu ở đây, giá vốn lưu ở `product_product` (company-dependent)

| Cột                | Odoo Type        | DB Type     | Nullable | Key | FK Trỏ về          | Mô tả                                                                                                                                                                                                                           |
| ------------------ | ---------------- | ----------- | -------- | --- | ------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `id`               | Integer          | `integer`   | NO       | PK  | —                  | Định danh tự tăng                                                                                                                                                                                                               |
| `name`             | Char (translate) | `jsonb`     | NO       | —   | —                  | ⚠️ Trường dịch — lưu dạng `{"en_US": "Standard Desk"}`, KHÔNG phải text thường. So sánh/tìm kiếm bằng `name->>'en_US'` hoặc `name::text LIKE`                                                                                   |
| `list_price`       | Float            | `numeric`   | YES      | —   | —                  | ⭐ Giá bán niêm yết — áp dụng cho tất cả variants                                                                                                                                                                               |
| `categ_id`         | Many2one         | `integer`   | NO       | FK  | `product_category` | Nhóm SP — ảnh hưởng tài khoản kế toán valuation                                                                                                                                                                                 |
| `type`             | Selection        | `varchar`   | NO       | —   | —                  | ⚠️ Odoo 18 chỉ còn `consu` (hàng hóa) \|`service` (dịch vụ) — KHÔNG còn giá trị `product`. Việc theo dõi tồn kho được tách ra field `is_storable` riêng                                                                         |
| `is_storable`      | Boolean          | `boolean`   | YES      | —   | —                  | ⭐⭐ true = BẮT BUỘC để `stock.quant` được tạo/cập nhật khi giao dịch. Nếu để trống (NULL/false), mọi stock.move vẫn `state=done` bình thường nhưng KHÔNG có bản ghi tồn kho nào được sinh ra — lỗi âm thầm, không có exception |
| `service_tracking` | Selection        | `varchar`   | NO       | —   | —                  | Tạo gì khi bán dịch vụ (project/task) — mặc định `'no'`                                                                                                                                                                         |
| `tracking`         | Selection        | `varchar`   | NO       | —   | —                  | Theo dõi theo `none` \|`lot` \|`serial` — mặc định `'none'`                                                                                                                                                                     |
| `uom_id`           | Many2one         | `integer`   | NO       | FK  | `uom_uom`          | ⭐ Đơn vị bán hàng (Piece, Set...)                                                                                                                                                                                              |
| `uom_po_id`        | Many2one         | `integer`   | NO       | FK  | `uom_uom`          | Đơn vị mua hàng (có thể khác đơn vị bán)                                                                                                                                                                                        |
| `sale_ok`          | Boolean          | `boolean`   | YES      | —   | —                  | true = được phép bán, hiện trong SO dropdown                                                                                                                                                                                    |
| `purchase_ok`      | Boolean          | `boolean`   | YES      | —   | —                  | true = được phép mua, hiện trong PO dropdown                                                                                                                                                                                    |
| `active`           | Boolean          | `boolean`   | YES      | —   | —                  | false = ngừng kinh doanh                                                                                                                                                                                                        |
| `description_sale` | Text (translate) | `jsonb`     | YES      | —   | —                  | Mô tả hiển thị trên báo giá, hóa đơn khách                                                                                                                                                                                      |
| `sale_delay`       | Integer          | `int4`      | NO       | —   | —                  | ⭐ "Customer Lead Time" — số ngày chuẩn bị hàng mặc định, copy sang `sale_order_line.customer_lead` khi thêm dòng đơn (qua onchange UI, KHÔNG retroactive cho dòng đã có). Set = **3 ngày** đồng nhất mọi SP (2026-07-22) |
| `write_date`       | Datetime         | `timestamp` | YES      | —   | —                  | ⭐ Lần sửa giá cuối — nguồn SCD2 dim_product                                                                                                                                                                                    |

### `product_product` &nbsp;·&nbsp; `product.product`

> ⭐ SKU THẬT — mọi order_line / stock_move / bom_line trỏ vào đây, KHÔNG phải template

| Cột               | Odoo Type                 | DB Type   | Nullable | Key | FK Trỏ về          | Mô tả                                                                                                                                                                                                                                        |
| ----------------- | ------------------------- | --------- | -------- | --- | ------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `id`              | Integer                   | `integer` | NO       | PK  | —                  | Định danh tự tăng — đây là ID mà SO line dùng                                                                                                                                                                                                |
| `product_tmpl_id` | Many2one                  | `integer` | NO       | FK  | `product_template` | ⭐ Thuộc template nào                                                                                                                                                                                                                        |
| `standard_price`  | Float (company-dependent) | `jsonb`   | YES      | —   | —                  | ⭐⭐ Giá vốn — dùng tính COGS. Nằm ở `product.product`, KHÔNG phải template. Company-dependent: lưu jsonb khóa theo `company_id` (vd `{"1": 45.5}`) — KHÔNG set được qua INSERT trực tiếp, phải `write()` qua ORM/XML-RPC sau khi tạo record |
| `default_code`    | Char                      | `varchar` | YES      | —   | —                  | ⭐ Mã SKU nội bộ (SS-FUR-0001, SS-TEC-0042)                                                                                                                                                                                                  |
| `barcode`         | Char                      | `varchar` | YES      | UQ  | —                  | Mã vạch EAN-13 hoặc UPC                                                                                                                                                                                                                      |
| `active`          | Boolean                   | `boolean` | YES      | —   | —                  | false = SKU ngừng, lịch sử đơn hàng vẫn giữ                                                                                                                                                                                                  |

---

## Tầng 3 — Warehouse

### `stock_warehouse` &nbsp;·&nbsp; `stock.warehouse`

> Kho hàng — tạo qua XML-RPC, Odoo tự sinh ~15 records phụ (locations, routes, picking types)

| Cột               | Odoo Type | DB Type   | Nullable | Key | FK Trỏ về        | Mô tả                                                 |
| ----------------- | --------- | --------- | -------- | --- | ---------------- | ----------------------------------------------------- |
| `id`              | Integer   | `integer` | NO       | PK  | —                | Định danh tự tăng                                     |
| `name`            | Char      | `varchar` | NO       | —   | —                | Tên kho (Los Angeles - West, Newark - East...)        |
| `code`            | Char      | `varchar` | NO       | UQ  | —                | ⭐ Mã kho (WEST/EAST/CNTL/SOUT) — tiền tố số chứng từ |
| `company_id`      | Many2one  | `integer` | NO       | FK  | `res_company`    | Công ty sở hữu kho                                    |
| `partner_id`      | Many2one  | `integer` | YES      | FK  | `res_partner`    | Địa chỉ kho (dùng trên delivery slip)                 |
| `lot_stock_id`    | Many2one  | `integer` | YES      | FK  | `stock_location` | ⭐ Location Stock chính — nơi hàng thực sự nằm        |
| `reception_steps` | Selection | `varchar` | NO       | —   | —                | Quy trình nhận: one_step\|two_steps\|three_steps      |
| `delivery_steps`  | Selection | `varchar` | NO       | —   | —                | Quy trình xuất: ship_only\|pick_ship\|pick_pack_ship  |
| `active`          | Boolean   | `boolean` | NO       | —   | —                | false = kho ngừng hoạt động                           |

### `stock_location` &nbsp;·&nbsp; `stock.location`

> Vị trí kho — cả THẬT (kệ A1) và ẢO (Suppliers, Customers, Inventory). Mọi stock_move đi từ location → location

| Cột             | Odoo Type | DB Type   | Nullable | Key | FK Trỏ về        | Mô tả                                                    |
| --------------- | --------- | --------- | -------- | --- | ---------------- | -------------------------------------------------------- |
| `id`            | Integer   | `integer` | NO       | PK  | —                | Định danh tự tăng                                        |
| `name`          | Char      | `varchar` | NO       | —   | —                | Tên vị trí (Stock, Input, Shelf A1...)                   |
| `complete_name` | Char      | `varchar` | YES      | —   | —                | Computed: đường dẫn đầy đủ WH-WEST/Stock/Shelf A1        |
| `location_id`   | Many2one  | `integer` | YES      | FK  | `stock_location` | ⭐ Vị trí cha — cây phân cấp kho (self-reference)        |
| `usage`         | Selection | `varchar` | NO       | —   | —                | ⭐ internal\|supplier(ảo)\|customer(ảo)\|inventory\|view |
| `company_id`    | Many2one  | `integer` | YES      | FK  | `res_company`    | NULL = location dùng chung (Suppliers ảo, Customers ảo)  |
| `barcode`       | Char      | `varchar` | YES      | —   | —                | Barcode vị trí kệ — dùng khi scan                        |
| `active`        | Boolean   | `boolean` | NO       | —   | —                | false = vị trí không còn dùng                            |

### `delivery_carrier` &nbsp;·&nbsp; `delivery.carrier`

> ⚠️ Module `delivery` + `stock_delivery` mới cài (2026-07-22) — bảng chỉ có **1 dòng mặc định** ("Standard delivery", base data của module, KHÔNG phải carrier nghiệp vụ tự tạo). Chưa có carrier nào được gán vào `sale_order.carrier_id`/`stock_picking.carrier_id` thật. Không có field lưu "số ngày vận chuyển" trên bảng này — thời gian vận chuyển thật nằm ở `stock_rule.delay` (rule `<WH>: Stock → Customers`), xem công thức đầy đủ ở `stock_picking.scheduled_date`

| Cột             | Odoo Type         | DB Type   | Nullable | Key | FK Trỏ về         | Mô tả                                                                 |
| ---------------- | ----------------- | --------- | -------- | --- | ------------------ | ---------------------------------------------------------------------- |
| `id`             | Integer            | `integer` | NO       | PK  | —                  | Định danh tự tăng                                                     |
| `name`           | Char (translate)   | `jsonb`   | NO       | —   | —                  | Tên phương thức giao hàng — hiện chỉ có `{"en_US": "Standard delivery"}` |
| `delivery_type`  | Selection          | `varchar` | NO       | —   | —                  | `fixed`\|`base_on_rule`\|... — dòng mặc định = `fixed`                |
| `product_id`     | Many2one           | `integer` | NO       | FK  | `product_product`  | ⭐ Mỗi carrier gắn với 1 SP dịch vụ để lên hóa đơn cước phí (`_inherits`) |
| `company_id`     | Many2one           | `integer` | YES      | FK  | `res_company`      | Công ty                                                               |
| `active`         | Boolean            | `boolean` | YES      | —   | —                  | false = ẩn khỏi lựa chọn                                              |

> Ngoài ra module còn tạo `delivery_price_rule` (quy tắc tính cước) và `delivery_zip_prefix` (quy tắc theo mã vùng) — cả 2 bảng hiện **0 dòng**, chưa cấu hình.

### `stock_rule` &nbsp;·&nbsp; `stock.rule`

> Quy tắc procurement — mỗi cặp location nguồn/đích (vd "Stock → Customers") có 1 rule. Odoo tự sinh khi tạo warehouse. `delay` là input trực tiếp cho công thức `scheduled_date` (xem `stock_picking.scheduled_date`)

| Cột             | Odoo Type | DB Type   | Nullable | Key | FK Trỏ về         | Mô tả                                                                                                                        |
| ---------------- | --------- | --------- | -------- | --- | ------------------ | ------------------------------------------------------------------------------------------------------------------------------ |
| `id`             | Integer   | `integer` | NO       | PK  | —                  | Định danh tự tăng                                                                                                            |
| `name`           | Char (translate) | `jsonb` | NO     | —   | —                  | Vd `{"en_US": "WEST: Stock → Customers"}`                                                                                    |
| `action`         | Selection | `varchar` | NO       | —   | —                  | `pull`\|`push`\|`pull_push` — `pull` cho rule xuất hàng                                                                      |
| `warehouse_id`   | Many2one  | `integer` | YES      | FK  | `stock_warehouse`  | Thuộc kho nào                                                                                                                |
| `delay`          | Integer   | `int4`    | NO       | —   | —                  | ⭐⭐ "Lead Time" — số ngày vận chuyển kho→khách. Set (2026-07-22): **WEST=2, EAST=2** (gần) · **CNTL=3, SOUT=3** (xa) trên rule `<WH>: Stock → Customers` (non-MTO). Mặc định Odoo = 0 cho MỌI rule khác |

---

## Tầng 4 — Manufacturing

### `mrp_workcenter` &nbsp;·&nbsp; `mrp.workcenter`

> Trạm sản xuất vật lý. WC-CUT (cắt), WC-ASM (lắp ráp), WC-QC (kiểm tra chất lượng)

| Cột                | Odoo Type | DB Type   | Nullable | Key | FK Trỏ về           | Mô tả                                                                                                                                               |
| ------------------ | --------- | --------- | -------- | --- | ------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------- |
| `id`               | Integer   | `integer` | NO       | PK  | —                   | Định danh tự tăng                                                                                                                                   |
| `resource_id`      | Many2one  | `integer` | NO       | FK  | `resource_resource` | ⭐⭐ BẮT BUỘC — mrp.workcenter kế thừa resource.mixin, phải tạo `resource_resource` (resource_type='material') TRƯỚC rồi mới insert được workcenter |
| `name`             | Char      | `varchar` | YES      | —   | —                   | Tên trạm (Cutting Station, Assembly Line, Quality Control)                                                                                          |
| `code`             | Char      | `varchar` | YES      | —   | —                   | Mã ngắn (WC-CUT, WC-ASM, WC-QC)                                                                                                                     |
| `company_id`       | Many2one  | `integer` | YES      | FK  | `res_company`       | Công ty                                                                                                                                             |
| `default_capacity` | Float     | `float8`  | YES      | —   | —                   | ⚠️ Tên field thật là `default_capacity`, KHÔNG phải `capacity`. Số worker song song: WC-CUT=2, WC-ASM=3, WC-QC=1                                    |
| `time_efficiency`  | Float     | `float8`  | YES      | —   | —                   | Hiệu suất % (100=lý thuyết, thực tế 85-95%)                                                                                                         |
| `active`           | Boolean   | `boolean` | YES      | —   | —                   | false = trạm ngừng hoạt động                                                                                                                        |

### `mrp_bom` &nbsp;·&nbsp; `mrp.bom`

> Bill of Materials — công thức sản xuất. Thiếu BOM = không tạo được Manufacturing Order

| Cột               | Odoo Type | DB Type   | Nullable | Key | FK Trỏ về          | Mô tả                                            |
| ----------------- | --------- | --------- | -------- | --- | ------------------ | ------------------------------------------------ |
| `id`              | Integer   | `integer` | NO       | PK  | —                  | Định danh tự tăng                                |
| `product_tmpl_id` | Many2one  | `integer` | NO       | FK  | `product_template` | ⭐ SP đang định nghĩa công thức sản xuất         |
| `product_id`      | Many2one  | `integer` | YES      | FK  | `product_product`  | Variant cụ thể — NULL = áp dụng tất cả variants  |
| `product_qty`     | Float     | `float8`  | NO       | —   | —                  | Số lượng thành phẩm tạo ra (thường = 1.0)        |
| `product_uom_id`  | Many2one  | `integer` | NO       | FK  | `uom_uom`          | Đơn vị tính thành phẩm                           |
| `type`            | Selection | `varchar` | NO       | —   | —                  | normal=sản xuất tạo MO\|phantom=kit không tạo MO |
| `company_id`      | Many2one  | `integer` | NO       | FK  | `res_company`      | Công ty                                          |
| `code`            | Char      | `varchar` | YES      | —   | —                  | Mã BOM nội bộ (tự đặt)                           |

### `mrp_bom_line` &nbsp;·&nbsp; `mrp.bom.line`

> Từng nguyên liệu trong BOM. Standard Desk: tabletop + frame + hardware + edge banding + packaging

| Cột              | Odoo Type | DB Type   | Nullable | Key | FK Trỏ về         | Mô tả                                             |
| ---------------- | --------- | --------- | -------- | --- | ----------------- | ------------------------------------------------- |
| `id`             | Integer   | `integer` | NO       | PK  | —                 | Định danh tự tăng                                 |
| `bom_id`         | Many2one  | `integer` | NO       | FK  | `mrp_bom`         | ⭐ Thuộc BOM nào                                  |
| `product_id`     | Many2one  | `integer` | NO       | FK  | `product_product` | ⭐ Nguyên liệu cần dùng (raw material SKU)        |
| `product_qty`    | Float     | `float8`  | NO       | —   | —                 | Số lượng cần (1.0 bộ khung, 3.5 mét edge banding) |
| `product_uom_id` | Many2one  | `integer` | NO       | FK  | `uom_uom`         | Đơn vị tính nguyên liệu                           |
| `sequence`       | Integer   | `integer` | NO       | —   | —                 | Thứ tự hiển thị trong BOM                         |

### `mrp_routing_workcenter` &nbsp;·&nbsp; `mrp.routing.workcenter`

> Operation trong BOM — OP-01 Cutting 45min tại WC-CUT → OP-02 Assembly 120min → OP-03 QC 30min

| Cột                 | Odoo Type | DB Type   | Nullable | Key | FK Trỏ về        | Mô tả                                                                                                                                                      |
| ------------------- | --------- | --------- | -------- | --- | ---------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `id`                | Integer   | `integer` | NO       | PK  | —                | Định danh tự tăng                                                                                                                                          |
| `name`              | Char      | `varchar` | NO       | —   | —                | Tên công đoạn (OP-01: Material Prep, OP-02: Assembly)                                                                                                      |
| `bom_id`            | Many2one  | `integer` | **NO**   | FK  | `mrp_bom`        | ⚠️ BẮT BUỘC trong Odoo 18 (khác doc cũ ghi YES) — không có `mrp.routing` đứng riêng nữa, mọi operation phải gắn trực tiếp với 1 BOM ngay khi tạo           |
| `workcenter_id`     | Many2one  | `integer` | NO       | FK  | `mrp_workcenter` | ⭐ Thực hiện tại work center nào                                                                                                                           |
| `time_mode`         | Selection | `varchar` | YES      | —   | —                | `manual` = nhập tay thời gian (dùng `time_cycle_manual`) \|khác = tự tính từ lịch sử work order                                                            |
| `time_cycle_manual` | Float     | `float8`  | YES      | —   | —                | ⚠️ Tên field thật là `time_cycle_manual`, KHÔNG phải `duration_expected`. Thời gian chuẩn (phút): 45 / 120 / 30 — chỉ có hiệu lực khi `time_mode='manual'` |
| `sequence`          | Integer   | `integer` | YES      | —   | —                | Thứ tự công đoạn: 1=Cutting, 2=Assembly, 3=QC                                                                                                              |

---

## Tầng 5 — Accounting

### `account_account` &nbsp;·&nbsp; `account.account`

> Chart of Accounts — ngăn kéo phân loại tiền. Không có COA = không tạo được invoice hay payment

| Cột            | Odoo Type                | DB Type   | Nullable | Key | FK Trỏ về      | Mô tả                                                                                                                                                                                                                  |
| -------------- | ------------------------ | --------- | -------- | --- | -------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `id`           | Integer                  | `integer` | NO       | PK  | —              | Định danh tự tăng                                                                                                                                                                                                      |
| `code`         | Char (computed)          | `—`       | —        | —   | —              | ⚠️⚠️ KHÔNG có cột `code` thật trong DB. `code` là computed field đọc từ `code_store` (jsonb, company-dependent: `{"1": "121000"}`). Raw SQL phải query `code_store->>'<company_id>'`, không dùng `WHERE code=...` được |
| `code_store`   | Char (company-dependent) | `jsonb`   | YES      | —   | —              | Giá trị thật của mã TK, khóa theo company_id. Mã CoA US hiện tại (6 chữ số): `101401`=Bank \|`101501`=Cash \|`121000`=AR \|`211000`=AP \|`400000`=Revenue \|`500000`=COGS                                              |
| `name`         | Char (translate)         | `jsonb`   | NO       | —   | —              | ⚠️ Trường dịch — `{"en_US": "Cash"}`, không phải text thường                                                                                                                                                           |
| `account_type` | Selection                | `varchar` | NO       | —   | —              | ⭐ asset*\* \|liability*_ \|equity \|income \|expense\__ (nhiều subtype hơn bản mô tả gốc, vd `asset_receivable`, `liability_payable`)                                                                                 |
| `company_ids`  | Many2many (computed)     | `—`       | —        | —   | `res_company`  | ⚠️ KHÔNG có cột `company_id` (Many2one) — Odoo 18 đổi COA sang dùng chung nhiều công ty qua bảng quan hệ `account_account_res_company_rel` (Many2many), không còn 1-account-1-company như bản cũ                       |
| `currency_id`  | Many2one                 | `integer` | YES      | FK  | `res_currency` | NULL = tiền tệ công ty. Có giá trị = TK ngoại tệ                                                                                                                                                                       |
| `reconcile`    | Boolean                  | `boolean` | YES      | —   | —              | true = TK công nợ AR/AP — cần reconcile với payment                                                                                                                                                                    |
| `deprecated`   | Boolean                  | `boolean` | YES      | —   | —              | true = ngừng dùng (không xóa khi đã có bút toán)                                                                                                                                                                       |

### `account_journal` &nbsp;·&nbsp; `account.journal`

> Sổ nhật ký phân loại bút toán theo nghiệp vụ. Mỗi loại có sequence số riêng (INV/BILL/BNK)

| Cột                  | Odoo Type | DB Type   | Nullable | Key | FK Trỏ về         | Mô tả                                                |
| -------------------- | --------- | --------- | -------- | --- | ----------------- | ---------------------------------------------------- |
| `id`                 | Integer   | `integer` | NO       | PK  | —                 | Định danh tự tăng                                    |
| `name`               | Char      | `varchar` | NO       | —   | —                 | Tên sổ (Customer Invoices, Vendor Bills, Bank, Cash) |
| `type`               | Selection | `varchar` | NO       | —   | —                 | ⭐ sale\|purchase\|bank\|cash\|general               |
| `code`               | Char      | `varchar` | NO       | UQ  | —                 | ⭐ Tiền tố số chứng từ: INV / BILL / BNK / CSH       |
| `company_id`         | Many2one  | `integer` | NO       | FK  | `res_company`     | Công ty                                              |
| `currency_id`        | Many2one  | `integer` | YES      | FK  | `res_currency`    | NULL = tiền tệ công ty                               |
| `default_account_id` | Many2one  | `integer` | YES      | FK  | `account_account` | TK mặc định của sổ (Bank → TK ngân hàng 1010)        |

---

## Tầng 6 — HR

### `resource_resource` &nbsp;·&nbsp; `resource.resource`

> ⭐ Bảng nền tảng dùng chung bởi `hr.employee` VÀ `mrp.workcenter` (cả 2 kế thừa `resource.mixin`). Phải tạo record ở đây trước, rồi mới insert được employee/workcenter với `resource_id` trỏ về

| Cột               | Odoo Type | DB Type   | Nullable | Key | FK Trỏ về     | Mô tả                                                                       |
| ----------------- | --------- | --------- | -------- | --- | ------------- | --------------------------------------------------------------------------- |
| `id`              | Integer   | `integer` | NO       | PK  | —             | Định danh tự tăng                                                           |
| `name`            | Char      | `varchar` | NO       | —   | —             | Tên — trùng tên nhân viên hoặc tên trạm sản xuất                            |
| `resource_type`   | Selection | `varchar` | NO       | —   | —             | ⭐ `user` = con người (nhân viên) \|`material` = máy móc/trạm (work center) |
| `time_efficiency` | Float     | `float8`  | NO       | —   | —             | Hệ số hiệu suất % — mặc định 100                                            |
| `tz`              | Char      | `varchar` | NO       | —   | —             | Múi giờ làm việc — mặc định `'UTC'`                                         |
| `company_id`      | Many2one  | `integer` | YES      | FK  | `res_company` | Công ty                                                                     |
| `active`          | Boolean   | `boolean` | YES      | —   | —             | false = ngừng dùng                                                          |

### `hr_department` &nbsp;·&nbsp; `hr.department`

> Cây phòng ban tổ chức. Phải tạo TRƯỚC khi tạo hr_employee

| Cột          | Odoo Type        | DB Type   | Nullable | Key | FK Trỏ về       | Mô tả                                                                                                                                                |
| ------------ | ---------------- | --------- | -------- | --- | --------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| `id`         | Integer          | `integer` | NO       | PK  | —               | Định danh tự tăng                                                                                                                                    |
| `name`       | Char (translate) | `jsonb`   | NO       | —   | —               | ⚠️ Trường dịch — `{"en_US": "Sales & CRM"}`, không phải text thường                                                                                  |
| `parent_id`  | Many2one         | `integer` | YES      | FK  | `hr_department` | Phòng cha — NULL = cấp cao nhất (self-reference)                                                                                                     |
| `manager_id` | Many2one         | `integer` | YES      | FK  | `hr_employee`   | Trưởng phòng — generator hiện KHÔNG set field này (chỉ set `job_id`/`job_title` = "Manager" ở employee, không link ngược `hr_department.manager_id`) |
| `company_id` | Many2one         | `integer` | YES      | FK  | `res_company`   | Công ty                                                                                                                                              |
| `active`     | Boolean          | `boolean` | YES      | —   | —               | false = phòng ban giải tán                                                                                                                           |

### `hr_job` &nbsp;·&nbsp; `hr.job`

> Chức danh/vị trí công việc. 1 chức danh/phòng ban (vd "Sales Manager" trong Sales & CRM), nhiều nhân viên có thể giữ cùng chức danh

| Cột             | Odoo Type        | DB Type   | Nullable | Key | FK Trỏ về       | Mô tả                                                                                                                                                                                                         |
| --------------- | ---------------- | --------- | -------- | --- | --------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `id`            | Integer          | `integer` | NO       | PK  | —               | Định danh tự tăng                                                                                                                                                                                             |
| `name`          | Char (translate) | `jsonb`   | NO       | —   | —               | ⚠️ Trường dịch — `{"en_US": "Sales Manager"}`. Mỗi phòng ban có 1 chức danh "lead" (Manager/Supervisor/C-level) + 2-3 chức danh "staff" (vd Sales: Sales Representative, Account Executive, Inside Sales Rep) |
| `department_id` | Many2one         | `integer` | YES      | FK  | `hr_department` | Thuộc phòng ban nào                                                                                                                                                                                           |
| `company_id`    | Many2one         | `integer` | YES      | FK  | `res_company`   | Công ty                                                                                                                                                                                                       |

### `hr_employee` &nbsp;·&nbsp; `hr.employee`

> Hồ sơ nhân viên. Khác res.users — nhân viên không nhất thiết có account login Odoo

| Cột                       | Odoo Type | DB Type   | Nullable | Key | FK Trỏ về           | Mô tả                                                                                                                                      |
| ------------------------- | --------- | --------- | -------- | --- | ------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| `id`                      | Integer   | `integer` | NO       | PK  | —                   | Định danh tự tăng                                                                                                                          |
| `resource_id`             | Many2one  | `integer` | **NO**   | FK  | `resource_resource` | ⭐⭐ BẮT BUỘC — hr.employee kế thừa resource.mixin, phải tạo `resource_resource` (resource_type='user') TRƯỚC rồi mới insert được employee |
| `name`                    | Char      | `varchar` | YES      | —   | —                   | Họ và tên đầy đủ                                                                                                                           |
| `department_id`           | Many2one  | `integer` | YES      | FK  | `hr_department`     | ⭐ Phòng ban                                                                                                                               |
| `job_id`                  | Many2one  | `integer` | YES      | FK  | `hr_job`            | ⭐ Chức danh (FK có cấu trúc) — nhân viên đầu tiên/phòng ban nhận chức danh "lead", còn lại random từ danh sách "staff"                    |
| `job_title`               | Char      | `varchar` | YES      | —   | —                   | Chức danh dạng text tự do — generator set trùng giá trị với `job_id.name` để hiển thị nhanh không cần join                                 |
| `user_id`                 | Many2one  | `integer` | YES      | FK  | `res_users`         | Tài khoản login Odoo — NULL OK (công nhân kho)                                                                                             |
| `address_id`              | Many2one  | `integer` | YES      | FK  | `res_partner`       | Địa chỉ liên hệ nhân viên                                                                                                                  |
| `company_id`              | Many2one  | `integer` | NO       | FK  | `res_company`       | Công ty                                                                                                                                    |
| `work_email`              | Char      | `varchar` | YES      | —   | —                   | Email công việc                                                                                                                            |
| `employee_type`           | Selection | `varchar` | NO       | —   | —                   | employee\|worker\|student\|trainee\|contractor\|freelance — mặc định `'employee'`                                                          |
| `marital`                 | Selection | `varchar` | NO       | —   | —                   | Tình trạng hôn nhân — mặc định `'single'`                                                                                                  |
| `distance_home_work_unit` | Selection | `varchar` | NO       | —   | —                   | Đơn vị khoảng cách nhà-cơ quan (kilometers\|miles) — mặc định `'kilometers'`                                                               |
| `active`                  | Boolean   | `boolean` | YES      | —   | —                   | false = đã nghỉ việc (lịch sử transaction vẫn giữ)                                                                                         |

### `hr_contract` &nbsp;·&nbsp; `hr.contract`

> ⭐ SCD2 tự nhiên nhất hệ thống. Tăng lương = đóng contract cũ + tạo contract mới. Lịch sử lương đầy đủ

| Cột           | Odoo Type | DB Type   | Nullable | Key | FK Trỏ về     | Mô tả                                                               |
| ------------- | --------- | --------- | -------- | --- | ------------- | ------------------------------------------------------------------- |
| `id`          | Integer   | `integer` | NO       | PK  | —             | Định danh tự tăng                                                   |
| `name`        | Char      | `varchar` | NO       | —   | —             | Tên HĐ (Contract-15-1, Contract-15-2 sau tăng lương)                |
| `employee_id` | Many2one  | `integer` | NO       | FK  | `hr_employee` | ⭐ Của nhân viên nào                                                |
| `wage`        | Monetary  | `float8`  | NO       | —   | —             | ⭐ Lương cơ bản USD/năm — thay đổi = KHÔNG update, tạo contract mới |
| `date_start`  | Date      | `date`    | NO       | —   | —             | ⭐ Hiệu lực từ ngày (→ dbt_valid_from trong SCD2)                   |
| `date_end`    | Date      | `date`    | YES      | —   | —             | ⭐ Hết hiệu lực. NULL = đang active (→ dbt_valid_to)                |
| `state`       | Selection | `varchar` | NO       | —   | —             | State machine: draft → open (active) → close                        |
| `company_id`  | Many2one  | `integer` | NO       | FK  | `res_company` | Công ty                                                             |

---

## Tầng 7 — Marketing (UTM)

### `utm_source` &nbsp;·&nbsp; `utm.source`

> Nguồn traffic (google, facebook, direct...). Cùng với utm_medium + utm_campaign tạo bộ 3 UTM attribution chuẩn

| Cột    | Odoo Type | DB Type   | Nullable | Key | FK Trỏ về | Mô tả                                                                     |
| ------ | --------- | --------- | -------- | --- | --------- | ------------------------------------------------------------------------- |
| `id`   | Integer   | `integer` | NO       | PK  | —         | Định danh tự tăng                                                         |
| `name` | Char      | `varchar` | NO       | —   | —         | Tên nguồn (google, facebook, instagram, email, direct, referral, organic) |

### `utm_medium` &nbsp;·&nbsp; `utm.medium`

> Kênh truyền tải (cpc, email, social, organic...)

| Cột      | Odoo Type | DB Type   | Nullable | Key | FK Trỏ về | Mô tả                                                           |
| -------- | --------- | --------- | -------- | --- | --------- | --------------------------------------------------------------- |
| `id`     | Integer   | `integer` | NO       | PK  | —         | Định danh tự tăng                                               |
| `name`   | Char      | `varchar` | NO       | —   | —         | Tên kênh (cpc, email, social, organic, referral, none, display) |
| `active` | Boolean   | `boolean` | YES      | —   | —         | false = ngừng dùng                                              |

### `utm_campaign` &nbsp;·&nbsp; `utm.campaign`

> Chiến dịch marketing. `sale_order.campaign_id` / `account_move.campaign_id` trỏ vào đây để attribution doanh thu

| Cột          | Odoo Type        | DB Type   | Nullable | Key | FK Trỏ về     | Mô tả                                                                                                                           |
| ------------ | ---------------- | --------- | -------- | --- | ------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| `id`         | Integer          | `integer` | NO       | PK  | —             | Định danh tự tăng                                                                                                               |
| `name`       | Char             | `varchar` | NO       | UQ  | —             | ⚠️ "Campaign Identifier" — mã kỹ thuật, KHÔNG dịch, unique. KHÔNG phải tên hiển thị chính (xem `title`)                         |
| `title`      | Char (translate) | `jsonb`   | NO       | —   | —             | ⭐⭐ "Campaign Name" — tên hiển thị thật, trường dịch `{"en_US": "..."}`. Đây là field `_rec_name` của model, không phải `name` |
| `user_id`    | Many2one         | `integer` | **NO**   | FK  | `res_users`   | ⚠️ BẮT BUỘC — người phụ trách chiến dịch, không có default ở tầng DB khi insert thẳng SQL                                       |
| `stage_id`   | Many2one         | `integer` | **NO**   | FK  | `utm_stage`   | ⚠️ BẮT BUỘC — cần lấy 1 `utm.stage` có sẵn (`SELECT id FROM utm_stage LIMIT 1`) trước khi insert                                |
| `company_id` | Many2one         | `integer` | YES      | FK  | `res_company` | Công ty                                                                                                                         |
| `active`     | Boolean          | `boolean` | YES      | —   | —             | false = chiến dịch đã kết thúc/ẩn                                                                                               |

### `crm_stage` &nbsp;·&nbsp; `crm.stage`

> Các giai đoạn phễu CRM — dùng cho `crm_lead.stage_id`. Base data Odoo (không do generator sinh): New → Qualified → Proposition → Won

| Cột       | Odoo Type        | DB Type   | Nullable | Key | FK Trỏ về   | Mô tả                                                              |
| --------- | ---------------- | --------- | -------- | --- | ----------- | -------------------------------------------------------------------- |
| `id`      | Integer          | `integer` | NO       | PK  | —           | Định danh tự tăng — 1=New, 2=Qualified, 3=Proposition, 4=Won (base data thật) |
| `name`    | Char (translate) | `jsonb`   | NO       | —   | —           | Tên giai đoạn                                                        |
| `sequence`| Integer          | `integer` | YES      | —   | —           | ⚠️ KHÔNG trùng với `id` ở giai đoạn Won — id=4 nhưng sequence=70 (Won luôn xếp cuối, cách xa các stage thường) |
| `is_won`  | Boolean          | `boolean` | YES      | —   | —           | ⭐ true = giai đoạn coi là "chốt thành công" — dùng để lọc Won lead thay vì so tên chuỗi |
| `team_id` | Many2one         | `integer` | YES      | FK  | `crm_team`  | NULL = dùng chung mọi team                                          |

### `crm_lost_reason` &nbsp;·&nbsp; `crm.lost.reason`

> Danh mục lý do mất lead — dùng cho `crm_lead.lost_reason_id`. Base data Odoo: "Too expensive", "We don't have people/skills", "Not enough stock"

| Cột      | Odoo Type        | DB Type   | Nullable | Key | FK Trỏ về | Mô tả              |
| -------- | ---------------- | --------- | -------- | --- | --------- | -------------------- |
| `id`     | Integer          | `integer` | NO       | PK  | —         | Định danh tự tăng    |
| `name`   | Char (translate) | `jsonb`   | NO       | —   | —         | Lý do mất lead        |
| `active` | Boolean          | `boolean` | YES      | —   | —         | false = lý do đã ẩn   |

---

## Transaction — Sales

### `crm_lead` &nbsp;·&nbsp; `crm.lead`

> ⭐ Phễu Lead→Opportunity→SO. Generator v3 (Phase 2b) sinh **Won opportunity** (1:1 với mọi `sale_order`) và prospect bị mất để đạt conversion ~25%. Prospect mất ở New giữ `type='lead'`; prospect đã qua Qualified/Proposition mang `type='opportunity'`. Phase 2b cũng repair link/ngày chuyển đổi do bản generator cũ bỏ trống.

| Cột                | Odoo Type | DB Type     | Nullable | Key | FK Trỏ về         | Mô tả                                                                                                                                                              |
| ------------------- | --------- | ----------- | -------- | --- | ------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `id`                | Integer   | `integer`   | NO       | PK  | —                  | Định danh tự tăng                                                                                                                                                       |
| `name`              | Char      | `varchar`   | NO       | —   | —                  | ⭐ Tiêu đề lead — Won lead generator đặt `"Opportunity — {sale_order.name}"`, dùng để nối ngược về SO (xem cột `type`)                                                  |
| `type`              | Selection | `varchar`   | NO       | —   | —                  | `lead` \| `opportunity` — Won luôn là opportunity; lost sau Qualified/Proposition cũng là opportunity                                                      |
| `partner_id`        | Many2one  | `integer`   | YES      | FK  | `res_partner`      | Won lead: = `sale_order.partner_id` tương ứng. Lost lead: **NULL** — chưa từng thành khách hàng, dùng `contact_name`/`partner_name`/`email_from` (text tự do) thay thế |
| `team_id`           | Many2one  | `integer`   | YES      | FK  | `crm_team`         | Sales team phụ trách; dùng phân tích ownership và SLA                                                                                                           |
| `contact_name`      | Char      | `varchar`   | YES      | —   | —                  | Tên người liên hệ (Lost lead: Faker name, không link `res_partner`)                                                                                                    |
| `partner_name`      | Char      | `varchar`   | YES      | —   | —                  | Tên công ty prospect (Lost lead: Faker company)                                                                                                                        |
| `email_from`        | Char      | `varchar`   | YES      | —   | —                  | Email liên hệ                                                                                                                                                          |
| `stage_id`          | Many2one  | `integer`   | YES      | FK  | `crm_stage`        | ⭐ Won lead = stage `is_won=true`. Lost lead = New(50%)/Qualified(30%)/Proposition(20%) — trọng số mô phỏng hình phễu thật (rớt sớm nhiều hơn rớt muộn)                |
| `probability`       | Float     | `float8`    | YES      | —   | —                  | Won = 100.0, Lost = 0.0                                                                                                                                                |
| `active`            | Boolean   | `boolean`   | YES      | —   | —                  | ⭐ Lost lead = **false** (Odoo dùng archive để biểu thị "mất", KHÔNG có stage "Lost" riêng) — Won lead = true                                                          |
| `expected_revenue`  | Monetary  | `numeric`   | YES      | —   | —                  | Won lead = `sale_order.amount_total` tương ứng (khớp 100%, đã verify)                                                                                                  |
| `lost_reason_id`    | Many2one  | `integer`   | YES      | FK  | `crm_lost_reason`  | Chỉ Lost lead có                                                                                                                                                        |
| `campaign_id`       | Many2one  | `integer`   | YES      | FK  | `utm_campaign`      | Won lead: kế thừa từ `sale_order.campaign_id` (khớp ~45-49%). Lost lead: random 70% có                                                                                |
| `source_id`         | Many2one  | `integer`   | YES      | FK  | `utm_source`        | Chỉ Lost lead gán (random 80% có) — Won lead không set field này                                                                                                        |
| `medium_id`         | Many2one  | `integer`   | YES      | FK  | `utm_medium`         | Chỉ Lost lead gán (random 80% có)                                                                                                                                       |
| `date_open`         | Datetime  | `timestamp` | YES      | —   | —                  | Won lead = `date_order` trừ random 3-21 ngày (sales cycle trước khi chốt). Lost lead = ngày tạo lead                                                                   |
| `date_conversion`    | Datetime  | `timestamp` | YES      | —   | —                  | Thời điểm Lead chuyển thành Opportunity; demo tạo thẳng opportunity thì = `date_open`                                                                    |
| `date_closed`        | Datetime  | `timestamp` | YES      | —   | —                  | Won = `sale_order.date_order`; lost = thời điểm đóng/mất                                                                                                         |
| `date_last_stage_update` | Datetime | `timestamp` | YES   | —   | —                  | Lần đổi stage cuối; current-state SLA dùng field này, full time-in-stage phải dùng lịch sử CDC                                                          |
| `create_date`       | Datetime  | `timestamp` | YES      | —   | —                  | ⚠️ Bị Odoo ghi đè `now()` lúc tạo qua XML-RPC — generator restore lại về `date_open` sau khi tạo (cùng pattern planned-vs-actual dùng xuyên suốt dự án)                |

---

### `sale_order` &nbsp;·&nbsp; `sale.order`

> Đơn bán (Header). Báo giá (draft) và đơn hàng (sale) chung 1 bảng, phân biệt bằng state

| Cột              | Odoo Type | DB Type     | Nullable | Key | FK Trỏ về         | Mô tả                                                                                                                                                                                                                                                                                                                                                                                                                        |
| ---------------- | --------- | ----------- | -------- | --- | ----------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `id`             | Integer   | `integer`   | NO       | PK  | —                 | Định danh tự tăng                                                                                                                                                                                                                                                                                                                                                                                                            |
| `name`           | Char      | `varchar`   | NO       | UQ  | —                 | Số SO tự sinh: S000001 / SR000001 (RFM-driven)                                                                                                                                                                                                                                                                                                                                                                               |
| `partner_id`     | Many2one  | `integer`   | NO       | FK  | `res_partner`     | ⭐ Khách hàng (customer_rank > 0)                                                                                                                                                                                                                                                                                                                                                                                            |
| `date_order`     | Datetime  | `timestamp` | NO       | —   | —                 | Ngày đặt hàng — phân phối theo mùa vụ. ⚠️⚠️ `action_confirm()` của Odoo TỰ ĐỘNG ghi đè field này thành `now()` khi confirm SO (help text gốc: "Creation date of draft/sent orders, **Confirmation date of confirmed orders**"). Nếu backfill dữ liệu lịch sử, phải confirm SO xong rồi UPDATE lại `date_order` bằng ngày lịch sử đã sinh trước đó — nếu không toàn bộ đơn confirmed sẽ dồn về đúng 1 ngày (ngày chạy script) |
| `state`          | Selection | `varchar`   | NO       | —   | —                 | ⭐ draft→sent→sale\|cancel — state machine. KHÔNG có giá trị `done`: đơn hoàn tất (đã giao + đã xuất hóa đơn) vẫn giữ `state='sale'`, độ hoàn tất đọc qua `invoice_status`/`delivery_status` bên dưới, không phải qua `state`. ~3% đơn bị cancel (`cancel_rate`) — SAU KHI đã confirm (`sale`→`cancel`), không phải hủy từ draft, nên vẫn để lại vết `stock_picking`/`stock_move` state=`cancel` thật của 1 chu trình bán hàng bị đổ vỡ                                                                                                                                                                  |
| `amount_untaxed` | Monetary  | `float8`    | NO       | —   | —                 | Tổng tiền hàng trước thuế                                                                                                                                                                                                                                                                                                                                                                                                    |
| `amount_tax`     | Monetary  | `float8`    | NO       | —   | —                 | Tổng thuế                                                                                                                                                                                                                                                                                                                                                                                                                    |
| `amount_total`   | Monetary  | `float8`    | NO       | —   | —                 | ⭐ Tổng đơn (tiền hàng + thuế)                                                                                                                                                                                                                                                                                                                                                                                               |
| `currency_id`    | Many2one  | `integer`   | NO       | FK  | `res_currency`    | Tiền tệ đơn hàng                                                                                                                                                                                                                                                                                                                                                                                                             |
| `warehouse_id`   | Many2one  | `integer`   | YES      | FK  | `stock_warehouse` | ⭐ Kho xuất hàng: WEST/EAST/CNTL/SOUT                                                                                                                                                                                                                                                                                                                                                                                        |
| `invoice_status` | Selection | `varchar`   | NO       | —   | —                 | ⭐ no\|to invoice\|invoiced\|upselling — "invoiced" = đã xuất hết hóa đơn cho đơn này                                                                                                                                                                                                                                                                                                                                                                                                     |
| `delivery_status`| Selection | `varchar`   | YES      | —   | —                 | ⭐ pending\|partial\|full — cột thật, do Odoo compute rồi lưu (`store=True`), không nhập tay. "full" = đã giao hết hàng. **Đơn được coi là HOÀN TẤT khi**: `state='sale' AND invoice_status='invoiced' AND delivery_status='full'` — không có 1 field `state` duy nhất thể hiện "done"                                                                                                                                                                                                                                                                                                                                                                                                     |
| `campaign_id`    | Many2one  | `integer`   | YES      | FK  | `utm_campaign`    | ⭐ UTM campaign — marketing revenue attribution                                                                                                                                                                                                                                                                                                                                                                              |
| `source_id`      | Many2one  | `integer`   | YES      | FK  | `utm_source`      | Nguồn UTM của đơn                                                                                                                                                                                                                                                                                                                                                                                                  |
| `medium_id`      | Many2one  | `integer`   | YES      | FK  | `utm_medium`      | Medium UTM của đơn                                                                                                                                                                                                                                                                                                                                                                                                     |
| `opportunity_id` | Many2one  | `integer`   | YES      | FK  | `crm_lead`        | Opportunity nguồn; generator Phase 2b mới ghi FK này và repair dữ liệu demo cũ                                                                                                                                                                                                                                                                                                                        |
| `carrier_id`     | Many2one  | `integer`   | YES      | FK  | `delivery_carrier` | ⚠️ Field từ module `delivery` (cài 2026-07-22). **100% NULL trên 21.156 đơn hiện có** — cài module không hồi cứu dữ liệu cũ, chỉ áp dụng cho đơn tạo mới qua UI/ORM sau khi cài                                                                                                                                                                                                                                          |
| `user_id`        | Many2one  | `integer`   | YES      | FK  | `res_users`       | Sales rep phụ trách đơn                                                                                                                                                                                                                                                                                                                                                                                                      |
| `company_id`     | Many2one  | `integer`   | NO       | FK  | `res_company`     | Công ty                                                                                                                                                                                                                                                                                                                                                                                                                      |
| `create_date`    | Datetime  | `timestamp` | YES      | —   | —                 | Ngày tạo (audit)                                                                                                                                                                                                                                                                                                                                                                                                             |
| `write_date`     | Datetime  | `timestamp` | YES      | —   | —                 | Ngày sửa cuối — CDC trigger khi state thay đổi                                                                                                                                                                                                                                                                                                                                                                               |
| `create_uid`     | Many2one  | `integer`   | YES      | FK  | `res_users`       | Ai tạo (audit)                                                                                                                                                                                                                                                                                                                                                                                                               |

### `sale_order_line` &nbsp;·&nbsp; `sale.order.line`

> ⭐ GRAIN của fact_sales. 1 row = 1 sản phẩm trong đơn. Dùng COUNT DISTINCT order_id để đếm số đơn

| Cột               | Odoo Type | DB Type   | Nullable | Key | FK Trỏ về         | Mô tả                                                               |
| ----------------- | --------- | --------- | -------- | --- | ----------------- | ------------------------------------------------------------------- |
| `id`              | Integer   | `integer` | NO       | PK  | —                 | Định danh tự tăng                                                   |
| `order_id`        | Many2one  | `integer` | NO       | FK  | `sale_order`      | ⭐ Thuộc SO nào (header)                                            |
| `product_id`      | Many2one  | `integer` | YES      | FK  | `product_product` | ⭐ SKU variant — KHÔNG phải template                                |
| `name`            | Text      | `text`    | NO       | —   | —                 | Mô tả dòng (tự điền từ tên SP)                                      |
| `product_uom_qty` | Float     | `float8`  | NO       | —   | —                 | ⭐ Số lượng đặt                                                     |
| `qty_delivered`   | Float     | `float8`  | NO       | —   | —                 | Đã giao thực tế — so với product_uom_qty = delivery KPI             |
| `qty_invoiced`    | Float     | `float8`  | NO       | —   | —                 | Đã xuất hóa đơn                                                     |
| `price_unit`      | Float     | `float8`  | NO       | —   | —                 | ⭐ Đơn giá bán (có thể khác list_price nếu có thỏa thuận)           |
| `discount`        | Float     | `float8`  | NO       | —   | —                 | ⭐ % Chiết khấu: 5/10/15/20 theo bậc B2B. Deep discount → margin âm |
| `price_subtotal`  | Float     | `float8`  | NO       | —   | —                 | ⭐ Computed: qty × price × (1-discount%). Grain của fact_sales      |
| `price_tax`       | Float     | `float8`  | NO       | —   | —                 | Tiền thuế của dòng                                                  |
| `price_total`     | Float     | `float8`  | NO       | —   | —                 | price_subtotal + price_tax                                          |
| `product_uom`     | Many2one  | `integer` | YES      | FK  | `uom_uom`         | Đơn vị tính của dòng                                                |
| `customer_lead`   | Float     | `float8`  | NO       | —   | —                 | ⭐ Số ngày lead time của dòng — default copy từ `product_template.sale_delay` lúc TẠO dòng (không tự sync lại nếu sau đó đổi `sale_delay`). Dùng tính `stock_picking.scheduled_date` — xem công thức đầy đủ ở đó |

---

## Transaction — Purchasing

### `purchase_order` &nbsp;·&nbsp; `purchase.order`

> Đơn mua (Header). P2P cycle: RFQ → PO confirm → Goods Receipt → 3-way match → Payment

| Cột            | Odoo Type | DB Type     | Nullable | Key | FK Trỏ về      | Mô tả                                           |
| -------------- | --------- | ----------- | -------- | --- | -------------- | ----------------------------------------------- |
| `id`           | Integer   | `integer`   | NO       | PK  | —              | Định danh tự tăng                               |
| `name`         | Char      | `varchar`   | NO       | UQ  | —              | Số PO tự sinh: P000001...                       |
| `partner_id`   | Many2one  | `integer`   | NO       | FK  | `res_partner`  | ⭐ Nhà cung cấp (supplier_rank > 0)             |
| `date_order`   | Datetime  | `timestamp` | YES      | —   | —              | Ngày tạo PO                                     |
| `date_planned` | Datetime  | `timestamp` | YES      | —   | —              | Ngày hẹn giao hàng — basis on-time delivery KPI |
| `state`        | Selection | `varchar`   | NO       | —   | —              | draft\|sent\|purchase\|done\|cancel             |
| `amount_total` | Monetary  | `float8`    | NO       | —   | —              | Tổng giá trị PO                                 |
| `currency_id`  | Many2one  | `integer`   | NO       | FK  | `res_currency` | Tiền tệ PO                                      |
| `company_id`   | Many2one  | `integer`   | NO       | FK  | `res_company`  | Công ty                                         |
| `user_id`      | Many2one  | `integer`   | YES      | FK  | `res_users`    | Buyer phụ trách                                 |

### `purchase_order_line` &nbsp;·&nbsp; `purchase.order.line`

> Dòng đơn mua. qty_received vs product_qty = on-time delivery rate NCC. Basis 3-way match

| Cột              | Odoo Type | DB Type     | Nullable | Key | FK Trỏ về         | Mô tả                                                     |
| ---------------- | --------- | ----------- | -------- | --- | ----------------- | --------------------------------------------------------- |
| `id`             | Integer   | `integer`   | NO       | PK  | —                 | Định danh tự tăng                                         |
| `order_id`       | Many2one  | `integer`   | NO       | FK  | `purchase_order`  | ⭐ Thuộc PO nào                                           |
| `product_id`     | Many2one  | `integer`   | YES      | FK  | `product_product` | ⭐ Sản phẩm / nguyên liệu mua                             |
| `name`           | Text      | `text`      | NO       | —   | —                 | Mô tả dòng                                                |
| `product_qty`    | Float     | `float8`    | NO       | —   | —                 | ⭐ Số lượng đặt mua                                       |
| `qty_received`   | Float     | `float8`    | NO       | —   | —                 | ⭐ Đã nhận thực tế (3-way match: so với product_qty)      |
| `qty_invoiced`   | Float     | `float8`    | NO       | —   | —                 | ⚠️ Tên field thật là `qty_invoiced`, KHÔNG phải `qty_billed`. Đã được ghi vào vendor bill |
| `price_unit`     | Float     | `float8`    | NO       | —   | —                 | ⭐ Giá mua đơn vị — basis 3-way match giá với vendor bill |
| `price_subtotal` | Float     | `float8`    | NO       | —   | —                 | Tổng tiền dòng = qty × price_unit                         |
| `product_uom`    | Many2one  | `integer`   | YES      | FK  | `uom_uom`         | Đơn vị tính                                               |
| `date_planned`   | Datetime  | `timestamp` | YES      | —   | —                 | Ngày hẹn giao cho dòng này (có thể khác header)           |

---

## Transaction — Inventory

### `stock_picking` &nbsp;·&nbsp; `stock.picking`

> Phiếu kho (Header) — tự sinh khi confirm SO/PO. origin trỏ về số SO/PO nguồn

| Cột              | Odoo Type | DB Type     | Nullable | Key | FK Trỏ về     | Mô tả                                                                                                                                                                                                                                                                                                                                                                                           |
| ---------------- | --------- | ----------- | -------- | --- | ------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `id`             | Integer   | `integer`   | NO       | PK  | —             | Định danh tự tăng                                                                                                                                                                                                                                                                                                                                                                               |
| `name`           | Char      | `varchar`   | YES      | UQ  | —             | Số phiếu: WH/IN/00001 (nhận)\|WH/OUT/00001 (xuất)                                                                                                                                                                                                                                                                                                                                               |
| `partner_id`     | Many2one  | `integer`   | YES      | FK  | `res_partner` | Giao/nhận từ ai (KH hoặc NCC)                                                                                                                                                                                                                                                                                                                                                                   |
| `sale_id`        | Many2one  | `integer`   | YES      | FK  | `sale_order`  | ⭐ SO nguồn (delivery) — dùng join ngược thay vì parse `origin` bằng text                                                                                                                                                                                                                                                                                                                       |
| `state`          | Selection | `varchar`   | YES      | —   | —             | draft\|waiting\|confirmed\|assigned\|done\|cancel                                                                                                                                                                                                                                                                                                                                               |
| `origin`         | Char      | `varchar`   | YES      | —   | —             | Số SO/PO nguồn dạng text — tồn tại song song với `sale_id`/`purchase_id` (FK có cấu trúc, nên ưu tiên dùng FK để join)                                                                                                                                                                                                                                                                          |
| `scheduled_date` | Datetime  | `timestamp` | YES      | —   | —             | ⭐ **KẾ HOẠCH** — ngày kho HẸN xuất/giao hàng. So với `date_done` = cơ sở tính on-time vs late. **Công thức chuẩn Odoo (từ 2026-07-22, xem `scripts/superstore_data_generator.py` dòng ~782-808):**<br>`commitment_date = date_order + sale_delay + stock_rule.delay`<br>`scheduled_date  = commitment_date − security_lead`<br>`                = date_order + sale_delay + stock_rule.delay − security_lead`<br>• `sale_delay` = `sale_order_line.customer_lead` (MAX theo dòng, copy từ `product_template.sale_delay`)<br>• `stock_rule.delay` = "Lead Time" của rule `<WH>: Stock → Customers` — set **2 ngày** (WEST/EAST) · **3 ngày** (CNTL/SOUT)<br>• `security_lead` = `res_company.security_lead` = **2 ngày** — kéo ngày kho SẴN SÀNG sớm hơn `commitment_date` (buffer)<br>Với config hiện tại (`sale_delay=3`): **commitment_date = +5 ngày (WEST/EAST) / +6 ngày (CNTL/SOUT)**, **scheduled_date = +3 ngày (WEST/EAST) / +4 ngày (CNTL/SOUT)**. Fallback 1 ngày nếu `sched_days ≤ 0` (chưa cấu hình). ⚠️ 20.862 phiếu ĐÃ SINH trước 2026-07-22 vẫn giữ công thức cũ (`date_order + 1 ngày`) — công thức mới chỉ áp dụng khi chạy lại generator |
| `date_deadline`  | Datetime  | `timestamp` | YES      | —   | —             | Hạn chót kế hoạch — trong dataset này set trùng `scheduled_date`                                                                                                                                                                                                                                                                                                                                |
| `date`           | Datetime  | `timestamp` | YES      | —   | —             | Field kỹ thuật Odoo dùng sắp xếp/hiển thị — trong dataset này set trùng `date_done` (ngày thực tế)                                                                                                                                                                                                                                                                                              |
| `date_done`      | Datetime  | `timestamp` | YES      | —   | —             | ⭐⭐ **THỰC TẾ** — ngày kho hoàn tất `button_validate()` (hàng rời kho nội bộ). Trung bình ~8% phiếu trễ hơn `scheduled_date` 1-5 ngày (imperfection `late_delivery`), nhưng KHÔNG đều giữa các kho — kho `CNTL` (Central) bị lệch cao hơn hẳn (~2.5x tỉ lệ trung bình), 3 kho còn lại thấp hơn (~0.7x), phản ánh vấn đề vận hành cục bộ tại 1 kho thay vì độ trễ ngẫu nhiên đồng đều. ⚠️ `button_validate()` mặc định stamp field này = `now()` tại thời điểm chạy script — nếu backfill dữ liệu lịch sử PHẢI ghi đè lại sau khi validate xong, nếu không toàn bộ phiếu sẽ dồn về đúng ngày chạy script |
| `carrier_id`     | Many2one  | `integer`   | YES      | FK  | `delivery_carrier` | ⚠️ Field từ module `stock_delivery` (cài 2026-07-22, KHÁC module `delivery` — xem bảng `delivery_carrier` bên dưới). **100% NULL trên 23.374 phiếu hiện có**, không hồi cứu |
| `carrier_price`  | Float     | `float8`   | YES      | —   | —             | Cước phí giao hàng — từ `stock_delivery`, cùng tình trạng NULL như `carrier_id` |
| `carrier_tracking_ref` | Char | `varchar`  | YES      | —   | —             | Mã tracking hãng vận chuyển — từ `stock_delivery`, hiện chưa có dữ liệu nào |
| `company_id`     | Many2one  | `integer`   | YES      | FK  | `res_company` | Công ty                                                                                                                                                                                                                                                                                                                                                                                         |

### `stock_move` &nbsp;·&nbsp; `stock.move`

> ⭐ NHẬT KÝ di chuyển hàng. Grain của fact_inventory_movement. Mọi biến động đều thành 1 move

| Cột                | Odoo Type | DB Type     | Nullable | Key | FK Trỏ về         | Mô tả                                                                                                                                           |
| ------------------ | --------- | ----------- | -------- | --- | ----------------- | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| `id`               | Integer   | `integer`   | NO       | PK  | —                 | Định danh tự tăng                                                                                                                               |
| `picking_id`       | Many2one  | `integer`   | YES      | FK  | `stock_picking`   | Thuộc phiếu kho nào (NULL = move nội bộ)                                                                                                        |
| `product_id`       | Many2one  | `integer`   | NO       | FK  | `product_product` | ⭐ Sản phẩm di chuyển                                                                                                                           |
| `product_uom_qty`  | Float     | `numeric`   | NO       | —   | —                 | ⭐ Số lượng kế hoạch                                                                                                                            |
| `quantity`         | Float     | `numeric`   | YES      | —   | —                 | ⚠️ Tên field thật là `quantity` (Odoo 17+ đổi từ `quantity_done`). Số lượng thực tế đã thực hiện                                                |
| `picked`           | Boolean   | `boolean`   | YES      | —   | —                 | ⭐ Field mới đi kèm `quantity` — phải set `true` TRƯỚC KHI gọi `button_validate()`, nếu không di chuyển sẽ không hoàn tất đúng                  |
| `location_id`      | Many2one  | `integer`   | NO       | FK  | `stock_location`  | ⭐ Vị trí NGUỒN (từ đâu)                                                                                                                        |
| `location_dest_id` | Many2one  | `integer`   | NO       | FK  | `stock_location`  | ⭐ Vị trí ĐÍCH (đến đâu)                                                                                                                        |
| `state`            | Selection | `varchar`   | YES      | —   | —                 | draft\|waiting\|confirmed\|assigned\|done\|cancel                                                                                               |
| `date`             | Datetime  | `timestamp` | NO       | —   | —                 | ⭐ Thời điểm THỰC TẾ thực hiện move — set trùng `stock_picking.date_done` của phiếu chứa nó (mốc "hàng rời kho", xem ghi chú ở `stock_picking`) |
| `date_deadline`    | Datetime  | `timestamp` | YES      | —   | —                 | Hạn chót KẾ HOẠCH — set trùng `stock_picking.scheduled_date`. So với `date` = on-time vs late ở mức từng move                                   |
| `product_uom`      | Many2one  | `integer`   | NO       | FK  | `uom_uom`         | Đơn vị tính                                                                                                                                     |
| `company_id`       | Many2one  | `integer`   | NO       | FK  | `res_company`     | Công ty                                                                                                                                         |

### `stock_quant` &nbsp;·&nbsp; `stock.quant`

> ⭐ Số dư tồn kho HIỆN TẠI — derived từ stock_move. KHÔNG sửa tay. = Σ (moves vào) - Σ (moves ra)

| Cột                 | Odoo Type | DB Type     | Nullable | Key | FK Trỏ về         | Mô tả                                               |
| ------------------- | --------- | ----------- | -------- | --- | ----------------- | --------------------------------------------------- |
| `id`                | Integer   | `integer`   | NO       | PK  | —                 | Định danh tự tăng                                   |
| `product_id`        | Many2one  | `integer`   | NO       | FK  | `product_product` | SP nào                                              |
| `location_id`       | Many2one  | `integer`   | NO       | FK  | `stock_location`  | Tại vị trí nào (chỉ internal location)              |
| `quantity`          | Float     | `float8`    | NO       | —   | —                 | ⭐ Tồn thực tế = Σ stock_move done vào trừ ra       |
| `reserved_quantity` | Float     | `float8`    | NO       | —   | —                 | Đã đặt chỗ cho đơn chờ xuất (chưa rời kho)          |
| `inventory_quantity` | Float    | `numeric`   | YES      | —   | —                 | "Counted Quantity" — số lượng đếm được khi kiểm kê thủ công (physical inventory). Hiện có giá trị trên **1.812/3.211** dòng, còn lại NULL (chưa từng kiểm kê) |
| `inventory_diff_quantity` | Float | `numeric`  | YES      | —   | —                 | "Difference" — help text gốc Odoo: chênh lệch giữa tồn LÝ THUYẾT (`quantity`) và tồn ĐẾM THỰC TẾ (`inventory_quantity`). Non-NULL trên cả 3.211 dòng (computed field, mặc định 0 nếu chưa đếm) — ⚠️ `inventory_quantity_set=true` trên **0/3.211** dòng → chưa có lần kiểm kê nào được "áp dụng" (apply) chính thức |
| `company_id`        | Many2one  | `integer`   | NO       | FK  | `res_company`     | Công ty                                             |
| `write_date`        | Datetime  | `timestamp` | YES      | —   | —                 | Lần cập nhật cuối — dùng snapshot tồn kho hằng ngày |

### `stock_valuation_layer` &nbsp;·&nbsp; `stock.valuation.layer`

> ⭐ NHẬT KÝ định giá tồn kho — 1 dòng/1 stock_move ảnh hưởng giá trị hàng tồn (COGS). Đã có trong SRS Phụ lục E.1/E.2 (nguồn `fact_inventory_valuation`) nhưng trước đây CHƯA được đưa vào data dictionary — bổ sung 2026-07-23. **98.143 dòng, đã có dữ liệu đầy đủ** (quantity/unit_cost/value không NULL dòng nào)

| Cột               | Odoo Type | DB Type     | Nullable | Key | FK Trỏ về         | Mô tả                                                                                          |
| ------------------ | --------- | ----------- | -------- | --- | ------------------ | ------------------------------------------------------------------------------------------------ |
| `id`               | Integer   | `integer`   | NO       | PK  | —                  | Định danh tự tăng                                                                               |
| `product_id`       | Many2one  | `integer`   | NO       | FK  | `product_product`  | ⭐ SP được định giá                                                                             |
| `company_id`       | Many2one  | `integer`   | NO       | FK  | `res_company`      | Công ty                                                                                         |
| `stock_move_id`    | Many2one  | `integer`   | YES      | FK  | `stock_move`       | ⭐ Move nào tạo ra lớp định giá này (nhập kho = +, xuất kho = −)                                |
| `quantity`         | Float     | `numeric`   | YES      | —   | —                  | ⭐ Số lượng của move — âm khi xuất kho (COGS), dương khi nhập kho                               |
| `unit_cost`        | Float     | `numeric`   | YES      | —   | —                  | ⭐ Giá vốn đơn vị tại thời điểm move (theo phương pháp valuation của SP: FIFO/AVCO/Standard)    |
| `value`            | Float     | `numeric`   | YES      | —   | —                  | ⭐⭐ = quantity × unit_cost — GIÁ TRỊ biến động, nguồn COGS/fact_inventory_valuation             |
| `remaining_qty`    | Float     | `numeric`   | YES      | —   | —                  | Số lượng còn lại CHƯA được "tiêu thụ" bởi 1 lớp xuất kho khác (chỉ có ý nghĩa với FIFO)          |
| `remaining_value`  | Float     | `numeric`   | YES      | —   | —                  | Giá trị còn lại tương ứng `remaining_qty`                                                       |
| `account_move_id`  | Many2one  | `integer`   | YES      | FK  | `account_move`     | Bút toán kế toán tương ứng (nếu SP dùng Automated valuation)                                    |
| `description`      | Char      | `varchar`   | YES      | —   | —                  | Diễn giải nguồn gốc — vd "INV/2026/0001", tên phiếu kho                                         |
| `create_date`      | Datetime  | `timestamp` | YES      | —   | —                  | Thời điểm tạo lớp định giá — dùng làm mốc thời gian trong `fact_inventory_valuation`             |

---

## Transaction — Accounting

### `account_move` &nbsp;·&nbsp; `account.move`

> Hóa đơn + Bút toán (Header). out_invoice / in_invoice / entry chung 1 bảng, phân biệt bằng move_type

| Cột               | Odoo Type | DB Type   | Nullable | Key | FK Trỏ về         | Mô tả                                                           |
| ----------------- | --------- | --------- | -------- | --- | ----------------- | --------------------------------------------------------------- |
| `id`              | Integer   | `integer` | NO       | PK  | —                 | Định danh tự tăng                                               |
| `name`            | Char      | `varchar` | YES      | —   | —                 | Số chứng từ: INV/2024/0001\|BILL/2024/0001                      |
| `move_type`       | Selection | `varchar` | NO       | —   | —                 | ⭐ out_invoice\|in_invoice\|out_refund\|in_refund\|entry        |
| `partner_id`      | Many2one  | `integer` | YES      | FK  | `res_partner`     | ⭐ Đối tượng công nợ (KH hoặc NCC)                              |
| `invoice_date`    | Date      | `date`    | YES      | —   | —                 | Ngày HĐ (accrual basis — khác ngày thu tiền)                    |
| `state`           | Selection | `varchar` | NO       | —   | —                 | draft\|posted (đã ghi sổ, không sửa)\|cancel                    |
| `journal_id`      | Many2one  | `integer` | NO       | FK  | `account_journal` | Sổ nhật ký                                                      |
| `currency_id`     | Many2one  | `integer` | NO       | FK  | `res_currency`    | Tiền tệ                                                         |
| `amount_untaxed`  | Monetary  | `float8`  | NO       | —   | —                 | Tiền hàng trước thuế                                            |
| `amount_tax`      | Monetary  | `float8`  | NO       | —   | —                 | Tiền thuế                                                       |
| `amount_total`    | Monetary  | `float8`  | NO       | —   | —                 | ⭐ Tổng HĐ                                                      |
| `amount_residual` | Monetary  | `float8`  | NO       | —   | —                 | ⭐ Còn nợ chưa thanh toán. = 0 khi đã tất toán (basis AR aging) |
| `payment_state`   | Selection | `varchar` | YES      | —   | —                 | not_paid\|partial\|paid\|in_payment                             |
| `campaign_id`     | Many2one  | `integer` | YES      | FK  | `utm_campaign`    | UTM — marketing revenue attribution                             |
| `company_id`      | Many2one  | `integer` | NO       | FK  | `res_company`     | Công ty                                                         |

### `account_move_line` &nbsp;·&nbsp; `account.move.line`

> ⭐⭐ Dòng bút toán — DOUBLE ENTRY LAW: trong mỗi move: Σ debit = Σ credit (bắt buộc, không có ngoại lệ)

| Cột               | Odoo Type | DB Type   | Nullable | Key | FK Trỏ về         | Mô tả                                                       |
| ----------------- | --------- | --------- | -------- | --- | ----------------- | ----------------------------------------------------------- |
| `id`              | Integer   | `integer` | NO       | PK  | —                 | Định danh tự tăng                                           |
| `move_id`         | Many2one  | `integer` | NO       | FK  | `account_move`    | ⭐ Thuộc chứng từ nào                                       |
| `account_id`      | Many2one  | `integer` | NO       | FK  | `account_account` | ⭐ Ghi vào tài khoản nào (1200 AR / 4000 Revenue / 2000 AP) |
| `partner_id`      | Many2one  | `integer` | YES      | FK  | `res_partner`     | Đối tác liên quan (cho TK công nợ AR/AP)                    |
| `name`            | Char      | `varchar` | YES      | —   | —                 | Mô tả dòng bút toán                                         |
| `debit`           | Monetary  | `float8`  | NO       | —   | —                 | ⭐ Số tiền NỢ                                               |
| `credit`          | Monetary  | `float8`  | NO       | —   | —                 | ⭐ Số tiền CÓ — Σ debit = Σ credit không có ngoại lệ        |
| `amount_currency` | Monetary  | `float8`  | NO       | —   | —                 | Số tiền theo tiền tệ gốc của dòng (nếu khác USD)            |
| `date`            | Date      | `date`    | NO       | —   | —                 | Ngày bút toán có hiệu lực                                   |
| `payment_id`      | Many2one  | `integer` | YES      | FK  | `account_payment` | ⚠️ CHỈ set trên dòng thuộc chính move của payment đó — KHÔNG set trên dòng của hóa đơn. KHÔNG dùng field này để tìm hóa đơn của payment (xem `account_partial_reconcile`) |
| `reconciled`      | Boolean   | `boolean` | YES      | —   | —                 | ⭐ true = dòng AR/AP này đã được đối soát (khớp nợ-có) xong |
| `matching_number` | Char      | `varchar` | YES      | —   | —                 | ⭐ Mọi dòng cùng 1 lần reconcile chia sẻ chung giá trị này — cách NGẮN NHẤT để nối payment↔invoice, không cần qua `account_partial_reconcile` (xem ví dụ ở bảng đó) |
| `full_reconcile_id` | Many2one | `integer` | YES      | FK  | `account_full_reconcile` | Nhóm reconcile đầy đủ (khi tổng debit=credit vừa khít, không còn dư) |
| `company_id`      | Many2one  | `integer` | NO       | FK  | `res_company`     | Công ty                                                     |

### `account_payment` &nbsp;·&nbsp; `account.payment`

> Thanh toán thu/chi. Reconcile với account_move → amount_residual về 0

| Cột            | Odoo Type | DB Type   | Nullable | Key | FK Trỏ về         | Mô tả                                                                                                                                                                                                                               |
| -------------- | --------- | --------- | -------- | --- | ----------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `id`           | Integer   | `integer` | NO       | PK  | —                 | Định danh tự tăng                                                                                                                                                                                                                   |
| `partner_id`   | Many2one  | `integer` | YES      | FK  | `res_partner`     | Đối tác (KH thu tiền / NCC trả tiền)                                                                                                                                                                                                |
| `amount`       | Monetary  | `float8`  | NO       | —   | —                 | ⭐ Số tiền thanh toán                                                                                                                                                                                                               |
| `payment_type` | Selection | `varchar` | NO       | —   | —                 | inbound=thu từ KH\|outbound=trả cho NCC                                                                                                                                                                                             |
| `state`        | Selection | `varchar` | NO       | —   | —                 | ⚠️ Odoo 18 KHÔNG có state `posted`. Chuỗi thật: `draft` → `in_process` (đã post, đang chờ đối soát bank) → `paid` (đã reconcile xong) — hoặc `canceled` \|`rejected`. `action_post()` chuyển sang `in_process`, không phải `posted`. Dataset này: 100% = `paid` (11.108/11.108) |
| `journal_id`   | Many2one  | `integer` | NO       | FK  | `account_journal` | Kênh thanh toán: Bank (BNK)\|Cash (CSH)                                                                                                                                                                                             |
| `date`         | Date      | `date`    | NO       | —   | —                 | ⭐ Ngày thanh toán thực tế — basis DSO = date - invoice_date                                                                                                                                                                        |
| `currency_id`  | Many2one  | `integer` | NO       | FK  | `res_currency`    | Tiền tệ thanh toán                                                                                                                                                                                                                  |
| `move_id`      | Many2one  | `integer` | YES      | FK  | `account_move`    | ⭐ Journal entry CỦA CHÍNH payment (vd "PBNK1/2026/00001") — KHÔNG phải hóa đơn. Muốn tới hóa đơn phải đi tiếp qua `account_move_line`/`account_partial_reconcile`, xem bảng đó |
| `is_reconciled` | Boolean  | `boolean` | YES      | —   | —                 | true = đã đối soát xong với (các) hóa đơn liên quan. 11.108/11.108 = true (2026-07-23, sau khi chạy reconcile qua ORM — xem `account_partial_reconcile`) |
| `company_id`   | Many2one  | `integer` | NO       | FK  | `res_company`     | Công ty                                                                                                                                                                                                                             |

### `account_partial_reconcile` &nbsp;·&nbsp; `account.partial.reconcile`

> ⭐⭐ Bảng NỐI THẬT giữa `account_payment` và hóa đơn (`account_move`) — mọi cách join khác (qua `payment_id` trên move_line, qua tên/ref) đều SAI hoặc không đủ. Trước 2026-07-23: **0 dòng** (generator chỉ ép `payment_state='paid'` bằng raw SQL, không bao giờ gọi reconcile thật). Đã chạy `account.move.line.reconcile()` qua ORM cho toàn bộ 11.108 cặp payment↔invoice/bill (khớp partner_id+amount 1:1 tuyệt đối) → giờ có **11.108 dòng**, khớp chính xác 100% với `account_payment` (8.890 AR + 2.218 AP)

| Cột               | Odoo Type | DB Type   | Nullable | Key | FK Trỏ về         | Mô tả                                                                                       |
| ------------------ | --------- | --------- | -------- | --- | ------------------ | --------------------------------------------------------------------------------------------- |
| `id`               | Integer   | `integer` | NO       | PK  | —                  | Định danh tự tăng                                                                             |
| `debit_move_id`    | Many2one  | `integer` | NO       | FK  | `account_move_line` | ⭐ Dòng bên NỢ trong cặp khớp — với AR: dòng của hóa đơn; với AP: dòng của payment            |
| `credit_move_id`   | Many2one  | `integer` | NO       | FK  | `account_move_line` | ⭐ Dòng bên CÓ trong cặp khớp — với AR: dòng của payment; với AP: dòng của hóa đơn (chiều NGƯỢC AR — phải dùng `debit_move_id = x OR credit_move_id = x` khi join, không hardcode 1 chiều) |
| `full_reconcile_id` | Many2one | `integer` | YES      | FK  | `account_full_reconcile` | Nhóm reconcile đầy đủ tương ứng                                                          |
| `amount`           | Monetary  | `numeric` | YES      | —   | —                  | Số tiền được khớp trong cặp này                                                              |
| `max_date`         | Date      | `date`    | YES      | —   | —                  | Ngày muộn nhất trong 2 dòng — dùng tính DSO thực tế                                          |
| `company_id`       | Many2one  | `integer` | YES      | FK  | `res_company`      | Công ty                                                                                       |

**Join payment → invoice (đã verify 11.108/11.108 khớp, xem thêm Cách B đơn giản hơn qua `matching_number` ở `account_move_line`):**
```sql
SELECT ap.id AS payment_id, am_inv.id AS invoice_id, am_inv.name, am_inv.move_type
FROM account_payment ap
JOIN account_move_line aml_pay ON aml_pay.payment_id = ap.id
JOIN account_partial_reconcile apr
     ON apr.debit_move_id = aml_pay.id OR apr.credit_move_id = aml_pay.id
JOIN account_move_line aml_inv
     ON aml_inv.id = CASE WHEN apr.debit_move_id = aml_pay.id
                          THEN apr.credit_move_id ELSE apr.debit_move_id END
JOIN account_move am_inv ON am_inv.id = aml_inv.move_id AND am_inv.id != aml_pay.move_id
```

### `account_full_reconcile` &nbsp;·&nbsp; `account.full.reconcile`

> Nhóm các `account_partial_reconcile` khi tổng debit=credit khớp vừa khít (không còn dư nợ/có). 11.108 dòng — 1:1 với `account_partial_reconcile` vì dataset này mọi payment đều trả ĐÚNG số tiền hóa đơn (không có thanh toán từng phần)

| Cột    | Odoo Type | DB Type   | Nullable | Key | FK Trỏ về | Mô tả              |
| ------- | --------- | --------- | -------- | --- | --------- | -------------------- |
| `id`    | Integer   | `integer` | NO       | PK  | —         | Định danh tự tăng   |
| `name`  | Char      | `varchar` | YES      | UQ  | —         | Mã tự sinh          |

---

## Transaction — Manufacturing

### `mrp_production` &nbsp;·&nbsp; `mrp.production`

> Lệnh sản xuất MO. Confirm = xuất NVL khỏi kho + tạo work orders. Done = nhập thành phẩm vào kho

| Cột              | Odoo Type | DB Type     | Nullable | Key | FK Trỏ về         | Mô tả                                                                                                                                                                                                                                                                                                                                                                                                                                |
| ---------------- | --------- | ----------- | -------- | --- | ----------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `id`             | Integer   | `integer`   | NO       | PK  | —                 | Định danh tự tăng                                                                                                                                                                                                                                                                                                                                                                                                                    |
| `name`           | Char      | `varchar`   | NO       | UQ  | —                 | Số MO: MO/2024/0001...                                                                                                                                                                                                                                                                                                                                                                                                               |
| `product_id`     | Many2one  | `integer`   | NO       | FK  | `product_product` | ⭐ Sản phẩm cần sản xuất (thành phẩm)                                                                                                                                                                                                                                                                                                                                                                                                |
| `bom_id`         | Many2one  | `integer`   | YES      | FK  | `mrp_bom`         | ⭐ BOM áp dụng — định mức NVL + routing công đoạn                                                                                                                                                                                                                                                                                                                                                                                    |
| `product_qty`    | Float     | `numeric`   | NO       | —   | —                 | Số lượng cần sản xuất                                                                                                                                                                                                                                                                                                                                                                                                                |
| `qty_producing`  | Float     | `numeric`   | YES      | —   | —                 | Đang sản xuất (intermediate)                                                                                                                                                                                                                                                                                                                                                                                                         |
| `product_uom_id` | Many2one  | `integer`   | NO       | FK  | `uom_uom`         | Đơn vị tính thành phẩm                                                                                                                                                                                                                                                                                                                                                                                                               |
| `state`          | Selection | `varchar`   | YES      | —   | —                 | draft\|confirmed\|progress\|to_close\|done\|cancel. ⚠️ `to_close` là state COMPUTED (không phải trạng thái set tay) — MO tự chuyển sang `to_close` khi mọi work order done nhưng bản thân MO chưa gọi `button_mark_done()` thành công. Nếu thấy nhiều MO kẹt ở `to_close`, nghĩa là `button_mark_done()` đang trả về 1 wizard (Consumption Warning / Backorder) thay vì hoàn tất — cần check giá trị trả về, không chỉ bắt exception |
| `date_start`     | Datetime  | `timestamp` | **NO**   | —   | —                 | ⚠️ Tên field thật là `date_start`, KHÔNG phải `date_planned_start`. Ngày bắt đầu kế hoạch                                                                                                                                                                                                                                                                                                                                            |
| `date_finished`  | Datetime  | `timestamp` | YES      | —   | —                 | Ngày hoàn thành thực tế                                                                                                                                                                                                                                                                                                                                                                                                              |
| `company_id`     | Many2one  | `integer`   | NO       | FK  | `res_company`     | Công ty                                                                                                                                                                                                                                                                                                                                                                                                                              |

### `mrp_workorder` &nbsp;·&nbsp; `mrp.workorder`

> Work Order — 1 công đoạn trong MO. duration_expected vs duration = hiệu suất work center (OEE)

| Cột                 | Odoo Type | DB Type            | Nullable | Key | FK Trỏ về        | Mô tả                                                                                                                             |
| ------------------- | --------- | ------------------ | -------- | --- | ---------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| `id`                | Integer   | `integer`          | NO       | PK  | —                | Định danh tự tăng                                                                                                                 |
| `name`              | Char      | `varchar`          | NO       | —   | —                | Tên công đoạn: OP-01: Cutting / OP-02: Assembly / OP-03: QC                                                                       |
| `production_id`     | Many2one  | `integer`          | NO       | FK  | `mrp_production` | ⭐ Thuộc MO nào                                                                                                                   |
| `workcenter_id`     | Many2one  | `integer`          | NO       | FK  | `mrp_workcenter` | ⭐ Thực hiện tại work center nào                                                                                                  |
| `state`             | Selection | `varchar`          | YES      | —   | —                | pending\|ready\|progress\|done\|cancel                                                                                            |
| `duration_expected` | Float     | `numeric`          | YES      | —   | —                | Compute field, Odoo tự tính lúc `action_confirm()` tạo work order (KHÔNG set tay): `CEIL(qty_producing / workcenter.default_capacity) × operation.time_cycle_manual × 100/workcenter.time_efficiency`. Trong dự án này `time_start=time_stop=0`, `time_efficiency=100%` nên rút gọn còn `CEIL(qty/default_capacity) × time_cycle_manual` — chỉ bằng phép nhân thẳng `qty × time_cycle_manual` khi `default_capacity=1` (case của WC-QC). Field này ĐÚNG tên trên mrp.workorder — khác với `mrp_routing_workcenter` dùng `time_cycle_manual` |
| `duration`          | Float     | `double precision` | YES      | —   | —                | ⭐ Field compute+inverse của Odoo (`compute='_compute_duration', inverse='_set_duration', store=True`) — trong Odoo thật = TỔNG các đoạn `date_end−date_start` của mọi dòng `mrp_workcenter_productivity` (loss_type='productive') gắn với WO, sinh ra khi công nhân bấm Start/Pause/Done trên Tablet View tại xưởng. Generator v3 mô phỏng bằng cách tự SET: `duration_expected` × hệ số ngẫu nhiên 0.85–1.35 (~94% workorder) hoặc 1.4–2.2 (~6% — chậm bất thường) — dùng làm chỉ số Performance của OEE. ⚠️ KHÔNG bằng `date_finished−date_start` khi WO có block availability/quality trước (~14% WO) — luôn lấy thẳng cột này, không tự tính lại từ 2 mốc ngày |
| `date_start`        | Datetime  | `timestamp`        | YES      | —   | —                | ⚠️ Tên field thật là `date_start`, KHÔNG phải `date_planned_start`. Neo theo lịch sử của MO cha, các work order trong cùng 1 MO chạy nối tiếp nhau (+ khoảng chuyển ca 5-20 phút) — không dồn về ngày chạy script. Với WO có block sự cố, đây là lúc bắt đầu BLOCK ĐẦU TIÊN (có thể là availability/quality), KHÔNG phải lúc bắt đầu chạy thật (productive)                                |
| `date_finished`     | Datetime  | `timestamp`        | YES      | —   | —                | Ngày hoàn thành thực tế = `date_start` + `duration` + các khối downtime/quality nếu có (xem `mrp_workcenter_productivity`) — vì vậy khoảng `date_finished−date_start` có thể LỚN HƠN `duration` riêng lẻ                                                       |

### `mrp_workcenter_productivity` &nbsp;·&nbsp; `mrp.workcenter.productivity`

> Sổ OEE gốc của Odoo — mỗi block thời gian gắn với 1 `loss_id` (productive\|availability\|performance\|quality). Đây là nguồn dữ liệu chính để tính OEE = Availability × Performance × Quality, không cần bảng tự chế
>
> ⚠️ **Availability = SUM(duration WHERE loss_type='productive') / SUM(duration WHERE loss_type IN ('productive','availability'))** — CHỈ cộng 2/4 loại. KHÔNG cộng thêm `quality`/`performance` vào mẫu số — đó là nguyên liệu của 2 chỉ số OEE khác (Quality dùng bảng `stock_scrap` riêng; Performance dùng `duration_expected/duration`, không dùng block trong bảng này)

| Cột             | Odoo Type | DB Type             | Nullable | Key | FK Trỏ về                       | Mô tả                                                                                                                                                                       |
| ---------------- | --------- | ------------------- | -------- | --- | -------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `id`              | Integer   | `integer`           | NO       | PK  | —                                 | Định danh tự tăng                                                                                                                                                                     |
| `workcenter_id`   | Many2one  | `integer`            | NO       | FK  | `mrp_workcenter`                  | ⭐ Work center phát sinh block thời gian này                                                                                                                                          |
| `workorder_id`    | Many2one  | `integer`            | YES      | FK  | `mrp_workorder`                   | ⭐ Work order liên quan (NULL nếu downtime không gắn work order cụ thể)                                                                                                              |
| `loss_id`         | Many2one  | `integer`            | NO       | FK  | `mrp_workcenter_productivity_loss` | ⭐ Loại thời gian — xem bảng loss bên dưới                                                                                                                                            |
| `loss_type`       | Char      | `varchar`            | YES      | —   | —                                 | Related từ `loss_id.loss_type` — `productive`\|`availability`\|`performance`\|`quality`, lưu lại để query nhanh không cần join                                                       |
| `date_start`      | Datetime  | `timestamp`          | NO       | —   | —                                 | Bắt đầu block                                                                                                                                                                          |
| `date_end`        | Datetime  | `timestamp`          | YES      | —   | —                                 | Kết thúc block (NULL = đang diễn ra)                                                                                                                                                  |
| `duration`        | Float     | `double precision`   | YES      | —   | —                                 | Số phút của block                                                                                                                                                                      |
| `user_id`         | Many2one  | `integer`            | YES      | FK  | `res_users`                       | Người ghi nhận block                                                                                                                                                                  |
| `company_id`      | Many2one  | `integer`            | NO       | FK  | `res_company`                     | Công ty                                                                                                                                                                                |

> Mỗi work order có đúng 1 block `productive` (= khoảng `date_start`→`date_finished` thật của work order). Thêm vào đó: ~10% work order có 1 block `availability` chèn TRƯỚC (downtime — Material Availability / Equipment Failure / Setup and Adjustments, 15-90 phút), ~4% có 1 block `quality` chèn trước (Process Defect / Reduced Yield, 10-40 phút). `performance` loss không tách thành block riêng — đã phản ánh trực tiếp qua tỉ lệ `duration`/`duration_expected` ở `mrp_workorder`.

### `mrp_workcenter_productivity_loss` &nbsp;·&nbsp; `mrp.workcenter.productivity.loss`

> Danh mục 7 loại loss cố định (base data Odoo, không do generator sinh ra) — mỗi dòng `mrp_workcenter_productivity` trỏ về 1 trong 7 loại này

| `loss_type`    | `name`                      |
| -------------- | ---------------------------- |
| `availability` | Material Availability         |
| `availability` | Equipment Failure              |
| `availability` | Setup and Adjustments          |
| `performance`  | Reduced Speed                  |
| `quality`      | Process Defect                 |
| `quality`      | Reduced Yield                  |
| `productive`   | Fully Productive Time          |

### `stock_scrap` &nbsp;·&nbsp; `stock.scrap`

> Phế phẩm thật — nguồn dữ liệu cho Quality = (qty_produced − scrap_qty)/qty_produced trong OEE. ⚠️ Tên bảng thật là `stock_scrap` (model `stock.scrap`), KHÔNG phải `mrp_scrap` (bảng đó không tồn tại trong Odoo 18)

| Cột              | Odoo Type | DB Type     | Nullable | Key | FK Trỏ về         | Mô tả                                                                                                                                                                                |
| ----------------- | --------- | ----------- | -------- | --- | ------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `id`              | Integer   | `integer`   | NO       | PK  | —                  | Định danh tự tăng                                                                                                                                                                              |
| `name`            | Char      | `varchar`   | NO       | UQ  | —                  | Số phiếu tự sinh (ir.sequence)                                                                                                                                                                 |
| `product_id`      | Many2one  | `integer`   | NO       | FK  | `product_product`  | ⭐ Sản phẩm bị scrap                                                                                                                                                                            |
| `production_id`   | Many2one  | `integer`   | YES      | FK  | `mrp_production`   | ⭐ MO phát sinh phế phẩm này                                                                                                                                                                    |
| `workorder_id`    | Many2one  | `integer`   | YES      | FK  | `mrp_workorder`     | ⭐ Work order cụ thể — dùng để nối với block `quality` trong `mrp_workcenter_productivity` (cùng work order)                                                                                    |
| `scrap_qty`       | Float     | `float8`    | NO       | —   | —                  | ⭐ Số lượng phế phẩm — Generator v3 (Phase 4c) set = 10–35% `qty_produced` của work order đó                                                                                                    |
| `location_id`     | Many2one  | `integer`   | NO       | FK  | `stock_location`    | Nguồn hàng bị lấy ra để scrap — Odoo tự compute (`_compute_location_id`)                                                                                                                        |
| `scrap_location_id` | Many2one| `integer`   | NO       | FK  | `stock_location`    | Kho ảo chứa phế phẩm — Odoo tự compute (`_compute_scrap_location_id`)                                                                                                                           |
| `state`           | Selection | `varchar`   | YES      | —   | —                  | draft\|done                                                                                                                                                                                     |
| `date_done`       | Datetime  | `timestamp` | YES      | —   | —                  | ⚠️ Bị `action_validate()` ghi đè thành `now()` — Generator v3 restore lại về `date_finished` của work order sau khi validate (cùng pattern "planned vs actual" dùng xuyên suốt dự án)          |
| `origin`          | Char      | `varchar`   | YES      | —   | —                  | Tên MO nguồn (truy vết)                                                                                                                                                                          |

> Generator v3 chỉ tạo scrap cho work order đã có block `quality` trong `mrp_workcenter_productivity` (~4% work order) — không phải mọi work order đều có nguy cơ scrap. Defect rate tổng công ty thực đo được ~0.96% (dưới target <1.5%).

---

## Tầng 8 — External Marketing Data (ngoài Odoo · Lớp 3, PHẦN 4 master-plan)

> Generator tạo 4 file CSV ngoài Odoo để mô phỏng multi-source: campaign master, ads daily, email và A/B. `fact_marketing_funnel` được dbt tổng hợp từ Ads, CRM, linked Sales và Customer Acquisition, không có CSV staging riêng. Customer acquisition được tính trực tiếp từ `fact_sales`, `dim_customer` và `fact_ad_spend`, không dùng CSV riêng. `campaign_id` trong 4 raw source đọc từ `utm_campaign` thật và được audit trước khi ingest.
>
> ⚠️ **Hai loại ROAS KHÔNG được nhầm lẫn với nhau:**
> 1. **ROAS nội bộ CSV** (cột `roas` trong `ad_performance_daily.csv`/`email_campaigns.csv`/`ab_test_results.csv`) — synthetic, tính từ `revenue_usd` mô phỏng theo `roas_target` từng kênh (google_search 3.8x, email 9.5x...) + jitter ±12%+mùa vụ. Chỉ dùng để CTR/CPC trông thực tế trong nội bộ file, KHÔNG phản ánh doanh thu ERP thật.
> 2. **ROAS cross-source thật** — join `total_budget_usd` (`marketing_campaigns_master.csv`) với doanh thu THẬT attributed qua `campaign_id` trong `sale_order`/`account_move` (Tầng 7). Đây là con số dùng để đối chiếu target FRD-02 (3.0x) — đã audit ra **tổng ~3.3–3.4x**, thấp nhất là 3 campaign `year-end-promo` (~1.2x), cao nhất là `email-newsletter` (~150–190x). Xem ghi chú PHẦN 4 trong `master-plan-superstore-erp-v2.md`.
>
> `avg_daily_budget` mỗi kênh (trong script, không phải cột CSV) đã hiệu chỉnh **×36** so với bản gốc để ROAS cross-source (#2) về đúng thang thực tế — xem comment `CHANNELS` trong generator.

### `marketing_campaigns_master.csv`

> Campaign metadata — 16 dòng = 16 `utm_campaign.id` thật (chỉ những campaign thật sự tồn tại trong Odoo DB, không phải đủ 8 template × 4 năm)

| Cột | Mô tả |
| --- | --- |
| `campaign_id` | ⭐ Khớp 1:1 `utm_campaign.id` — khóa join sang Tầng 7 |
| `campaign_name`, `objective`, `target_segment`, `product_focus`, `channels` | Metadata mô tả chiến dịch |
| `start_date`, `end_date`, `duration_days` | Thời gian chạy — Black Friday ngắn (11 ngày) vs year-end-promo dài (61 ngày) |
| `total_budget_usd` | ⭐ Tổng ngân sách cả chiến dịch = Σ(`avg_daily_budget` kênh × `budget_multiplier` × `duration_days`), đã tính ×36 |
| `budget_multiplier` | Hệ số nhân ngân sách theo campaign (0.3–2.0) — không tỷ lệ với ROAS cross-source thật (xem ghi chú Tầng 8 ở trên) |
| `is_underperformer`, `notes` | ⚠️ Cờ đánh dấu campaign bị CỐ Ý gán 1 kênh ROAS thấp (`BAD_CAMPAIGN_SLOTS` trong script) — khác với hiệu ứng year-end-promo ROAS thấp (đó là tự nhiên, không đánh dấu cờ này) |

### `ad_performance_daily.csv`

> File ROAS chính — 1 dòng/ngày/campaign/kênh. Cột: `date, campaign_id, campaign_name, channel, channel_label, channel_type, year, month, quarter, spend_usd, impressions, reach, clicks, ctr, cpc_usd, cpm_usd, frequency, leads, conversions, conv_rate, cpa_usd, cpl_usd, revenue_usd, roas, lead_quality_score, is_underperformer`

> `spend_usd` = ngân sách ngày đã ×36 + jitter + mùa vụ (`seasonal_multiplier`). `revenue_usd`/`roas` = **synthetic nội bộ** (loại #1 ở trên), không phải doanh thu ERP thật — muốn ROAS thật phải join `campaign_id` sang `sale_order`/`account_move`.

### `email_campaigns.csv`

> Email marketing theo từng đợt gửi (không phải `mailing.mailing` thật của Odoo). `campaign_id` trỏ tới `utm_campaign.id`; `sent` tách khỏi list size. Cột: `email_id, campaign_id, year, send_date, month, quarter, email_type, goal, list_name, subject_line, sent, list_size, delivered, bounced_total, hard_bounce, soft_bounce, deliverability, opens, unique_opens, open_rate, clicks, unique_clicks, ctr, ctor, unsubscribes, unsubscribe_rate, spam_reports, conversions, revenue_usd, cost_usd, roas, revenue_per_email`

### `ab_test_results.csv`

> Creative A/B test theo kênh — `variant_id` là grain, `campaign_id` trỏ tới Odoo. Test không có campaign cùng year/channel bị loại thay vì gắn ID giả. Cột: `test_id, variant_id, campaign_id, year, test_name, channel, start_date, end_date, duration_days, variant_name, is_winner, budget_usd, impressions, clicks, ctr, conversions, conv_rate, revenue_usd, roas, cpa_usd, insight`

---
