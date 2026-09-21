-- 1:1 sale.order.line. GRAIN: 1 CDC event (append-only). SOURCE: bronze CDC topic odoo.sale.order.line
{{ config(
    materialized='incremental',
    incremental_strategy='append',
    on_schema_change='sync_all_columns'
) }}
select
    raw_data:id::number                as sale_order_line_id,
    raw_data:order_id::number          as order_id,
    raw_data:product_id::number        as product_id,
    raw_data:state::string             as state,
    raw_data:product_uom_qty::number   as product_uom_qty,
    raw_data:qty_delivered::number     as qty_delivered,
    raw_data:price_unit::number        as price_unit,
    raw_data:discount::number          as discount,
    raw_data:price_subtotal::number    as price_subtotal,
    raw_data:price_total::number       as price_total,
    raw_data:cdc_status::string        as cdc_status,
    raw_data:is_deleted::boolean       as is_deleted,
    raw_data:_cdc_ts_ms::number        as _cdc_ts_ms,
    raw_data:_cdc_lsn::number          as _cdc_lsn,
    {{ deb_ts('raw_data:write_date') }} as write_date,
    raw_data:ingested_at::timestamp_ntz as ingested_at
from {{ source('bronze', 'sale_order_line') }}
{{ incremental_filter() }}
