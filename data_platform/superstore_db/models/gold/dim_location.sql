-- GRAIN: 1 stock_location hiện hành. SOURCE: stg_stock_location (không silver — dùng staging
-- trực tiếp). Domain-specific dim (KHÔNG conformed) — thay location_name degenerate ở
-- fact_inventory_movement (src/dest) và fact_inventory_balance.
-- TEST: unique(location_sk), not_null(location_id)
{{ config(materialized='table') }}

with location_latest as (
    select *
    from {{ ref('stg_stock_location') }}
    qualify row_number() over (partition by location_id order by _cdc_ts_ms desc, _cdc_lsn desc) = 1
)
select
    {{ dbt_utils.generate_surrogate_key(['loc.location_id']) }} as location_sk,
    loc.location_id,
    loc.complete_name                  as location_name,
    loc.usage,
    dw.warehouse_sk,
    (loc.is_deleted = false)            as active,
    {{ deb_cdc_ts('loc._cdc_ts_ms') }} as dim_updated_at,
    {{ pipeline_now() }}                as gold_refreshed_at
from location_latest loc
left join {{ ref('dim_warehouse') }} dw on dw.warehouse_id = loc.warehouse_id
