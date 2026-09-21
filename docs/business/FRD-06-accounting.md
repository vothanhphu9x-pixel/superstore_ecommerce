# FRD-06 — YÊU CẦU CHỨC NĂNG: KẾ TOÁN (ACCOUNTING)
## Superstore ERP · Phòng Accounting · Phiên bản 1.0 · 2026

---

## 1. Tổng quan phòng ban

**Sứ mệnh:** Ghi nhận chính xác mọi giao dịch tài chính theo nguyên tắc kế toán kép (double-entry), quản lý công nợ phải thu và phải trả, đóng sổ đúng hạn và cung cấp báo cáo tài chính chính xác cho ban lãnh đạo.

**Nhân sự:**
- 1 Chief Accountant (Robert Hayes) — giám sát sổ sách, đóng sổ tháng, báo cáo CFO
- 1 AR Specialist (Accounts Receivable) — quản lý công nợ khách hàng, nhắc nợ, thu tiền
- 1 AP Specialist (Accounts Payable) — quản lý công nợ NCC, 3-way match, thanh toán

**Nguyên tắc kế toán áp dụng:** US GAAP (Generally Accepted Accounting Principles) mức cơ bản — accrual basis (ghi nhận khi phát sinh, không phải khi thu/chi tiền).

**Nguyên tắc Double-Entry (Kế toán kép):** Mỗi bút toán phải có tổng Nợ (Debit) = tổng Có (Credit). Không có ngoại lệ.

**KPI phòng:**

| KPI | Mục tiêu | Chu kỳ |
|---|---|---|
| DSO — Days Sales Outstanding (số ngày thu tiền bình quân) | ≤ 38 ngày | Tháng |
| Tỷ lệ hóa đơn quá hạn > 30 ngày / tổng AR | ≤ 10% | Tháng |
| DPO — Days Payable Outstanding (số ngày trả NCC bình quân) | 28–35 ngày (đúng Net-30) | Tháng |
| Đóng sổ tháng | Trước ngày 5 tháng sau | Tháng |
| 3-way match rate | 100% | Tháng |

---

## 2. Hệ thống tài khoản (Chart of Accounts — COA)

| Nhóm | Mã TK | Tên tài khoản | Loại |
|---|---|---|---|
| Tài sản | 1010 | Cash and Cash Equivalents | Asset |
| Tài sản | 1200 | Accounts Receivable (Phải thu KH) | Asset |
| Tài sản | 1300 | Inventory — Finished Goods | Asset |
| Tài sản | 1310 | Inventory — Raw Materials | Asset |
| Nợ phải trả | 2000 | Accounts Payable (Phải trả NCC) | Liability |
| Nợ phải trả | 2100 | Accrued Liabilities | Liability |
| Vốn chủ | 3000 | Owner's Equity | Equity |
| Doanh thu | 4000 | Sales Revenue — Furniture | Income |
| Doanh thu | 4010 | Sales Revenue — Technology | Income |
| Doanh thu | 4020 | Sales Revenue — Office Supplies | Income |
| Chi phí | 5000 | COGS — Furniture (Cost of Goods Sold) | COGS |
| Chi phí | 5010 | COGS — Technology | COGS |
| Chi phí | 5020 | COGS — Office Supplies | COGS |
| Chi phí | 6000 | Payroll Expense | Expense |
| Chi phí | 6100 | Rent & Utilities | Expense |
| Chi phí | 6200 | Shipping & Freight | Expense |
| Chi phí | 6300 | Marketing & Advertising | Expense |
| Chi phí | 6900 | Other Operating Expenses | Expense |

---

## 3. Sơ đồ luồng nghiệp vụ

```mermaid
flowchart TD
    subgraph AR["CÔNG NỢ PHẢI THU - AR"]
        A([Hàng đã giao → SO invoice_status = to invoice]) --> B[AR Specialist tạo\nCustomer Invoice Draft]
        B --> C[Chief Accountant review\nPost Invoice]
        C --> D[Bút toán: Nợ 1200 AR / Có 4000 Revenue]
        D --> E{B2C hay B2B?}
        E -->|B2C — thanh toán ngay| F[Register Payment ngay]
        E -->|B2B — Net-30| G[Ghi nhận công nợ\ntheo dõi đến hạn]
        G --> H{Đến hạn chưa?}
        H -->|Chưa| G
        H -->|Đến hạn| I[AR gửi nhắc nợ tự động\nhoặc gọi điện]
        I --> J[Khách thanh toán]
        F --> K[Register Payment\nBút toán: Nợ 1010 Cash / Có 1200 AR]
        J --> K
        K --> L([amount_residual = 0 ✓])
    end

    subgraph AP["CÔNG NỢ PHẢI TRẢ - AP"]
        M([3-way match OK từ Purchasing]) --> N[AP tạo Vendor Bill từ PO]
        N --> O[Post Vendor Bill\nBút toán: Nợ 5000 COGS / Có 2000 AP]
        O --> P{Đến hạn thanh toán?}
        P -->|Chưa (Net-30)| Q[Chờ đến hạn]
        Q --> P
        P -->|Đến hạn| R{Early payment\ndiscount có lợi?}
        R -->|Có 2/10 Net30| S[Thanh toán sớm,\nhưởng 2% discount]
        R -->|Không| T[Thanh toán đúng hạn\nNet-30]
        S --> U[Register Payment\nBút toán: Nợ 2000 AP / Có 1010 Cash]
        T --> U
    end
```

---

## 4. Ví dụ bút toán mẫu (Journal Entries)

**Bút toán 1 — Bán hàng B2B, chưa thu tiền:**
```
Dr 1200 Accounts Receivable    $5,500    (khách nợ ta)
   Cr 4000 Sales Revenue           $5,000    (doanh thu)
   Cr 2100 Sales Tax Payable          $500    (thuế bán hàng thu hộ)
```

**Bút toán 2 — Ghi nhận COGS khi xuất kho:**
```
Dr 5000 COGS — Technology      $3,200
   Cr 1300 Inventory — Finished Goods    $3,200
```

**Bút toán 3 — Thu tiền từ khách B2B:**
```
Dr 1010 Cash                    $5,500
   Cr 1200 Accounts Receivable      $5,500
```

**Bút toán 4 — Nhận hóa đơn NCC:**
```
Dr 1310 Inventory — Raw Materials   $8,000
Dr 5010 COGS — Technology          $12,000
   Cr 2000 Accounts Payable            $20,000
```

**Bút toán 5 — Trả tiền NCC:**
```
Dr 2000 Accounts Payable        $20,000
   Cr 1010 Cash                     $20,000
```

---

## 5. SOP — Quy trình chuẩn từng bước

### 5.1. Accounts Receivable (AR)

| Bước | Ai | Hành động | Trên Odoo | Bảng DB ghi | Kết quả |
|---|---|---|---|---|---|
| 1 | AR Specialist | Tạo hóa đơn từ SO | Accounting → Customers → Invoices → Create from SO | `account_move` INSERT (out_invoice, draft) | HĐ draft |
| 2 | Chief Accountant | Review và ghi sổ | Invoice → Confirm (Post) | `account_move.state` = `posted`; `account_move_line` INSERT | Bút toán Nợ/Có |
| 3 | Hệ thống | Theo dõi công nợ đến hạn | AR Aging report tự động | — | Báo cáo aging |
| 4 | AR Specialist | Gửi nhắc nợ | Accounting → Follow-up → Send Reminder | `mail_message` | Email nhắc khách |
| 5 | AR Specialist | Ghi nhận thanh toán | Invoice → Register Payment | `account_payment`; reconcile với `account_move_line` | `amount_residual` → 0 |

### 5.2. Accounts Payable (AP)

| Bước | Ai | Hành động | Trên Odoo | Bảng DB ghi | Kết quả |
|---|---|---|---|---|---|
| 1 | AP Specialist | Tạo vendor bill từ PO (sau 3-way match OK) | Purchase → Bills → Create from PO | `account_move` INSERT (in_invoice, draft) | Vendor bill draft |
| 2 | Chief Accountant | Review và ghi sổ | Bill → Confirm (Post) | `account_move_line` INSERT | Bút toán Nợ COGS / Có AP |
| 3 | AP Specialist | Lên lịch thanh toán theo due date | Accounting → Bills → filter Due date | — | Payment schedule |
| 4 | AP Specialist | Thanh toán khi đến hạn | Bill → Register Payment → Bank journal | `account_payment` | `amount_residual` → 0; NCC tất toán |

### 5.3. Đóng sổ tháng (Month-End Closing)

| Bước | Ai | Thời hạn | Hành động |
|---|---|---|---|
| 1 | AR Specialist | Ngày 1–2 tháng sau | Đảm bảo tất cả hóa đơn tháng đã post |
| 2 | AP Specialist | Ngày 1–2 | Đảm bảo tất cả vendor bills tháng đã post |
| 3 | Production Planner | Ngày 2 | Xác nhận MO tháng đã close, giá thành đã ghi |
| 4 | Chief Accountant | Ngày 3–4 | Review P&L draft, kiểm tra bất thường |
| 5 | Chief Accountant | Ngày 4–5 | Lock accounting period — không ai ghi sổ được vào tháng đã đóng |
| 6 | Chief Accountant | Ngày 5 | Gửi báo cáo P&L, Balance Sheet cho CFO |
| 7 | CFO | Ngày 7 | Review, approve, trình CEO |

---

## 6. Quy tắc nghiệp vụ

| Mã | Quy tắc | Chi tiết |
|---|---|---|
| BR-ACC-01 | Double-entry bắt buộc | Mọi account.move phải có Σdebit = Σcredit trước khi Post |
| BR-ACC-02 | Không sửa sau khi Post | Hóa đơn đã Post không được xóa/sửa — chỉ tạo Credit Note nếu cần điều chỉnh |
| BR-ACC-03 | Accrual basis | Doanh thu ghi nhận khi hàng giao (invoice date), không phải khi thu tiền |
| BR-ACC-04 | Credit hold tự động | AR Aging alert: khách có HĐ > 30 ngày quá hạn → gửi cảnh báo Sales để credit hold |
| BR-ACC-05 | Early payment | Tận dụng 2/10 Net 30 từ NCC khi cash flow tốt (tiết kiệm 2% trên AP) |
| BR-ACC-06 | Khóa kỳ | Sau ngày 5 tháng sau → lock period; bút toán bổ sung (adjustment) phải có Chief Accountant duyệt |
| BR-ACC-07 | 3-way match | Vendor bill chỉ Post sau khi Purchasing xác nhận 3-way match OK |

---

## 7. Handoff Matrix

| Nhận từ | Giao cho | Trigger | Dữ liệu chuyển |
|---|---|---|---|
| Sales | Accounting | SO `invoice_status` = `to invoice` | `sale_order` → tạo `account_move` |
| Purchasing (3-way match OK) | Accounting | Vendor bill approved for payment | `purchase_order` → tạo `account_move` (in_invoice) |
| Manufacturing | Accounting | MO done → giá thành ghi nhận | `mrp_production` cost → journal entry |
| Accounting | Sales | HĐ quá hạn → credit hold | Thông báo AR aging report |
| Accounting | Management | Month-end close | P&L, Balance Sheet, Cash Flow báo cáo |

---

## 8. Exception Flows

**Ngoại lệ 1 — Khách không trả đúng hạn:**
DSO vượt 38 ngày → AR gửi nhắc tự động (email) → Nếu sau 7 ngày chưa trả: Sales gọi điện → Nếu sau 15 ngày: credit hold, đơn mới yêu cầu prepay → Nếu sau 60 ngày: CFO xem xét chuyển bad debt provision.

**Ngoại lệ 2 — Hóa đơn đã Post bị sai:**
Phát hiện sai sau Post → Không được xóa → Tạo Credit Note (hóa đơn đảo ngược) để hủy → Tạo lại hóa đơn đúng → Ghi chú lý do trên chatter.

**Ngoại lệ 3 — Vendor bill không khớp PO:**
AP phát hiện price/qty khác PO → Không Post bill → Gửi lại Purchasing điều tra → Purchasing liên hệ NCC → NCC gửi credit note hoặc corrected invoice.

---

## 9. Data Footprint

| Bảng DB | Vai trò | Loại |
|---|---|---|
| `account_account` | Chart of Accounts | Master |
| `account_journal` | Sổ nhật ký (Sales/Purchase/Bank/Cash) | Master |
| `account_move` | Hóa đơn & bút toán (header) | Transaction |
| `account_move_line` | Dòng Nợ/Có (double-entry) | Transaction → **fact_journal_entries** |
| `account_payment` | Thanh toán thu/chi | Transaction |
| `account_partial_reconcile` | Phân bổ/đối soát payment với hóa đơn | Transaction → **fact_payment_allocation** |

**Phân tích downstream:**
- `fact_journal_entries` → `mart_pnl_monthly`
- `fact_customer_invoice` → daily snapshot `mart_ar_aging`
- `fact_payment_allocation` → `mart_dso_monthly`
- P&L, AR Aging và DSO là phạm vi analytics hiện tại; Balance Sheet, Cash Flow và DPO cần model riêng trước khi công bố KPI.
