-- 1:1 res.country. GRAIN: 1 CDC event (append-only).
{{ config(
    materialized='incremental',
    incremental_strategy='append',
    on_schema_change='sync_all_columns'
) }}

select
    raw_data:id::number                  as country_id,
    {{ deb_i18n('raw_data:name') }}      as name,
    raw_data:code::string                as code,
    raw_data:phone_code::number          as phone_code,
    raw_data:state_required::boolean     as state_required,
    raw_data:zip_required::boolean       as zip_required,
    raw_data:cdc_status::string          as cdc_status,
    raw_data:is_deleted::boolean         as is_deleted,
    raw_data:_cdc_ts_ms::number          as _cdc_ts_ms,
    raw_data:_cdc_lsn::number            as _cdc_lsn,
    {{ deb_ts('raw_data:write_date') }}  as write_date,
    raw_data:ingested_at::timestamp_ntz as ingested_at
from {{ source('bronze', 'res_country') }}
{{ incremental_filter() }}
