-- 1:1 product.product. GRAIN: 1 CDC event (append-only). SOURCE: bronze CDC topic odoo.product.product
{{ config(
    materialized='incremental',
    incremental_strategy='append',
    on_schema_change='sync_all_columns'
) }}
select
    raw_data:id::number                as product_id,
    raw_data:product_tmpl_id::number   as product_tmpl_id,
    raw_data:default_code::string      as default_code,
    raw_data:barcode::string           as barcode,
    -- Giá vốn nằm ở product.product (KHÔNG phải product.template — bảng đó không hề có cột
    -- standard_price, verify bằng cách liệt kê key của payload CDC thật). Cột này là
    -- company-dependent nên Postgres lưu jsonb {"<company_id>": 51.99} → phải bóc qua macro.
    {{ deb_jsonb_get('raw_data:standard_price', '"1"') }}::number as standard_price,
    raw_data:active::boolean           as active,
    {{ deb_ts('raw_data:write_date') }} as write_date,
    raw_data:cdc_status::string        as cdc_status,
    raw_data:is_deleted::boolean       as is_deleted,
    raw_data:_cdc_ts_ms::number        as _cdc_ts_ms,
    raw_data:_cdc_lsn::number          as _cdc_lsn,
    raw_data:ingested_at::timestamp_ntz as ingested_at
from {{ source('bronze', 'product_product') }}
{{ incremental_filter() }}