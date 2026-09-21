-- 1:1 mrp.bom. GRAIN: 1 CDC event (append-only). SOURCE: bronze CDC topic odoo.mrp.bom
{{ config(
    materialized='incremental',
    incremental_strategy='append',
    on_schema_change='sync_all_columns'
) }}
select
    raw_data:id::number                as bom_id,
    raw_data:product_tmpl_id::number   as product_tmpl_id,
    raw_data:type::string              as bom_type,
    raw_data:active::boolean           as is_active,
    raw_data:cdc_status::string        as cdc_status,
    raw_data:is_deleted::boolean       as is_deleted,
    raw_data:_cdc_ts_ms::number        as _cdc_ts_ms,
    raw_data:_cdc_lsn::number          as _cdc_lsn,
    raw_data:ingested_at::timestamp_ntz as ingested_at
from {{ source('bronze', 'mrp_bom') }}
{{ incremental_filter() }}
