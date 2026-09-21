-- 1:1 stock.warehouse. GRAIN: 1 CDC event (append-only). SOURCE: bronze CDC topic odoo.stock.warehouse.
-- ⚠️ Odoo core KHÔNG có city/state/region trên warehouse trực tiếp — dim_warehouse dùng mapping
-- tĩnh theo warehouse_code (4 kho Superstore cố định), xem note dim_warehouse.
{{ config(
    materialized='incremental',
    incremental_strategy='append',
    on_schema_change='sync_all_columns'
) }}
select
    raw_data:id::number                as warehouse_id,
    raw_data:name::string              as name,
    raw_data:code::string              as code,
    raw_data:partner_id::number        as partner_id,
    raw_data:active::boolean           as active,
    raw_data:cdc_status::string        as cdc_status,
    raw_data:is_deleted::boolean       as is_deleted,
    raw_data:_cdc_ts_ms::number        as _cdc_ts_ms,
    raw_data:_cdc_lsn::number          as _cdc_lsn,
    raw_data:ingested_at::timestamp_ntz as ingested_at
from {{ source('bronze', 'stock_warehouse') }}
{{ incremental_filter() }}
