-- GRAIN   : 1 product_id × 1 captured product_template version.
-- SOURCE  : silver → sil_product_enriched (snap_product_template)
-- DERIVED : n/a (pass-through + is_current)
-- TEST    : unique(product_sk), not_null(product_id), relationships hợp lệ mọi fact.product_sk
-- unique_key=product_version_id (product_id có nhiều historical version).
-- MERGE toàn bộ Silver dimension để closure/correction của version cũ không bị watermark bỏ sót.
{{ config(
    materialized='incremental',
    incremental_strategy='merge',
    unique_key='product_version_id',
    on_schema_change='sync_all_columns'
) }}
select
    {{ dbt_utils.generate_surrogate_key(['product_version_id']) }} as product_sk,
    product_version_id,
    product_id,
    product_tmpl_id,
    product_name,
    sku,
    barcode,
    category_l1,
    category_l2,
    category_l3,
    list_price                         as list_price_amount,
    standard_price                     as standard_cost_amount,
    is_manufactured,
    is_storable,
    tracking,
    uom_name,
    sale_ok,
    purchase_ok,
    is_active,
    is_current,
    dbt_valid_from,
    dbt_valid_to,
    dbt_scd_id,
    source_cdc_ts_ms,
    source_cdc_lsn,
    enrichment_version_key,
    enrichment_updated_at,
    greatest_ignore_nulls(
        dbt_valid_from,
        dbt_valid_to,
        enrichment_updated_at
    )                                  as dim_updated_at,
    dbt_valid_from                     as dbt_updated_at,
    {{ pipeline_now() }}                as gold_refreshed_at
from {{ ref('sil_product_enriched') }}
