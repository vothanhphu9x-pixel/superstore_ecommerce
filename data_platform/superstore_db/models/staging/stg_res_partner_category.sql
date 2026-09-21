-- 1:1 res.partner.category. GRAIN: 1 CDC event (append-only). SOURCE: bronze CDC topic odoo.res.partner.category
{{ config(
    materialized='incremental',
    incremental_strategy='append',
    on_schema_change='sync_all_columns'
) }}
select
    raw_data:id::number                        as category_id,
    {{ deb_i18n('raw_data:name') }}             as name,
    raw_data:parent_id::number                 as parent_id,
    raw_data:cdc_status::string                 as cdc_status,
    raw_data:is_deleted::boolean                as is_deleted,
    raw_data:_cdc_ts_ms::number                 as _cdc_ts_ms,
    raw_data:_cdc_lsn::number                   as _cdc_lsn,
    raw_data:ingested_at::timestamp_ntz         as ingested_at
from {{ source('bronze', 'res_partner_category') }}
{{ incremental_filter() }}