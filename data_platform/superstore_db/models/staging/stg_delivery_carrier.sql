-- 1:1 delivery.carrier. GRAIN: 1 CDC event (append-only).
{{ config(
    materialized='incremental',
    incremental_strategy='append',
    on_schema_change='sync_all_columns'
) }}

select
    raw_data:id::number                    as carrier_id,
    {{ deb_i18n('raw_data:name') }}         as carrier_name,
    raw_data:delivery_type::string          as delivery_type,
    raw_data:product_id::number             as product_id,
    raw_data:fixed_price::number            as fixed_price,
    raw_data:company_id::number             as company_id,
    raw_data:active::boolean                as active,
    raw_data:cdc_status::string             as cdc_status,
    raw_data:is_deleted::boolean            as is_deleted,
    raw_data:_cdc_ts_ms::number             as _cdc_ts_ms,
    raw_data:_cdc_lsn::number               as _cdc_lsn,
    {{ deb_ts('raw_data:write_date') }}      as write_date,
    raw_data:ingested_at::timestamp_ntz     as ingested_at
from {{ source('bronze', 'delivery_carrier') }}
{{ incremental_filter() }}
