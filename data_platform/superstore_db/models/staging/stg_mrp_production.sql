-- 1:1 mrp.production. GRAIN: 1 CDC event (append-only). SOURCE: bronze CDC topic
-- odoo.mrp.production. KHÔNG qua silver.
{{ config(
    materialized='incremental',
    incremental_strategy='append',
    on_schema_change='sync_all_columns'
) }}
select
    raw_data:id::number                    as mrp_production_id,
    raw_data:name::string                  as name,
    raw_data:priority::string              as priority,
    raw_data:product_id::number            as product_id,
    raw_data:product_qty::number           as product_qty,
    raw_data:qty_producing::number         as qty_producing,
    raw_data:bom_id::number                as bom_id,
    raw_data:location_src_id::number       as location_src_id,
    raw_data:location_dest_id::number      as location_dest_id,
    {{ deb_ts('raw_data:date_deadline') }} as date_deadline,
    {{ deb_ts('raw_data:date_start') }}    as date_start,
    {{ deb_ts('raw_data:date_finished') }} as date_finished,
    raw_data:state::string                 as state,
    raw_data:cdc_status::string            as cdc_status,
    raw_data:is_deleted::boolean           as is_deleted,
    raw_data:_cdc_ts_ms::number            as _cdc_ts_ms,
    raw_data:_cdc_lsn::number              as _cdc_lsn,
    {{ deb_ts('raw_data:write_date') }}    as write_date,
    raw_data:ingested_at::timestamp_ntz    as ingested_at
from {{ source('bronze', 'mrp_production') }}
{{ incremental_filter() }}
