-- 1:1 account_partial_reconcile. GRAIN: 1 payment×invoice allocation. SOURCE: bronze CDC topic
-- odoo.account.partial_reconcile.
-- ⚠️ Ngoại lệ có chủ đích với naming_convention §1 (stg không join 2 source khác nhau), cùng lý
-- do stg_res_users: cột gốc chỉ có debit_move_id/credit_move_id (account_move_line.id) — Odoo
-- KHÔNG có cột payment_id trực tiếp trên bảng này. payment_id/invoice_move_id là cột
-- [derived@staging] qua JOIN account_move_line.move_id = account_payment.move_id, xem note
-- domain-de.dbml FINANCE_AR_PAYMENT. materialized=view, luôn tính lại "current mapping" mới
-- nhất từ cả 3 nguồn (partial_reconcile + move_line + payment đều append-only).
{{ config(materialized='view') }}

with recon_latest as (
    select
        raw_data:id::number                as account_partial_reconcile_id,
        raw_data:debit_move_id::number     as debit_move_id,
        raw_data:credit_move_id::number    as credit_move_id,
        raw_data:amount::number            as amount,
        {{ deb_date('raw_data:max_date') }} as max_date,
        raw_data:is_deleted::boolean       as is_deleted,
        raw_data:_cdc_ts_ms::number        as _cdc_ts_ms,
        raw_data:_cdc_lsn::number          as _cdc_lsn
    from {{ source('bronze', 'account_partial_reconcile') }}
    qualify row_number() over (
        partition by raw_data:id::number
        order by raw_data:_cdc_ts_ms::number desc, raw_data:_cdc_lsn::number desc
    ) = 1
),
aml_move as (
    select account_move_line_id, move_id
    from {{ ref('stg_account_move_line') }}
    qualify row_number() over (partition by account_move_line_id order by _cdc_ts_ms desc, _cdc_lsn desc) = 1
),
payment_moves as (
    select move_id, payment_id
    from {{ ref('stg_account_payment') }}
    qualify row_number() over (partition by move_id order by _cdc_ts_ms desc, _cdc_lsn desc) = 1
)
select
    r.account_partial_reconcile_id,
    r.debit_move_id,
    r.credit_move_id,
    r.amount,
    r.max_date,
    coalesce(pd.payment_id, pc.payment_id)             as payment_id,
    case
        when pd.payment_id is not null then amlc.move_id
        when pc.payment_id is not null then amld.move_id
    end                                                 as invoice_move_id,
    r.is_deleted,
    r._cdc_ts_ms,
    r._cdc_lsn
from recon_latest r
left join aml_move amld        on amld.account_move_line_id = r.debit_move_id
left join aml_move amlc        on amlc.account_move_line_id = r.credit_move_id
left join payment_moves pd     on pd.move_id = amld.move_id
left join payment_moves pc     on pc.move_id = amlc.move_id
