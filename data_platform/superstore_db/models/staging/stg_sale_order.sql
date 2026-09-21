-- 1:1 sale.order. GRAIN: 1 CDC event (append-only). SOURCE: bronze CDC topic odoo.sale.order
{{ config(
    materialized='incremental',
    incremental_strategy='append',
    on_schema_change='sync_all_columns'
) }}
select
    raw_data:id::number                as order_id,
    raw_data:name::string              as name,
    raw_data:partner_id::number        as partner_id,
    raw_data:user_id::number           as user_id,
    raw_data:warehouse_id::number      as warehouse_id,
    raw_data:state::string             as state,
    -- date_order thực chất là timestamp (verify qua information_schema), không phải date thuần
    -- như domain-de.dbml ghi — Debezium emit epoch MICROSECONDS, dùng deb_ts không phải deb_date.
    {{ deb_ts('raw_data:date_order') }} as date_order,
    raw_data:invoice_status::string    as invoice_status,
    -- delivery_status không có trong field list domain-de.dbml nhưng verify tồn tại thật trên
    -- sale_order qua information_schema — cần cho fact_sales.delivery_status (star-da.dbml).
    raw_data:delivery_status::string   as delivery_status,
    raw_data:amount_total::number      as amount_total,
    raw_data:campaign_id::number       as campaign_id,
    raw_data:medium_id::number         as medium_id,
    raw_data:source_id::number         as source_id,
    raw_data:opportunity_id::number    as opportunity_id,
    raw_data:cdc_status::string        as cdc_status,
    raw_data:is_deleted::boolean       as is_deleted,
    raw_data:_cdc_ts_ms::number        as _cdc_ts_ms,
    raw_data:_cdc_lsn::number          as _cdc_lsn,
    {{ deb_ts('raw_data:write_date') }} as write_date,
    raw_data:ingested_at::timestamp_ntz as ingested_at
from {{ source('bronze', 'sale_order') }}
{{ incremental_filter() }}
