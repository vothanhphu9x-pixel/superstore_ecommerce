-- GRAIN: 1 tài khoản kế toán (CoA) hiện hành. SOURCE: stg_account_account (không silver — dùng
-- staging trực tiếp, domain-de.dbml FINANCE_GENERAL_LEDGER). Domain-specific dim (KHÔNG conformed)
-- — dùng bởi fact_journal_entries, mart_pnl_monthly, mart_balance_sheet_monthly, mart_cashflow_monthly.
-- DERIVED: internal_group (suy từ account_type — xem note bên dưới), report_line, statement,
--          bs_section, is_debit_normal
-- TEST: unique(account_sk), unique(account_code), not_null(report_line), not_null(internal_group)
{{ config(materialized='table') }}

with account_latest as (
    select *
    from {{ ref('stg_account_account') }}
    qualify row_number() over (partition by account_id order by _cdc_ts_ms desc, _cdc_lsn desc) = 1
),

classified as (
    select
        code,
        name,
        account_type,
        is_deleted,
        -- ⚠️ internal_group SUY RA, không đọc từ nguồn. Postgres không có cột này (Odoo 17+ để
        -- computed non-stored) nên đọc thẳng ra NULL 100% — chính là bug đã làm P&L âm doanh thu.
        -- Công thức bám đúng Odoo (`_compute_internal_group`): lấy phần trước dấu gạch dưới đầu
        -- tiên của account_type. Riêng 'off_balance' phải giữ nguyên cả cụm, vì split ra sẽ thành
        -- 'off' — một giá trị không nằm trong selection của Odoo.
        case
            when account_type = 'off_balance' then 'off_balance'
            else split_part(account_type, '_', 1)
        end as internal_group
    from account_latest
)

select
    {{ dbt_utils.generate_surrogate_key(['code']) }} as account_sk,
    code                                as account_code,
    name                                as account_name,
    account_type,
    internal_group,

    -- Dòng báo cáo cho P&L (giữ tên cũ để mart_pnl_monthly và các template Text-to-SQL đang
    -- dùng không phải sửa theo).
    case
        when account_type in ('income', 'income_other')         then 'Revenue'
        when account_type = 'expense_direct_cost'               then 'COGS'
        when account_type in ('expense', 'expense_depreciation') then 'OpEx'
        when internal_group = 'asset'                            then 'Balance Sheet - Asset'
        when internal_group = 'liability'                        then 'Balance Sheet - Liability'
        when internal_group = 'equity'                           then 'Balance Sheet - Equity'
        else 'Other'
    end                                 as report_line,

    -- Tài khoản này thuộc báo cáo nào. Ba báo cáo tài chính chuẩn tách nhau ở đây thay vì để mỗi
    -- mart tự viết lại một bảng CASE — viết lại là cách chắc chắn nhất để hai báo cáo lệch nhau.
    case
        when internal_group in ('income', 'expense')             then 'income_statement'
        when internal_group in ('asset', 'liability', 'equity')  then 'balance_sheet'
        else 'off_balance'
    end                                 as statement,

    -- Khoản mục trên Bảng cân đối kế toán. Ngắn hạn / dài hạn tách được nhờ account_type của
    -- Odoo — đây là thứ cần để tính Current Ratio, và nó CÓ SẴN (ghi chú cũ trong
    -- docs/dashboard_by_role.md nói thiếu là sai, đã sửa).
    case
        when account_type in ('asset_receivable', 'asset_cash', 'asset_current', 'asset_prepayments')
            then 'Tài sản ngắn hạn'
        when account_type in ('asset_non_current', 'asset_fixed')
            then 'Tài sản dài hạn'
        when account_type in ('liability_payable', 'liability_credit_card', 'liability_current')
            then 'Nợ ngắn hạn'
        when account_type = 'liability_non_current'
            then 'Nợ dài hạn'
        when account_type in ('equity', 'equity_unaffected')
            then 'Vốn chủ sở hữu'
    end                                 as bs_section,

    -- Tài sản ngắn hạn có tính thanh khoản cao (loại hàng tồn kho và trả trước) — mẫu số của
    -- Quick Ratio. Odoo gộp cả tồn kho vào 'asset_current' nên không tách được tồn kho riêng
    -- bằng account_type; ở đây coi asset_current là KÉM thanh khoản để Quick Ratio thiên về
    -- thận trọng, thà báo động nhầm còn hơn bỏ sót rủi ro thanh khoản.
    account_type in ('asset_receivable', 'asset_cash')  as is_quick_asset,

    -- Tài khoản mang TIỀN (dùng cho báo cáo lưu chuyển tiền tệ).
    -- Gồm cả 'asset_current' là có chủ ý, không phải cẩu thả: dữ liệu Odoo ở đây chưa đối chiếu
    -- ngân hàng, nên tiền thật nằm ở hai tài khoản trung gian "Outstanding Receipts" (101403) và
    -- "Outstanding Payments" (101404) — cả hai đều là asset_current, còn hai tài khoản asset_cash
    -- thì KHÔNG có bút toán nào. Chỉ nhận asset_cash sẽ cho ra báo cáo lưu chuyển tiền tệ rỗng
    -- trong khi 22.216 dòng sổ ngân hàng vẫn đang chạy.
    -- ⚠️ Cờ này chỉ có nghĩa khi lọc trong sổ nhật ký loại bank/cash — ngoài phạm vi đó,
    -- 'asset_current' còn bao gồm hàng tồn kho và chi phí trả trước.
    account_type in ('asset_cash', 'asset_current', 'liability_credit_card') as is_cash_account,

    -- Dấu chuẩn của tài khoản: tài sản & chi phí ghi Nợ, nợ phải trả & vốn & doanh thu ghi Có.
    -- Đưa vào dim để mọi mart tính số dư bằng cùng một quy ước, không ai tự đoán dấu nữa.
    internal_group in ('asset', 'expense')              as is_debit_normal,

    (is_deleted = false)                as active,
    {{ pipeline_now() }}                as gold_refreshed_at
from classified
