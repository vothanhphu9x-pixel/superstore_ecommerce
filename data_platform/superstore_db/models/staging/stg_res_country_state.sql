-- 1:1 res.country.state (lookup nhỏ). GRAIN: 1 CDC event (append-only). SOURCE: bronze CDC topic odoo.res.country.state
{{ config(
    materialized='incremental',
    incremental_strategy='append',
    on_schema_change='sync_all_columns'
) }}
select
    raw_data:id::number                as state_id,
    raw_data:name::string              as name,
    raw_data:code::string              as code,
    raw_data:country_id::number        as country_id,
    raw_data:cdc_status::string        as cdc_status,
    raw_data:is_deleted::boolean       as is_deleted,
    raw_data:_cdc_ts_ms::number        as _cdc_ts_ms,
    raw_data:_cdc_lsn::number          as _cdc_lsn,
    raw_data:ingested_at::timestamp_ntz as ingested_at
from {{ source('bronze', 'res_country_state') }}
{{ incremental_filter() }}