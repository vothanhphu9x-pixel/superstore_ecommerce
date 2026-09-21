-- 1:1 hr.employee. GRAIN: 1 CDC event (append-only). SOURCE: bronze CDC topic odoo.hr.employee
-- ⚠️ domain-de.dbml liệt kê warehouse_code trên bảng này nhưng verify qua information_schema:
-- hr_employee KHÔNG có cột này thật (đúng như doc tự flag "CHƯA XÁC NHẬN") — bỏ hẳn khỏi model.
{{ config(
    materialized='incremental',
    incremental_strategy='append',
    on_schema_change='sync_all_columns'
) }}
select
    raw_data:id::number                as employee_id,
    raw_data:name::string              as name,
    raw_data:department_id::number     as department_id,
    raw_data:job_title::string         as job_title,
    raw_data:job_id::number            as job_id,
    raw_data:user_id::number           as user_id,
    raw_data:employee_type::string     as employee_type,
    raw_data:active::boolean           as active,
    raw_data:cdc_status::string        as cdc_status,
    raw_data:is_deleted::boolean       as is_deleted,
    raw_data:_cdc_ts_ms::number        as _cdc_ts_ms,
    raw_data:_cdc_lsn::number          as _cdc_lsn,
    raw_data:ingested_at::timestamp_ntz as ingested_at
from {{ source('bronze', 'hr_employee') }}
{{ incremental_filter() }}
