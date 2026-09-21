-- GRAIN: 1 account_partial_reconcile hiện hành = 1 allocation nối payment line với invoice line.
-- CDC của reconcile/invoice/payment/journal chỉ dùng phát hiện thay đổi.
-- silver_updated_at chỉ đổi khi source_version_key hoặc aging_bucket thực sự đổi.
-- invoice_date/payment_date là business time, không dùng để chọn version SCD2.
{{ config(
    materialized='incremental',
    incremental_strategy='merge',
    unique_key='account_partial_reconcile_id',
    on_schema_change='sync_all_columns'
) }}

with invoice_latest as (
    select *
    from {{ ref('stg_account_move') }}
    qualify row_number() over (
        partition by move_id
        order by _cdc_ts_ms desc, _cdc_lsn desc
    ) = 1
),
payment_latest as (
    select *
    from {{ ref('stg_account_payment') }}
    qualify row_number() over (
        partition by payment_id
        order by _cdc_ts_ms desc, _cdc_lsn desc
    ) = 1
),
journal_latest as (
    select *
    from {{ ref('stg_account_journal') }}
    qualify row_number() over (
        partition by journal_id
        order by _cdc_ts_ms desc, _cdc_lsn desc
    ) = 1
),
source_base as (
    select
        r.account_partial_reconcile_id,
        r.debit_move_id,
        r.credit_move_id,
        r.payment_id,
        r.invoice_move_id,
        r.amount,
        r.max_date,
        inv.amount_total as invoice_amount,
        inv.move_type as invoice_move_type,
        inv.invoice_date,
        inv.invoice_date_due,
        inv.amount_residual as outstanding_amount,
        p.date as payment_date,
        p.partner_id,
        p.journal_id,
        p.payment_type,
        p.state as payment_state,
        jr.code as journal_code,
        (
            coalesce(r.is_deleted, false)
            or coalesce(inv.is_deleted, false)
            or coalesce(p.is_deleted, false)
        ) as is_deleted,
        r._cdc_ts_ms as reconcile_cdc_ts_ms,
        r._cdc_lsn as reconcile_cdc_lsn,
        inv._cdc_ts_ms as invoice_cdc_ts_ms,
        inv._cdc_lsn as invoice_cdc_lsn,
        p._cdc_ts_ms as payment_cdc_ts_ms,
        p._cdc_lsn as payment_cdc_lsn,
        jr._cdc_ts_ms as journal_cdc_ts_ms,
        jr._cdc_lsn as journal_cdc_lsn
    from {{ ref('stg_account_partial_reconcile') }} r
    left join invoice_latest inv
        on inv.move_id = r.invoice_move_id
    left join payment_latest p
        on p.payment_id = r.payment_id
    left join journal_latest jr
        on jr.journal_id = p.journal_id
),
derived_rows as (
    select
        src.*,
        case
            when src.outstanding_amount is null
              or src.outstanding_amount <= 0
              or src.invoice_date_due is null
                then null
            when datediff('day', src.invoice_date_due, {{ pipeline_today() }}) < 0
                then 'not_due'
            when datediff('day', src.invoice_date_due, {{ pipeline_today() }}) <= 30
                then '0-30'
            when datediff('day', src.invoice_date_due, {{ pipeline_today() }}) <= 60
                then '31-60'
            when datediff('day', src.invoice_date_due, {{ pipeline_today() }}) <= 90
                then '61-90'
            else '90+'
        end as aging_bucket
    from source_base src
),
source_rows as (
    select
        src.*,
        {{ dbt_utils.generate_surrogate_key([
            'src.reconcile_cdc_ts_ms',
            'src.reconcile_cdc_lsn',
            'src.payment_id',
            'src.invoice_move_id',
            'src.invoice_move_type',
            'src.invoice_cdc_ts_ms',
            'src.invoice_cdc_lsn',
            'src.payment_cdc_ts_ms',
            'src.payment_cdc_lsn',
            'src.journal_cdc_ts_ms',
            'src.journal_cdc_lsn',
            'src.aging_bucket'
        ]) }} as source_version_key
    from derived_rows src
),
changed_rows as (
    select src.*
    from source_rows src
    {% if is_incremental() %}
    left join {{ this }} tgt
        on tgt.account_partial_reconcile_id = src.account_partial_reconcile_id
    where tgt.account_partial_reconcile_id is null
       or coalesce(src.source_version_key, '__NULL__')
          <> coalesce(tgt.source_version_key, '__NULL__')
    {% endif %}
)

select
    src.*,
    {{ pipeline_now() }} as silver_updated_at
from changed_rows src
