-- [+] 1:1 res.users — cầu nối sale_order.user_id / purchase_order.user_id → hr_employee.id,
-- cứu dim_employee khỏi mồ côi/orphan FK. SOURCE: bronze CDC topic odoo.res.users
-- ⚠️ Ngoại lệ có chủ đích với naming_convention §1 (stg không join 2 source khác nhau) VÀ với
-- pattern append-only chung: model này luôn tính lại "current mapping" mới nhất từ cả 2 phía
-- (res_users + hr_employee đều append-only), KHÔNG phải incremental — employee_id là cột
-- [derived@staging], res.users KHÔNG có cột employee_id trực tiếp.
{{ config(materialized='view') }}
select
    ru.user_id,
    ru.login,
    ru.partner_id,
    he.employee_id,
    greatest(ru._cdc_ts_ms, coalesce(he._cdc_ts_ms, 0)) as _cdc_ts_ms,
    greatest(ru._cdc_lsn, coalesce(he._cdc_lsn, 0)) as _cdc_lsn
from (
    select
        raw_data:id::number                as user_id,
        raw_data:login::string             as login,
        raw_data:partner_id::number        as partner_id,
        raw_data:is_deleted::boolean       as is_deleted,
        raw_data:_cdc_ts_ms::number        as _cdc_ts_ms,
        raw_data:_cdc_lsn::number          as _cdc_lsn
    from {{ source('bronze', 'res_users') }}
    qualify row_number() over (
        partition by raw_data:id::number
        order by raw_data:_cdc_ts_ms::number desc, raw_data:_cdc_lsn::number desc
    ) = 1
) ru
left join (
    select employee_id, user_id, _cdc_ts_ms, _cdc_lsn
    from {{ ref('stg_hr_employee') }}
    where is_deleted = false
    qualify row_number() over (
        partition by employee_id order by _cdc_ts_ms desc, _cdc_lsn desc
    ) = 1
) he on he.user_id = ru.user_id
where ru.is_deleted = false
