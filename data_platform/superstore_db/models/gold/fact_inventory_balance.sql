-- GRAIN   : 1 hàng = 1 product × 1 location × 1 snapshot_date.
-- SOURCE  : staging → stg_stock_quant (KHÔNG qua silver — stock_quant LIVE, không có lịch sử)
-- DERIVED : quantity_available = quantity - reserved_quantity
-- TEST    : unique(fact_inv_bal_sk), not_null(product_sk/location_sk/snapshot_date_key)
-- IMPORTANT: stock.quant thật có grain chi tiết theo quant_id/lot/package/owner/company. Model
-- deduplicate từng quant_id rồi SUM về grain product × location trước khi chụp snapshot ngày.
-- delete+insert theo snapshot_date_key giúp rerun cùng ngày thay toàn bộ partition, kể cả sau
-- partial failure. Population của ngày hiện tại được giữ để quant biến mất được ghi về 0,
-- không để lại balance cũ. full_refresh=false bảo vệ lịch sử các ngày trước.
-- Không có Silver timestamp nên Fact dùng snapshot_captured_at (processing time của lần chụp)
-- để temporal join với dbt_valid_from/dbt_valid_to của dim_product.
{{ config(
    materialized='incremental',
    incremental_strategy='delete+insert',
    unique_key='snapshot_date_key',
    full_refresh=false,
    on_schema_change='sync_all_columns'
) }}

with run_context as (
    select
        to_number(to_char({{ pipeline_today() }}, 'YYYYMMDD'))      as snapshot_date_key,
        {{ pipeline_now() }}                  as snapshot_captured_at
),
quant_latest as (
    select *
    from {{ ref('stg_stock_quant') }}
    qualify row_number() over (
        partition by stock_quant_id
        order by _cdc_ts_ms desc, _cdc_lsn desc
    ) = 1
),
quant_balance as (
    select
        product_id,
        location_id,
        sum(quantity)                                      as quantity,
        sum(reserved_quantity)                             as reserved_quantity
    from quant_latest
    where is_deleted = false
    group by product_id, location_id
),
snapshot_inventory as (
    select product_id, location_id
    from quant_balance
    {% if is_incremental() %}
    union
    select product_id, location_id
    from {{ this }}
    where snapshot_date_key = to_number(to_char({{ pipeline_today() }}, 'YYYYMMDD'))
    {% endif %}
)

select
    {{ dbt_utils.generate_surrogate_key([
        'inventory.product_id',
        'inventory.location_id',
        'rc.snapshot_date_key'
    ]) }}                                                   as fact_inv_bal_sk,
    rc.snapshot_date_key,
    rc.snapshot_captured_at,
    inventory.product_id,
    inventory.location_id,
    dp.product_sk,
    dloc.warehouse_sk,
    dloc.location_sk,
    coalesce(q.quantity, 0)                                 as quantity,
    coalesce(q.reserved_quantity, 0)                        as reserved_quantity,
    coalesce(q.quantity, 0) - coalesce(q.reserved_quantity, 0)
                                                               as quantity_available
from snapshot_inventory inventory
cross join run_context rc
left join quant_balance q
    on q.product_id = inventory.product_id
   and q.location_id = inventory.location_id
left join {{ ref('dim_product') }} dp
    on dp.product_id = inventory.product_id
   and rc.snapshot_captured_at >= dp.dbt_valid_from
   and rc.snapshot_captured_at < coalesce(
        dp.dbt_valid_to,
        '9999-12-31'::timestamp
   )
left join {{ ref('dim_location') }} dloc
    on dloc.location_id = inventory.location_id
