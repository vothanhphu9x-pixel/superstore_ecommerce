-- GRAIN   : 1 hàng = 1 mrp_production đã hoàn thành.
-- SOURCE  : silver → sil_manufacturing_enriched.
-- DERIVED : scrap_qty; cycle_time_minutes.
-- SCD2    : product_sk được resolve bằng silver_updated_at; date_finished chỉ dùng reporting.
{{ config(
    materialized='incremental',
    incremental_strategy='merge',
    unique_key='mrp_production_id',
    on_schema_change='sync_all_columns'
) }}

select
    {{ dbt_utils.generate_surrogate_key([
        'src.mrp_production_id'
    ]) }}                                                as fact_mfg_sk,
    src.mrp_production_id,
    to_number(
        to_char(src.date_finished, 'YYYYMMDD')
    )                                                   as completion_date_key,
    dp.product_sk,
    dloc.warehouse_sk,
    src.mo_name,
    src.qty_planned,
    src.qty_produced,
    src.scrap_qty,
    datediff(
        'minute',
        src.date_start,
        src.date_finished
    )                                                   as cycle_time_minutes,
    src.bom_id,
    src.mo_state,
    src.is_deleted,
    src.silver_updated_at                               as source_silver_updated_at,
    src.source_version_key,
    src.mo_cdc_ts_ms,
    src.mo_cdc_lsn,
    src.scrap_cdc_ts_ms,
    src.scrap_cdc_lsn,
    dp.dim_updated_at                                   as product_dim_updated_at,
    dloc.dim_updated_at                                 as location_dim_updated_at
from {{ ref('sil_manufacturing_enriched') }} src
left join {{ ref('dim_product') }} dp
    on dp.product_id = src.product_id
   and src.silver_updated_at >= dp.dbt_valid_from
   and src.silver_updated_at < coalesce(
        dp.dbt_valid_to,
        '9999-12-31'::timestamp
   )
left join {{ ref('dim_location') }} dloc
    on dloc.location_id = src.location_dest_id

{% if is_incremental() %}
left join {{ this }} tgt
    on tgt.mrp_production_id = src.mrp_production_id
where tgt.mrp_production_id is null
   or src.silver_updated_at > coalesce(
        tgt.source_silver_updated_at,
        '1900-01-01'::timestamp
   )
   or coalesce(src.source_version_key, '__NULL__')
      <> coalesce(tgt.source_version_key, '__NULL__')
   or coalesce(dp.product_sk, '__NULL__')
      <> coalesce(tgt.product_sk, '__NULL__')
   or coalesce(dloc.warehouse_sk, '__NULL__')
      <> coalesce(tgt.warehouse_sk, '__NULL__')
   or coalesce(
        dp.dim_updated_at,
        '1900-01-01'::timestamp
   ) > coalesce(
        tgt.product_dim_updated_at,
        '1900-01-01'::timestamp
   )
   or coalesce(
        dloc.dim_updated_at,
        '1900-01-01'::timestamp
   ) > coalesce(
        tgt.location_dim_updated_at,
        '1900-01-01'::timestamp
   )
{% endif %}
