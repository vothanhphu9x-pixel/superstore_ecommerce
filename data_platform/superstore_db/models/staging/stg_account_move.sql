-- 1:1 account.move. GRAIN: 1 CDC event (append-only). SOURCE: bronze CDC topic odoo.account.move
{{ config(
    materialized='incremental',
    incremental_strategy='append',
    on_schema_change='sync_all_columns'
) }}
select
    raw_data:id::number                    as move_id,
    raw_data:name::string                  as name,
    {{ deb_date('raw_data:date') }}        as date,
    {{ deb_date('raw_data:invoice_date') }} as invoice_date,
    {{ deb_date('raw_data:invoice_date_due') }} as invoice_date_due,
    {{ deb_date('raw_data:delivery_date') }} as delivery_date,
    raw_data:partner_id::number            as partner_id,
    raw_data:journal_id::number            as journal_id,
    raw_data:campaign_id::number           as campaign_id,
    raw_data:currency_id::number           as currency_id,
    raw_data:company_id::number            as company_id,
    raw_data:move_type::string             as move_type,
    raw_data:state::string                 as state,
    raw_data:amount_untaxed::number        as amount_untaxed,
    raw_data:amount_tax::number            as amount_tax,
    raw_data:amount_total::number          as amount_total,
    raw_data:amount_residual::number       as amount_residual,
    raw_data:payment_state::string         as payment_state,
    raw_data:cdc_status::string            as cdc_status,
    raw_data:is_deleted::boolean           as is_deleted,
    raw_data:_cdc_ts_ms::number            as _cdc_ts_ms,
    raw_data:_cdc_lsn::number              as _cdc_lsn,
    {{ deb_ts('raw_data:write_date') }}    as write_date,
    raw_data:ingested_at::timestamp_ntz    as ingested_at
from {{ source('bronze', 'account_move') }}
{{ incremental_filter() }}
