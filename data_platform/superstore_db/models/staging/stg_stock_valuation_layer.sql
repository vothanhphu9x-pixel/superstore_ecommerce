-- 1:1 stock.valuation.layer. GRAIN: 1 CDC event (append-only). SOURCE: bronze CDC topic
-- odoo.stock.valuation.layer. Silver dedup trước khi Gold temporal join dimension.
{{ config(
    materialized='incremental',
    incremental_strategy='append',
    on_schema_change='sync_all_columns'
) }}
select
    raw_data:id::number                    as stock_valuation_layer_id,
    raw_data:product_id::number            as product_id,
    raw_data:stock_move_id::number         as stock_move_id,
    raw_data:description::string           as description,
    raw_data:quantity::number              as quantity,
    raw_data:unit_cost::number             as unit_cost,
    raw_data:value::number                 as value,
    raw_data:remaining_qty::number         as remaining_qty,
    raw_data:remaining_value::number       as remaining_value,
    -- Magic field — dùng làm event_date vì bảng này không có cột 'date' riêng (domain-de.dbml)
    {{ deb_ts('raw_data:create_date') }}   as create_date,
    raw_data:cdc_status::string            as cdc_status,
    raw_data:is_deleted::boolean           as is_deleted,
    raw_data:_cdc_ts_ms::number            as _cdc_ts_ms,
    raw_data:_cdc_lsn::number              as _cdc_lsn,
    raw_data:ingested_at::timestamp_ntz    as ingested_at
from {{ source('bronze', 'stock_valuation_layer') }}
{{ incremental_filter() }}
