# Sơ đồ Phễu Chuyển Đổi End-to-End

Phễu mô tả hành trình từ lúc khách hàng nhìn thấy nội dung marketing, để lại thông tin, mua hàng, cho đến khi quay lại mua lần tiếp theo.

```text
Quảng cáo / Nội dung
        │
        ▼
1. Exposure ──► 2. Engagement ──► 3. Lead
                                         │
                                         ▼
                                4. Opportunity
                                  ├── Lost
                                  └── Quotation / Order
                                            │
                                            ▼
                                         5. Won
                                            │
                                            ▼
                              6. Fulfillment & Retention
```

## Tổng quan 6 giai đoạn

| Giai đoạn                  | Khách hàng làm gì?                         | Hệ thống chính                       | Dữ liệu / entity chính                                       | KPI chính                                   |
| -------------------------- | ------------------------------------------ | ------------------------------------ | ------------------------------------------------------------ | ------------------------------------------- |
| 1. Exposure                | Nhìn thấy quảng cáo hoặc nội dung          | Facebook Ads, Google Ads, TikTok Ads | Dữ liệu quảng cáo bên ngoài Odoo                             | Impressions, Reach                          |
| 2. Engagement              | Click, vào website hoặc landing page       | GA4, Web Tracking                    | Session, click và web event                                  | Clicks, Sessions, CTR                       |
| 3. Lead Generation         | Để lại thông tin liên hệ                   | Odoo CRM                             | `crm_lead` với `type = 'lead'`                               | Leads, CPL                                  |
| 4. Qualification           | Được Sales đánh giá và chuyển thành cơ hội | Odoo CRM, Odoo Sales                 | `crm_lead` với `type = 'opportunity'`                        | Opportunities, Lead-to-Opportunity Rate     |
| 5. Conversion / Won        | Đồng ý mua hàng                            | Odoo CRM, Sales, Invoicing           | `crm_lead`, `sale_order`, `account_move`                     | Won Deals, Win Rate, Actual Revenue         |
| 6. Fulfillment & Retention | Nhận hàng và có thể mua lại                | Inventory, Accounting, Sales, MRP    | `stock_picking`, `stock_move`, `account_move`, `res_partner` | Delivery Rate, AOV, CLV, Repeat Rate, Churn |

## Chi tiết từng giai đoạn

### 1. Exposure / Impression — Hiển thị

Quảng cáo hoặc nội dung xuất hiện trước người dùng trên Facebook, Google, TikTok hoặc các kênh số khác.

- **Hệ thống:** nền tảng quảng cáo và công cụ Digital Marketing.
- **Dữ liệu chính:** campaign, ad, channel, spend, impressions và reach.
- **KPI:** `Impressions`, `Reach`.

> Odoo không tự lưu lượt hiển thị của các nền tảng quảng cáo. Dữ liệu này phải được lấy từ API hoặc file của từng nền tảng.

### 2. Engagement / Click — Tương tác

Người dùng click quảng cáo, truy cập website, landing page, quét QR hoặc xem thêm thông tin sản phẩm.

- **Hệ thống:** GA4, Web Tracking, website và landing page.
- **Dữ liệu chính:** click, session, page view, landing page và UTM.
- **KPI:** `Clicks`, `Sessions`, `CTR`.

### 3. Lead Generation — Thu thập đầu mối

Người dùng để lại họ tên, điện thoại, email hoặc nhu cầu thông qua form, chat, hotline, email hay landing page. Từ đây dữ liệu được đưa vào Odoo CRM.

```text
crm_lead
  type = 'lead'
  stage_id -> crm_stage (thường là New)
```

Các trường attribution quan trọng:

- `campaign_id` → `utm_campaign`
- `source_id` → `utm_source`
- `medium_id` → `utm_medium`

**KPI:** Lead Count và CPL — Cost per Lead.

### 4. Qualification & Opportunity — Sàng lọc cơ hội

Sales tiếp nhận Lead, xác minh nhu cầu và chuyển Lead đủ điều kiện thành Opportunity. Đây vẫn là cùng một record trong `crm_lead`; Odoo giữ nguyên `id` và cập nhật:

```text
type = 'opportunity'
date_conversion = thời điểm chuyển đổi
partner_id = khách hàng được tạo hoặc liên kết, nếu có
user_id = salesperson phụ trách
team_id = sales team
```

Opportunity thường đi qua pipeline:

```text
New ──► Qualified ──► Proposition ──► Won / Lost
```

Các trường nghiệp vụ thường được bổ sung gồm `expected_revenue`, `date_deadline`, `partner_id`, `user_id` và `team_id`.

> `Quotation Sent` không phải stage CRM mặc định của Odoo 18. Quotation là một `sale_order` ở trạng thái báo giá; doanh nghiệp có thể tạo thêm CRM stage tên `Quotation Sent` nếu muốn theo dõi theo cách này.

**KPI:** Opportunity Count và Lead-to-Opportunity Conversion Rate.

### 5. Conversion / Won — Chốt đơn

Khi khách hàng đồng ý mua, Opportunity được đánh dấu Won và nghiệp vụ bán hàng tiếp tục trên Odoo Sales.

```text
crm_lead.id
  └── sale_order.opportunity_id

res_partner.id
  ├── crm_lead.partner_id
  └── sale_order.partner_id
        └── sale_order_line.order_id
```

Các thay đổi chính khi Won:

- `crm_lead.stage_id` trỏ đến `crm_stage.is_won = true`.
- `probability = 100`.
- `date_closed` được ghi nhận.
- Quotation hoặc Sales Order có thể đã được tạo trước khi Opportunity được đánh dấu Won.

**KPI:** Won Deals, Win Rate và Actual Revenue.

> `expected_revenue` là doanh thu kỳ vọng. Actual Revenue nên lấy từ hóa đơn khách hàng đã post trong `account_move`, sau khi trừ credit note/refund; không lấy trực tiếp từ `crm_lead.expected_revenue`.

### 6. Fulfillment & Retention — Giao hàng và mua lại

Sau khi xác nhận đơn, hệ thống xử lý tồn kho, giao hàng, hóa đơn, thanh toán và các lần mua tiếp theo.

```text
sale_order
  └── stock_picking.sale_id
        └── stock_move.picking_id

sale_order_line
  └── sale_order_line_invoice_rel
        └── account_move_line
              └── account_move

res_partner
  └── nhiều sale_order theo thời gian
        └── Repeat Purchase / CLV / Churn analytics
```

Nếu sản phẩm cần sản xuất, dòng bán hàng còn có thể phát sinh Manufacturing Order trước khi giao hàng.

**KPI:** Delivery Success Rate, AOV, CLV, Repeat Purchase Rate và Churn Rate.

> Retention, Repeat Purchase, CLV và Churn là chỉ số phân tích được suy ra từ lịch sử đơn hàng/hóa đơn theo `partner_id`; chúng không phải trạng thái được Odoo lưu sẵn trong một cột duy nhất.

## Dòng chảy dữ liệu giữa các hệ thống

```text
Facebook / Google / TikTok Ads
          │ impressions, clicks, spend, campaign key
          ▼
GA4 / Website / Landing Page
          │ sessions, form submission, UTM
          ▼
Odoo CRM
crm_lead + utm_campaign/source/medium
          │ qualify / convert
          ▼
Opportunity
          ├── Lost
          └── Quotation / sale_order
                         │
                         ├── stock_picking ──► stock_move ──► Delivery
                         │
                         └── account_move ──► Revenue / Payment
                                              │
                                              ▼
                                Customer history by partner_id
                                              │
                                              ▼
                                  Retention / Repeat Purchase
```

Để nối dữ liệu external marketing với Odoo, cần chuẩn hóa campaign key và UTM giữa các hệ thống. `utm_campaign`, `utm_source` và `utm_medium` trong Odoo phục vụ attribution, nhưng không thay thế dữ liệu impressions, clicks hoặc ad spend từ nền tảng quảng cáo.

## Công thức KPI cốt lõi

# KPI Framework theo Phễu Chuyển Đổi

| Giai đoạn / Phân loại                | KPI                               | Công thức đề xuất                                                                              |
| ------------------------------------ | --------------------------------- | ---------------------------------------------------------------------------------------------- |
| Giai đoạn 1: Exposure                | Impressions / Reach               | Lấy trực tiếp từ báo cáo tổng hợp của các nền tảng Ads / GA4                                   |
| Giai đoạn 2: Engagement              | CTR (Click-Through Rate)          | `Clicks / Impressions × 100`                                                                   |
|                                      | CPC (Cost Per Click)              | `Marketing Spend / Clicks`                                                                     |
| Giai đoạn 3: Lead Generation         | Leads Count                       | Đếm tổng số bản ghi tạo mới trong bảng `crm.lead`                                              |
|                                      | CPL (Cost Per Lead)               | `Marketing Spend / Leads`                                                                      |
| Giai đoạn 4: Qualification           | Lead-to-Opportunity Rate          | `Leads converted to Opportunity / Leads created in the same cohort × 100`                      |
| Giai đoạn 5: Conversion & Revenue    | CR (Conversion Rate tổng thể)     | `Total Won Orders (hoặc Won Opportunities) / Total Impressions (hoặc Clicks) × 100`            |
|                                      | CPS (Cost Per Sale / Acquisition) | `Marketing Spend / Won Opportunities (hoặc Total Won Orders)`                                  |
|                                      | Win Rate                          | `Won Opportunities / (Won + Lost Opportunities) × 100`                                         |
|                                      | Actual Revenue                    | Hóa đơn khách hàng đã post từ `account.move`, trừ credit note / refund đã post                 |
|                                      | ROAS (Return On Ad Spend)         | `Actual Revenue / Marketing Spend`                                                             |
|                                      | AOV (Average Order Value)         | `Actual Revenue / Completed Orders`                                                            |
| Giai đoạn 6: Fulfillment & Retention | Delivery Success Rate             | `Completed Outbound Deliveries / Non-cancelled Outbound Deliveries × 100`                      |
|                                      | Repeat Purchase Rate              | `Customers with at least 2 completed orders / Customers with at least 1 completed order × 100` |
|                                      | Historical CLV                    | Tổng `Actual Revenue` hoặc `Gross Margin` theo `partner_id` trong khoảng phân tích             |
|                                      | Churn Rate                        | `Customers exceeding inactivity threshold / Monitored customer base × 100`                     |
| Chỉ số tài chính tổng quát           | ROA (Return On Assets)            | `Net Income / Total Assets × 100`                                                              |

## Ghi chú

- `Marketing Spend` lấy từ các nền tảng quảng cáo như Facebook Ads, Google Ads, TikTok Ads.
- `crm.lead` dùng cho Lead và Opportunity trong Odoo CRM.
- `account.move` nên được dùng làm nguồn chính cho `Actual Revenue` nếu mục tiêu là doanh thu kế toán đã ghi nhận.
- `Completed Orders` cần được định nghĩa rõ theo business rule, ví dụ Sales Order đã hoàn tất hoặc đơn có delivery/invoice hoàn tất.
- `Churn Rate` cần định nghĩa rõ `inactivity threshold`, ví dụ khách hàng không mua trong 90 ngày, 180 ngày hoặc khoảng thời gian khác.
- `ROA` là KPI cấp doanh nghiệp, không thuộc trực tiếp marketing funnel nhưng có thể dùng trong lớp Financial Performance.
