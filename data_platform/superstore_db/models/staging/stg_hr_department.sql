-- 1:1 hr.department. GRAIN: 1 CDC event (append-only). SOURCE: bronze CDC topic odoo.hr.department
{{ config(
    materialized='incremental',
    incremental_strategy='append',
    on_schema_change='sync_all_columns'
) }}
select
    raw_data:id::number                as department_id,
    {{ deb_i18n('raw_data:name') }}    as name,
    raw_data:manager_id::number        as manager_id,
    raw_data:cdc_status::string        as cdc_status,
    raw_data:is_deleted::boolean       as is_deleted,
    raw_data:_cdc_ts_ms::number        as _cdc_ts_ms,
    raw_data:_cdc_lsn::number          as _cdc_lsn,
    raw_data:ingested_at::timestamp_ntz as ingested_at
from {{ source('bronze', 'hr_department') }}
{{ incremental_filter() }}
