-- 1:1 uom.uom. GRAIN: 1 CDC event (append-only). SOURCE: bronze CDC topic odoo.uom.uom
{{ config(
    materialized='incremental',
    incremental_strategy='append',
    on_schema_change='sync_all_columns'
) }}
select
    raw_data:id::number                as uom_id,
    {{ deb_i18n('raw_data:name') }}    as name,
    raw_data:cdc_status::string        as cdc_status,
    raw_data:is_deleted::boolean       as is_deleted,
    raw_data:_cdc_ts_ms::number        as _cdc_ts_ms,
    raw_data:_cdc_lsn::number          as _cdc_lsn,
    raw_data:ingested_at::timestamp_ntz as ingested_at
from {{ source('bronze', 'uom_uom') }}
{{ incremental_filter() }}
