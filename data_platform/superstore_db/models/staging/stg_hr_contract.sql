-- 1:1 hr.contract. GRAIN: 1 CDC event (append-only). SOURCE: bronze CDC topic odoo.hr.contract
{{ config(
    materialized='incremental',
    incremental_strategy='append',
    on_schema_change='sync_all_columns'
) }}
select
    raw_data:id::number                as contract_id,
    raw_data:name::string              as name,
    raw_data:employee_id::number       as employee_id,
    raw_data:wage::number              as wage,
    {{ deb_date('raw_data:date_start') }} as date_start,
    {{ deb_date('raw_data:date_end') }}   as date_end,
    raw_data:state::string             as state,
    raw_data:cdc_status::string        as cdc_status,
    raw_data:is_deleted::boolean       as is_deleted,
    raw_data:_cdc_ts_ms::number        as _cdc_ts_ms,
    raw_data:_cdc_lsn::number          as _cdc_lsn,
    raw_data:ingested_at::timestamp_ntz as ingested_at
from {{ source('bronze', 'hr_contract') }}
{{ incremental_filter() }}
