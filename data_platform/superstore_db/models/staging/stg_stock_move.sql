-- 1:1 stock.move. GRAIN: 1 CDC event (append-only). SOURCE: bronze CDC topic odoo.stock.move
{{ config(
    materialized='incremental',
    incremental_strategy='append',
    on_schema_change='sync_all_columns'
) }}
select
    raw_data:id::number                    as stock_move_id,
    {{ deb_ts('raw_data:date') }}          as date,
    raw_data:product_id::number            as product_id,
    raw_data:product_uom_qty::number       as product_uom_qty,
    -- field thật tên 'quantity' (Odoo 17+, trước đây 'quantity_done')
    raw_data:quantity::number              as quantity,
    raw_data:location_id::number           as location_id,
    raw_data:location_dest_id::number      as location_dest_id,
    raw_data:picking_id::number            as picking_id,
    raw_data:purchase_line_id::number      as purchase_order_line_id,
    raw_data:sale_line_id::number          as sale_order_line_id,
    raw_data:state::string                 as state,
    raw_data:origin::string                as origin,
    raw_data:reference::string             as reference,
    raw_data:cdc_status::string            as cdc_status,
    raw_data:is_deleted::boolean           as is_deleted,
    raw_data:_cdc_ts_ms::number            as _cdc_ts_ms,
    raw_data:_cdc_lsn::number              as _cdc_lsn,
    {{ deb_ts('raw_data:write_date') }}    as write_date,
    raw_data:ingested_at::timestamp_ntz    as ingested_at
from {{ source('bronze', 'stock_move') }}
{{ incremental_filter() }}
