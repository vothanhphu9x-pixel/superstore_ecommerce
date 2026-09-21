-- GRAIN   : 1 hàng = 1 valuation event (stock_valuation_layer).
-- SOURCE  : silver → sil_stock_valuation_enriched (đã enrich stock_move để trace location).
-- DERIVED : transaction_type suy ra từ description + dấu quantity.
-- TEST    : unique(fact_inv_val_sk), not_null(stock_valuation_layer_id).
-- product_sk temporal join theo Silver processing time; create_date chỉ là business time.
{{ config(
    materialized='incremental',
    incremental_strategy='merge',
    unique_key='stock_valuation_layer_id',
    on_schema_change='sync_all_columns'
) }}

select
    {{ dbt_utils.generate_surrogate_key(['svl.stock_valuation_layer_id']) }} as fact_inv_val_sk,
    svl.stock_valuation_layer_id,
    svl.stock_move_id,
    to_number(
        to_char(svl.create_date, 'YYYYMMDD')
    )                                                   as valuation_date_key,
    dp.product_sk,
    src_loc.location_sk                                 as src_location_sk,
    dest_loc.location_sk                                as dest_location_sk,
    coalesce(
        dest_loc.warehouse_sk,
        src_loc.warehouse_sk
    )                                                   as warehouse_sk,
    case
        when svl.description ilike '%revaluation%'
            then 'revaluation'
        when svl.quantity > 0
            then 'in'
        when svl.quantity < 0
            then 'out'
        else 'revaluation'
    end                                                 as transaction_type,
    svl.quantity,
    svl.is_deleted,
    svl.unit_cost                                       as unit_cost_amount,
    svl.value                                           as value_amount,
    svl.remaining_qty,
    svl.remaining_value                                 as remaining_value_amount,
    svl.reference,
    svl.silver_updated_at                               as source_silver_updated_at,
    svl.source_version_key,
    svl._cdc_ts_ms                                      as valuation_cdc_ts_ms,
    svl._cdc_lsn                                        as valuation_cdc_lsn,
    svl.move_cdc_ts_ms,
    svl.move_cdc_lsn,
    dp.dim_updated_at                                   as product_dim_updated_at,
    src_loc.dim_updated_at                              as src_location_dim_updated_at,
    dest_loc.dim_updated_at                             as dest_location_dim_updated_at
from {{ ref('sil_stock_valuation_enriched') }} svl
left join {{ ref('dim_product') }} dp
    on dp.product_id = svl.product_id
   and svl.silver_updated_at >= dp.dbt_valid_from
   and svl.silver_updated_at < coalesce(dp.dbt_valid_to, '9999-12-31'::timestamp)
left join {{ ref('dim_location') }} src_loc
    on src_loc.location_id = svl.location_id
left join {{ ref('dim_location') }} dest_loc
    on dest_loc.location_id = svl.location_dest_id

{% if is_incremental() %}
left join {{ this }} tgt
    on tgt.stock_valuation_layer_id = svl.stock_valuation_layer_id
where tgt.stock_valuation_layer_id is null
   or svl.silver_updated_at > coalesce(
        tgt.source_silver_updated_at,
        '1900-01-01'::timestamp
   )
   or coalesce(dp.product_sk, '__NULL__') <> coalesce(tgt.product_sk, '__NULL__')
   or coalesce(src_loc.location_sk, '__NULL__')
      <> coalesce(tgt.src_location_sk, '__NULL__')
   or coalesce(dest_loc.location_sk, '__NULL__')
      <> coalesce(tgt.dest_location_sk, '__NULL__')
   or coalesce(dp.dim_updated_at, '1900-01-01'::timestamp)
      > coalesce(tgt.product_dim_updated_at, '1900-01-01'::timestamp)
   or coalesce(src_loc.dim_updated_at, '1900-01-01'::timestamp)
      > coalesce(tgt.src_location_dim_updated_at, '1900-01-01'::timestamp)
   or coalesce(dest_loc.dim_updated_at, '1900-01-01'::timestamp)
      > coalesce(tgt.dest_location_dim_updated_at, '1900-01-01'::timestamp)
{% endif %}
