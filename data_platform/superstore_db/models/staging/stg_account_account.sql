-- 1:1 account.account (CoA). GRAIN: 1 CDC event (append-only). SOURCE: bronze CDC topic odoo.account.account
{{ config(
    materialized='incremental',
    incremental_strategy='append',
    on_schema_change='sync_all_columns'
) }}
select
    raw_data:id::number                    as account_id,
    -- Postgres thật: cột là 'code_store' (jsonb company-dependent, key=company_id — verify
    -- \d account_account, comment cũ trong file ghi ngược "field thật là code" là SAI).
    -- 'name' cũng jsonb (i18n, translate=True) — cùng pattern stg_product_template.
    {{ deb_jsonb_get('raw_data:code_store', '"1"') }}::string as code,
    {{ deb_i18n('raw_data:name') }}        as name,
    raw_data:account_type::string          as account_type,
    -- ⚠️ KHÔNG đọc 'internal_group' ở đây. Postgres thật KHÔNG có cột này (verify:
    -- information_schema.columns của account_account chỉ có 13 cột, không có internal_group) —
    -- từ Odoo 17 nó là field computed NON-STORED, sinh ra bằng account_type.split('_')[0], nên
    -- Debezium không có gì để bắt. Code cũ đọc `raw_data:internal_group` và nhận NULL cho cả
    -- 51 tài khoản, kéo theo `dim_account.report_line` xếp toàn bộ tài khoản bảng cân đối vào
    -- 'Other' và `mart_pnl_monthly` tính SAI DẤU doanh thu (ra âm 59,8 tỷ).
    -- Cùng họ bug với `code` vs `code_store` ở ngay trên: field trông có vẻ tồn tại vì Odoo
    -- hiển thị nó trên UI, nhưng không nằm trong bảng.
    -- Suy ra ở `dim_account` (đúng chỗ cho phân loại nghiệp vụ), không suy ở đây.
    raw_data:cdc_status::string            as cdc_status,
    raw_data:is_deleted::boolean           as is_deleted,
    raw_data:_cdc_ts_ms::number            as _cdc_ts_ms,
    raw_data:_cdc_lsn::number              as _cdc_lsn,
    raw_data:ingested_at::timestamp_ntz    as ingested_at
from {{ source('bronze', 'account_account') }}
{{ incremental_filter() }}
