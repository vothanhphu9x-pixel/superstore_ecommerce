-- GRAIN   : 1 hàng = 1 account_partial_reconcile allocation.
-- SOURCE  : silver → sil_invoice_payment_status.
-- DERIVED : dso_days = payment_date - invoice_date.
-- TEST    : unique(fact_payment_alloc_sk/account_partial_reconcile_id),
--           not_null(customer_sk/journal_sk/source_silver_updated_at).
-- customer_sk temporal join bằng silver_updated_at, cùng system-time semantic với khoảng
-- dbt_valid_from/dbt_valid_to. Business dates chỉ phục vụ DSO/reporting; không dùng pit_clamped().
{{ config(
    materialized='incremental',
    incremental_strategy='merge',
    unique_key='account_partial_reconcile_id',
    on_schema_change='sync_all_columns'
) }}

select
    {{ dbt_utils.generate_surrogate_key([
        'src.account_partial_reconcile_id'
    ]) }} as fact_payment_alloc_sk,
    src.account_partial_reconcile_id,
    src.payment_id,
    src.invoice_move_id,
    src.invoice_move_type,
    to_number(to_char(src.payment_date, 'YYYYMMDD')) as payment_date_key,
    to_number(to_char(src.invoice_date, 'YYYYMMDD')) as invoice_date_key,
    dc.customer_sk,
    dj.journal_sk,
    src.amount as allocated_amount,
    src.payment_type,
    src.payment_state,
    src.is_deleted,
    datediff('day', src.invoice_date, src.payment_date) as dso_days,
    (
        src.invoice_date_due is not null
        and src.payment_date > src.invoice_date_due
    ) as is_overdue,
    src.outstanding_amount,
    src.aging_bucket,
    src.silver_updated_at as source_silver_updated_at,
    src.source_version_key,
    src.reconcile_cdc_ts_ms,
    src.reconcile_cdc_lsn,
    src.invoice_cdc_ts_ms,
    src.invoice_cdc_lsn,
    src.payment_cdc_ts_ms,
    src.payment_cdc_lsn,
    src.journal_cdc_ts_ms,
    src.journal_cdc_lsn,
    dc.dim_updated_at as customer_dim_updated_at
from {{ ref('sil_invoice_payment_status') }} src
left join {{ ref('dim_journal') }} dj
    on dj.journal_code = src.journal_code
left join {{ ref('dim_customer') }} dc
    on dc.partner_id = src.partner_id
   and src.silver_updated_at >= dc.dbt_valid_from
   and src.silver_updated_at < coalesce(
        dc.dbt_valid_to,
        '9999-12-31'::timestamp
   )
{% if is_incremental() %}
left join {{ this }} tgt
    on tgt.account_partial_reconcile_id = src.account_partial_reconcile_id
where tgt.account_partial_reconcile_id is null
   or src.silver_updated_at > coalesce(
        tgt.source_silver_updated_at,
        '1900-01-01'::timestamp
   )
   or coalesce(src.source_version_key, '__NULL__')
      <> coalesce(tgt.source_version_key, '__NULL__')
   or coalesce(dc.customer_sk, '__NULL__')
      <> coalesce(tgt.customer_sk, '__NULL__')
   or coalesce(dj.journal_sk, '__NULL__')
      <> coalesce(tgt.journal_sk, '__NULL__')
   or coalesce(
        dc.dim_updated_at,
        '1900-01-01'::timestamp
   ) > coalesce(
        tgt.customer_dim_updated_at,
        '1900-01-01'::timestamp
   )
{% endif %}
