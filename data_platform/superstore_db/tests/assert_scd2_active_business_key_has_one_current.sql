-- Business key còn active ở source phải có đúng một current SCD2 version.
with partner_latest as (
    select *
    from {{ ref('stg_res_partner') }}
    qualify row_number() over (
        partition by partner_id
        order by _cdc_ts_ms desc, _cdc_lsn desc
    ) = 1
),
product_latest as (
    select *
    from {{ ref('stg_product_product') }}
    qualify row_number() over (
        partition by product_id
        order by _cdc_ts_ms desc, _cdc_lsn desc
    ) = 1
),
product_template_latest as (
    select *
    from {{ ref('stg_product_template') }}
    qualify row_number() over (
        partition by product_tmpl_id
        order by _cdc_ts_ms desc, _cdc_lsn desc
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
employee_latest as (
    select *
    from {{ ref('stg_hr_employee') }}
    qualify row_number() over (
        partition by employee_id
        order by _cdc_ts_ms desc, _cdc_lsn desc
    ) = 1
),
checks as (
    select
        'dim_customer' as model_name,
        src.partner_id::varchar as business_key,
        count_if(dim.is_current) as current_count
    from partner_latest src
    left join {{ ref('dim_customer') }} dim
        on dim.partner_id = src.partner_id
    where src.is_deleted = false
      and coalesce(src.active, true)
    group by src.partner_id

    union all

    select
        'dim_product',
        src.product_id::varchar,
        count_if(dim.is_current)
    from product_latest src
    join product_template_latest tmpl
        on tmpl.product_tmpl_id = src.product_tmpl_id
    left join {{ ref('dim_product') }} dim
        on dim.product_id = src.product_id
    where src.is_deleted = false
      and coalesce(src.active, true)
      and tmpl.is_deleted = false
    group by src.product_id

    union all

    select
        'dim_employee',
        src.contract_id::varchar,
        count_if(dim.is_current)
    from contract_latest src
    join employee_latest employee
        on employee.employee_id = src.employee_id
    left join {{ ref('dim_employee') }} dim
        on dim.contract_id = src.contract_id
    where src.is_deleted = false
      and employee.is_deleted = false
      and coalesce(employee.active, true)
    group by src.contract_id
)

select *
from checks
where current_count <> 1
