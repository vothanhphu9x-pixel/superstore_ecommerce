-- [+] M2M junction odoo.res_partner_res_partner_category_rel (partner ↔ tag).
-- GRAIN: 1 CDC event (append-only). Không có cột id riêng — NK thật = (partner_id, category_id).
-- SOURCE: bronze CDC topic odoo.res_partner_category_rel
{{ config(
    materialized='incremental',
    incremental_strategy='append',
    on_schema_change='sync_all_columns'
) }}
select
    raw_data:partner_id::number        as partner_id,
    raw_data:category_id::number       as category_id,
    raw_data:cdc_status::string        as cdc_status,
    raw_data:is_deleted::boolean       as is_deleted,
    raw_data:_cdc_ts_ms::number        as _cdc_ts_ms,
    raw_data:_cdc_lsn::number          as _cdc_lsn,
    raw_data:ingested_at::timestamp_ntz as ingested_at
from {{ source('bronze', 'res_partner_res_partner_category_rel') }}
{{ incremental_filter() }}