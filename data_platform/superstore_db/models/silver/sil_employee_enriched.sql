-- GRAIN: 1 version lịch sử của 1 contract (SCD2).
-- Khi contract boundary hoặc employee/department/job/user mapping đổi,
-- reload toàn bộ versions của contract đó.
{{ config(
    materialized='incremental',
    incremental_strategy='merge',
    unique_key='dbt_scd_id',
    on_schema_change='sync_all_columns',
    full_refresh=false
) }}

{% set target_has_enrichment_key =
    is_incremental() and relation_has_column(this, 'enrichment_version_key')
%}

with employee_latest as (
    select *
    from {{ ref('stg_hr_employee') }}
    qualify row_number() over (
        partition by employee_id
        order by _cdc_ts_ms desc, _cdc_lsn desc
    ) = 1
),
department_latest as (
    select *
    from {{ ref('stg_hr_department') }}
    qualify row_number() over (
        partition by department_id
        order by _cdc_ts_ms desc, _cdc_lsn desc
    ) = 1
),
job_latest as (
    select *
    from {{ ref('stg_hr_job') }}
    qualify row_number() over (
        partition by job_id
        order by _cdc_ts_ms desc, _cdc_lsn desc
    ) = 1
),
users_latest as (
    select *
    from {{ ref('stg_res_users') }}
    qualify row_number() over (
        partition by employee_id
        order by _cdc_ts_ms desc, _cdc_lsn desc, user_id
    ) = 1
),
contract_latest as (
    select *
    from {{ ref('stg_hr_contract') }}
    qualify row_number() over (
        partition by contract_id
        order by _cdc_ts_ms desc, _cdc_lsn desc
    ) = 1
),
first_contract as (
    select employee_id, min(date_start) as first_start
    from contract_latest
    where is_deleted = false
    group by employee_id
),
source_versions as (
    select *
    from {{ ref('snap_hr_contract') }}
    where is_deleted = false
),
source_enriched as (
    select
        snap.*,
        e.employee_id as resolved_employee_id,
        coalesce(e.user_id, ru.user_id) as user_id,
        e.department_id,
        e.name as employee_name,
        iff(d.is_deleted, null, d.name) as department_name,
        coalesce(iff(j.is_deleted, null, j.name), e.job_title) as resolved_job_title,
        e.employee_type,
        (e.is_deleted = false and coalesce(e.active, true)) as employee_is_active,
        fc.first_start,
        {{ dbt_utils.generate_surrogate_key([
            "coalesce(e.name, '__NULL__')",
            "coalesce(e.department_id, -1)",
            "coalesce(d.name, '__NULL__')",
            "coalesce(d.is_deleted, false)",
            "coalesce(j.name, '__NULL__')",
            "coalesce(j.is_deleted, false)",
            "coalesce(e.job_title, '__NULL__')",
            "coalesce(e.employee_type, '__NULL__')",
            "coalesce(e.active, false)",
            "coalesce(e.is_deleted, false)",
            "coalesce(e.user_id, ru.user_id, -1)",
            "coalesce(fc.first_start, '1900-01-01'::date)"
        ]) }} as enrichment_version_key
    from source_versions snap
    join employee_latest e
        on e.employee_id = snap.employee_id
    left join department_latest d
        on d.department_id = e.department_id
    left join job_latest j
        on j.job_id = e.job_id
    left join users_latest ru
        on ru.employee_id = e.employee_id
    left join first_contract fc
        on fc.employee_id = e.employee_id
),
changed_contracts as (
    {% if is_incremental() %}
    select distinct src.contract_id
    from source_enriched src
    left join {{ this }} tgt
        on tgt.dbt_scd_id = src.dbt_scd_id
    where tgt.dbt_scd_id is null
       or coalesce(tgt.dbt_valid_to, '9999-12-31'::timestamp)
          <> coalesce(src.dbt_valid_to, '9999-12-31'::timestamp)
       or coalesce(tgt.is_current, false)
          <> (src.dbt_valid_to is null and src.employee_is_active)
       {% if target_has_enrichment_key %}
       or coalesce(tgt.enrichment_version_key, '__NULL__')
          <> coalesce(src.enrichment_version_key, '__NULL__')
       {% else %}
       -- Rollout lần đầu: target cũ chưa có enrichment_version_key.
       or 1 = 1
       {% endif %}
    {% else %}
    select distinct contract_id
    from source_enriched
    {% endif %}
)

select
    src.dbt_scd_id,
    src.contract_id,
    src.resolved_employee_id as employee_id,
    src.user_id,
    src.department_id,
    src.employee_name,
    src.department_name,
    src.resolved_job_title as job_title,
    src.wage as wage_amount,
    case
        when src.wage < 60000 then 'Low'
        when src.wage < 100000 then 'Mid'
        else 'Senior'
    end as wage_band,
    src.employee_type,
    src.date_start as contract_start,
    src.date_end as contract_end,
    src.first_start as first_contract_start,
    round(
        datediff('day', src.first_start, coalesce(src.date_end, {{ pipeline_today() }})) / 365.25,
        2
    ) as tenure_years,
    src.employee_is_active as is_active,
    (src.dbt_valid_to is null and src.employee_is_active) as is_current,
    src.dbt_valid_from,
    src.dbt_valid_to,
    src._cdc_ts_ms as source_cdc_ts_ms,
    src._cdc_lsn as source_cdc_lsn,
    src.enrichment_version_key,
    {{ pipeline_now() }} as enrichment_updated_at
from source_enriched src
join changed_contracts cc
    on cc.contract_id = src.contract_id
