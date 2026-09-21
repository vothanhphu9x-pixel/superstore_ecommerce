-- GRAIN: 1 product_id × 1 captured product_template version.
-- MERGE theo product_version_id vì một dbt_scd_id của template có thể có nhiều SKU.
-- Khi boundary hoặc lookup/SKU/BOM đổi, reload toàn bộ versions của product_id đó.
{{ config(
    materialized='incremental',
    incremental_strategy='merge',
    unique_key='product_version_id',
    on_schema_change='sync_all_columns',
    full_refresh=false
) }}

{% set target_has_enrichment_key =
    is_incremental() and relation_has_column(this, 'enrichment_version_key')
%}

with bom_latest as (
    select *
    from {{ ref('stg_mrp_bom') }}
    qualify row_number() over (
        partition by bom_id
        order by _cdc_ts_ms desc, _cdc_lsn desc
    ) = 1
),
bom_products as (
    select
        product_tmpl_id,
        count_if(is_deleted = false and bom_type = 'normal' and is_active = true) > 0
            as is_manufactured,
        max(_cdc_ts_ms) as bom_cdc_ts_ms
    from bom_latest
    group by product_tmpl_id
),
product_product_latest as (
    select *
    from {{ ref('stg_product_product') }}
    qualify row_number() over (
        partition by product_id
        order by _cdc_ts_ms desc, _cdc_lsn desc
    ) = 1
),
product_variants as (
    select
        product_tmpl_id,
        product_id,
        default_code,
        barcode,
        standard_price,
        (is_deleted = false and active = true) as is_active,
        _cdc_ts_ms,
        _cdc_lsn
    from product_product_latest
),
category_latest as (
    select *
    from {{ ref('stg_product_category') }}
    qualify row_number() over (
        partition by categ_id
        order by _cdc_ts_ms desc, _cdc_lsn desc
    ) = 1
),
uom_latest as (
    select *
    from {{ ref('stg_uom_uom') }}
    qualify row_number() over (
        partition by uom_id
        order by _cdc_ts_ms desc, _cdc_lsn desc
    ) = 1
),
source_versions as (
    select *
    from {{ ref('snap_product_template') }}
    where is_deleted = false
),
source_enriched as (
    select
        {{ dbt_utils.generate_surrogate_key([
            'snap.dbt_scd_id',
            'pv.product_id'
        ]) }} as product_version_id,
        snap.*,
        pv.product_id,
        pv.default_code,
        pv.barcode,
        pv.standard_price,
        pv.is_active as variant_is_active,
        iff(cat.is_deleted, null, cat.complete_name) as category_path,
        iff(u.is_deleted, null, u.name) as resolved_uom_name,
        coalesce(bp.is_manufactured, false) as resolved_is_manufactured,
        {{ dbt_utils.generate_surrogate_key([
            "coalesce(pv.default_code, '__NULL__')",
            "coalesce(pv.barcode, '__NULL__')",
            "coalesce(pv.standard_price, -1)",
            "coalesce(pv.is_active, false)",
            "coalesce(cat.complete_name, '__NULL__')",
            "coalesce(cat.is_deleted, false)",
            "coalesce(u.name, '__NULL__')",
            "coalesce(u.is_deleted, false)",
            "coalesce(bp.is_manufactured, false)"
        ]) }} as enrichment_version_key
    from source_versions snap
    join product_variants pv
        on pv.product_tmpl_id = snap.product_tmpl_id
    left join category_latest cat
        on cat.categ_id = snap.categ_id
    left join uom_latest u
        on u.uom_id = snap.uom_id
    left join bom_products bp
        on bp.product_tmpl_id = snap.product_tmpl_id
),
changed_products as (
    {% if is_incremental() %}
    select distinct src.product_id
    from source_enriched src
    left join {{ this }} tgt
        on tgt.product_version_id = src.product_version_id
    where tgt.product_version_id is null
       or coalesce(tgt.dbt_valid_to, '9999-12-31'::timestamp)
          <> coalesce(src.dbt_valid_to, '9999-12-31'::timestamp)
       or coalesce(tgt.is_current, false)
          <> (src.dbt_valid_to is null and src.variant_is_active)
       {% if target_has_enrichment_key %}
       or coalesce(tgt.enrichment_version_key, '__NULL__')
          <> coalesce(src.enrichment_version_key, '__NULL__')
       {% else %}
       -- Rollout lần đầu: target cũ chưa có enrichment_version_key.
       or 1 = 1
       {% endif %}
    {% else %}
    select distinct product_id
    from source_enriched
    {% endif %}
)

select
    src.product_version_id,
    src.dbt_scd_id,
    src.product_tmpl_id,
    src.product_id,
    src.categ_id,
    src.name as product_name,
    src.default_code as sku,
    src.barcode,
    split_part(src.category_path, ' / ', 2) as category_l1,
    nullif(split_part(src.category_path, ' / ', 3), '') as category_l2,
    nullif(split_part(src.category_path, ' / ', 4), '') as category_l3,
    src.list_price,
    -- Giá vốn nằm trên product.product. Đây vẫn là current standard cost,
    -- không phải valuation cost lịch sử; fact_inventory_valuation giữ giá trị thực tế.
    src.standard_price,
    src.resolved_is_manufactured as is_manufactured,
    src.is_storable,
    src.tracking,
    src.resolved_uom_name as uom_name,
    src.sale_ok,
    src.purchase_ok,
    src.variant_is_active as is_active,
    (src.dbt_valid_to is null and src.variant_is_active) as is_current,
    src.dbt_valid_from,
    src.dbt_valid_to,
    src._cdc_ts_ms as source_cdc_ts_ms,
    src._cdc_lsn as source_cdc_lsn,
    src.enrichment_version_key,
    {{ pipeline_now() }} as enrichment_updated_at
from source_enriched src
join changed_products cp
    on cp.product_id = src.product_id
