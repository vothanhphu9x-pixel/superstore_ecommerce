-- 1:1 stock.scrap. GRAIN: 1 CDC event (append-only).
-- Chỉ chuẩn hoá kiểu dữ liệu; dedup và lọc trạng thái được thực hiện ở Silver.
{{ config(
    materialized='incremental',
    incremental_strategy='append',
    on_schema_change='sync_all_columns'
) }}

select
    raw_data:id::number                    as stock_scrap_id,
    raw_data:name::string                  as name,
    raw_data:product_id::number            as product_id,
    raw_data:production_id::number         as production_id,
    raw_data:workorder_id::number          as workorder_id,
    raw_data:scrap_qty::number             as scrap_qty,
    raw_data:location_id::number           as location_id,
    raw_data:scrap_location_id::number     as scrap_location_id,
    raw_data:state::string                 as state,
    {{ deb_ts('raw_data:date_done') }}     as date_done,
    raw_data:origin::string                as origin,
    raw_data:company_id::number            as company_id,
    raw_data:cdc_status::string            as cdc_status,
    raw_data:is_deleted::boolean           as is_deleted,
    raw_data:_cdc_ts_ms::number            as _cdc_ts_ms,
    raw_data:_cdc_lsn::number              as _cdc_lsn,
    {{ deb_ts('raw_data:write_date') }}    as write_date,
    raw_data:ingested_at::timestamp_ntz    as ingested_at
from {{ source('bronze', 'stock_scrap') }}
{{ incremental_filter() }}
