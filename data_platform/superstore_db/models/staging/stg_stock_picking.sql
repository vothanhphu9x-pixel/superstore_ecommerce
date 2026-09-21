-- 1:1 stock.picking. GRAIN: 1 CDC event (append-only). SOURCE: bronze CDC topic odoo.stock.picking
{{ config(
    materialized='incremental',
    incremental_strategy='append',
    on_schema_change='sync_all_columns'
) }}
select
    raw_data:id::number                    as picking_id,
    raw_data:name::string                  as name,
    raw_data:origin::string                as origin,
    -- FK cấu trúc tới sale_order; ưu tiên key này thay vì parse origin dạng text.
    raw_data:sale_id::number               as sale_id,
    raw_data:partner_id::number            as partner_id,
    raw_data:picking_type_id::number       as picking_type_id,
    raw_data:location_id::number           as location_id,
    raw_data:location_dest_id::number      as location_dest_id,
    raw_data:state::string                 as state,
    {{ deb_ts('raw_data:scheduled_date') }} as scheduled_date,
    {{ deb_ts('raw_data:date_deadline') }} as date_deadline,
    {{ deb_ts('raw_data:date') }}          as date,
    {{ deb_ts('raw_data:date_done') }}     as date_done,
    raw_data:has_deadline_issue::boolean   as has_deadline_issue,
    raw_data:carrier_id::number            as carrier_id,
    raw_data:carrier_tracking_ref::string  as carrier_tracking_ref,
    raw_data:carrier_price::number         as carrier_price,
    raw_data:cdc_status::string            as cdc_status,
    raw_data:is_deleted::boolean           as is_deleted,
    raw_data:_cdc_ts_ms::number            as _cdc_ts_ms,
    raw_data:_cdc_lsn::number              as _cdc_lsn,
    {{ deb_ts('raw_data:write_date') }}    as write_date,
    raw_data:ingested_at::timestamp_ntz    as ingested_at
from {{ source('bronze', 'stock_picking') }}
{{ incremental_filter() }}
