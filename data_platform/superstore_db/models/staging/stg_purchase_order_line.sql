-- 1:1 purchase.order.line. GRAIN: 1 CDC event (append-only). SOURCE: bronze CDC topic
-- odoo.purchase.order.line. Silver kết hợp line với purchase order header.
{{ config(
    materialized='incremental',
    incremental_strategy='append',
    on_schema_change='sync_all_columns'
) }}
select
    raw_data:id::number                    as purchase_order_line_id,
    raw_data:order_id::number              as order_id,
    raw_data:product_id::number            as product_id,
    {{ deb_ts('raw_data:date_planned') }}  as date_planned,
    raw_data:product_qty::number           as product_qty,
    raw_data:qty_received::number          as qty_received,
    raw_data:price_unit::number            as price_unit,
    raw_data:discount::number              as discount,
    raw_data:price_subtotal::number        as price_subtotal,
    raw_data:cdc_status::string            as cdc_status,
    raw_data:is_deleted::boolean           as is_deleted,
    raw_data:_cdc_ts_ms::number            as _cdc_ts_ms,
    raw_data:_cdc_lsn::number              as _cdc_lsn,
    raw_data:ingested_at::timestamp_ntz    as ingested_at
from {{ source('bronze', 'purchase_order_line') }}
{{ incremental_filter() }}
