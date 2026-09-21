-- 1:1 purchase.order. GRAIN: 1 CDC event (append-only). SOURCE: bronze CDC topic odoo.purchase.order
{{ config(
    materialized='incremental',
    incremental_strategy='append',
    on_schema_change='sync_all_columns'
) }}
select
    raw_data:id::number                    as order_id,
    raw_data:name::string                  as name,
    raw_data:partner_id::number            as partner_id,
    raw_data:user_id::number               as user_id,
    raw_data:state::string                 as state,
    {{ deb_ts('raw_data:date_order') }}    as date_order,
    {{ deb_ts('raw_data:date_planned') }}  as date_planned,
    raw_data:amount_total::number          as amount_total,
    raw_data:cdc_status::string            as cdc_status,
    raw_data:is_deleted::boolean           as is_deleted,
    raw_data:_cdc_ts_ms::number            as _cdc_ts_ms,
    raw_data:_cdc_lsn::number              as _cdc_lsn,
    {{ deb_ts('raw_data:write_date') }}    as write_date,
    raw_data:ingested_at::timestamp_ntz    as ingested_at
from {{ source('bronze', 'purchase_order') }}
{{ incremental_filter() }}
