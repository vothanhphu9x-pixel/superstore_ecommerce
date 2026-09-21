-- 1:1 account.move.line. GRAIN: 1 CDC event (append-only). SOURCE: bronze CDC topic odoo.account.move.line
-- Đi qua sil_journal_entries_enriched để theo dõi thay đổi của line/header/lookup và tạo
-- silver_updated_at trước khi fact_journal_entries temporal join dim_customer SCD2.
{{ config(
    materialized='incremental',
    incremental_strategy='append',
    on_schema_change='sync_all_columns'
) }}
select
    raw_data:id::number                    as account_move_line_id,
    raw_data:move_id::number               as move_id,
    raw_data:account_id::number            as account_id,
    raw_data:partner_id::number            as partner_id,
    raw_data:name::string                  as name,
    raw_data:debit::number(38, 6)          as debit,
    raw_data:credit::number(38, 6)         as credit,
    raw_data:balance::number(38, 6)        as balance,
    raw_data:amount_currency::number(38, 6) as amount_currency,
    raw_data:currency_id::number           as currency_id,
    {{ deb_date('raw_data:date_maturity') }} as date_maturity,
    raw_data:cdc_status::string            as cdc_status,
    raw_data:is_deleted::boolean           as is_deleted,
    raw_data:_cdc_ts_ms::number            as _cdc_ts_ms,
    raw_data:_cdc_lsn::number              as _cdc_lsn,
    raw_data:ingested_at::timestamp_ntz    as ingested_at
from {{ source('bronze', 'account_move_line') }}
{{ incremental_filter() }}
