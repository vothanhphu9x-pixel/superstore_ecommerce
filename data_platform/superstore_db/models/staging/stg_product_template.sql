-- 1:1 product.template. GRAIN: 1 CDC event (append-only). SOURCE: bronze CDC topic odoo.product.template
-- ⚠️ domain-de.dbml liệt kê uom_name là field trên bảng này ("related field: uom_id.name")
-- nhưng verify qua information_schema: product_template KHÔNG có cột uom_name thật, chỉ có
-- uom_id — tài liệu ghi sai. uom_name phải resolve bằng JOIN stg_uom_uom ở sil_product_enriched.
{{ config(
    materialized='incremental',
    incremental_strategy='append',
    on_schema_change='sync_all_columns'
) }}
select
    raw_data:id::number                as product_tmpl_id,
    {{ deb_i18n('raw_data:name') }}    as name,
    raw_data:type::string              as type,
    raw_data:is_storable::boolean      as is_storable,
    raw_data:categ_id::number          as categ_id,
    raw_data:list_price::number        as list_price,
    raw_data:sale_ok::boolean          as sale_ok,
    raw_data:purchase_ok::boolean      as purchase_ok,
    raw_data:tracking::string          as tracking,
    raw_data:uom_id::number            as uom_id,
    raw_data:cdc_status::string        as cdc_status,
    raw_data:is_deleted::boolean       as is_deleted,
    raw_data:_cdc_ts_ms::number        as _cdc_ts_ms,
    raw_data:_cdc_lsn::number          as _cdc_lsn,
    {{ deb_ts('raw_data:write_date') }} as write_date,
    raw_data:ingested_at::timestamp_ntz as ingested_at
from {{ source('bronze', 'product_template') }}
{{ incremental_filter() }}
