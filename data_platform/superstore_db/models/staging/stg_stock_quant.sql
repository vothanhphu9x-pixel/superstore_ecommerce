-- 1:1 stock.quant. GRAIN: 1 CDC event của stock_quant_id (append-only).
-- Business identity còn phụ thuộc product/location/lot/package/owner/company.
-- Đây là live balance, KHÔNG có lịch sử business trong Odoo.
-- KHÔNG qua silver, KHÔNG dbt snapshot — fact_inventory_balance tự lưu lịch sử qua
-- materialized=incremental (1 hàng/ngày/product×location).
{{ config(
    materialized='incremental',
    incremental_strategy='append',
    on_schema_change='sync_all_columns'
) }}
select
    raw_data:id::number                    as stock_quant_id,
    raw_data:product_id::number            as product_id,
    raw_data:location_id::number           as location_id,
    raw_data:lot_id::number                as lot_id,
    raw_data:package_id::number            as package_id,
    raw_data:owner_id::number              as owner_id,
    raw_data:company_id::number            as company_id,
    raw_data:quantity::number              as quantity,
    raw_data:reserved_quantity::number     as reserved_quantity,
    raw_data:inventory_quantity::number    as inventory_quantity,
    raw_data:inventory_diff_quantity::number as inventory_diff_quantity,
    raw_data:cdc_status::string            as cdc_status,
    raw_data:is_deleted::boolean           as is_deleted,
    raw_data:_cdc_ts_ms::number            as _cdc_ts_ms,
    raw_data:_cdc_lsn::number              as _cdc_lsn,
    {{ deb_ts('raw_data:write_date') }}    as write_date,
    raw_data:ingested_at::timestamp_ntz    as ingested_at
from {{ source('bronze', 'stock_quant') }}
{{ incremental_filter() }}
