-- 1:1 account.payment. GRAIN: 1 CDC event (append-only). SOURCE: bronze CDC topic odoo.account.payment
{{ config(
    materialized='incremental',
    incremental_strategy='append',
    on_schema_change='sync_all_columns'
) }}
select
    raw_data:id::number                    as payment_id,
    raw_data:name::string                  as name,
    raw_data:move_id::number               as move_id,
    {{ deb_date('raw_data:date') }}        as date,
    raw_data:journal_id::number            as journal_id,
    raw_data:partner_id::number            as partner_id,
    raw_data:amount::number                as amount,
    raw_data:payment_type::string          as payment_type,
    raw_data:state::string                 as state,
    raw_data:cdc_status::string            as cdc_status,
    raw_data:is_deleted::boolean           as is_deleted,
    raw_data:_cdc_ts_ms::number            as _cdc_ts_ms,
    raw_data:_cdc_lsn::number              as _cdc_lsn,
    raw_data:ingested_at::timestamp_ntz    as ingested_at
from {{ source('bronze', 'account_payment') }}
{{ incremental_filter() }}
