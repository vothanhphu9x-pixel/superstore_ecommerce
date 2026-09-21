-- 1:1 stock.location. GRAIN: 1 CDC event (append-only). SOURCE: bronze CDC topic odoo.stock.location
{{ config(
    materialized='incremental',
    incremental_strategy='append',
    on_schema_change='sync_all_columns'
) }}
select
    raw_data:id::number                    as location_id,
    raw_data:name::string                  as name,
    raw_data:complete_name::string         as complete_name,
    raw_data:usage::string                 as usage,
    raw_data:warehouse_id::number          as warehouse_id,
    raw_data:cdc_status::string            as cdc_status,
    raw_data:is_deleted::boolean           as is_deleted,
    raw_data:_cdc_ts_ms::number            as _cdc_ts_ms,
    raw_data:_cdc_lsn::number              as _cdc_lsn,
    raw_data:ingested_at::timestamp_ntz    as ingested_at
from {{ source('bronze', 'stock_location') }}
{{ incremental_filter() }}
