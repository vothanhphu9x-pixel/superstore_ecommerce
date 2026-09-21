-- 1:1 hr.job. GRAIN: 1 CDC event (append-only).
{{ config(
    materialized='incremental',
    incremental_strategy='append',
    on_schema_change='sync_all_columns'
) }}

select
    raw_data:id::number                  as job_id,
    {{ deb_i18n('raw_data:name') }}      as name,
    raw_data:department_id::number       as department_id,
    raw_data:company_id::number          as company_id,
    raw_data:expected_employees::number  as expected_employees,
    raw_data:no_of_employee::number      as employee_count,
    raw_data:no_of_recruitment::number   as recruitment_count,
    raw_data:active::boolean             as active,
    raw_data:cdc_status::string          as cdc_status,
    raw_data:is_deleted::boolean         as is_deleted,
    raw_data:_cdc_ts_ms::number          as _cdc_ts_ms,
    raw_data:_cdc_lsn::number            as _cdc_lsn,
    {{ deb_ts('raw_data:write_date') }}  as write_date,
    raw_data:ingested_at::timestamp_ntz as ingested_at
from {{ source('bronze', 'hr_job') }}
{{ incremental_filter() }}
