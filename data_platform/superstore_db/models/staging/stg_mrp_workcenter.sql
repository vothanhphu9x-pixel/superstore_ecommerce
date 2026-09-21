-- 1:1 mrp.workcenter. GRAIN: 1 CDC event (append-only). SOURCE: bronze CDC topic odoo.mrp.workcenter.
{{ config(
    materialized='incremental',
    incremental_strategy='append',
    on_schema_change='sync_all_columns'
) }}
select
    raw_data:id::number                as workcenter_id,
    raw_data:name::string              as name,
    raw_data:code::string              as code,
    raw_data:default_capacity::number  as default_capacity,
    raw_data:time_efficiency::number   as time_efficiency,
    raw_data:active::boolean           as active,
    raw_data:cdc_status::string        as cdc_status,
    raw_data:is_deleted::boolean       as is_deleted,
    raw_data:_cdc_ts_ms::number        as _cdc_ts_ms,
    raw_data:_cdc_lsn::number          as _cdc_lsn,
    raw_data:ingested_at::timestamp_ntz as ingested_at
from {{ source('bronze', 'mrp_workcenter') }}
{{ incremental_filter() }}
