-- GRAIN   : 1 hàng = 1 account_move_line hiện hành.
-- SOURCE  : silver → sil_journal_entries_enriched.
-- DERIVED : balance_amount = debit_amount - credit_amount.
-- TEST    : unique(fact_je_sk/account_move_line_id), not_null(account_sk/journal_sk),
--           assert_debit_equals_credit (Σ debit = Σ credit theo posted move_id).
-- account_sk/journal_sk resolve qua account_code/journal_code theo thiết kế dimension hiện tại.
-- customer_sk temporal join bằng silver_updated_at, cùng system-time semantic với khoảng
-- dbt_valid_from/dbt_valid_to. src.date chỉ phục vụ reporting; không dùng pit_clamped().
{{ config(
    materialized='incremental',
    incremental_strategy='merge',
    unique_key='account_move_line_id',
    on_schema_change='sync_all_columns'
) }}

select
    {{ dbt_utils.generate_surrogate_key([
        'src.account_move_line_id'
    ]) }} as fact_je_sk,
    src.account_move_line_id,
    src.move_id,
    src.account_id,
    src.partner_id,
    src.journal_id,
    to_number(to_char(src.date, 'YYYYMMDD')) as entry_date_key,
    dc.customer_sk,
    da.account_sk,
    dj.journal_sk,
    src.debit as debit_amount,
    src.credit as credit_amount,
    src.debit - src.credit as balance_amount,
    src.move_type,
    src.move_state,
    src.is_deleted,
    src.ref,
    src.silver_updated_at as source_silver_updated_at,
    src.source_version_key,
    src.line_cdc_ts_ms,
    src.line_cdc_lsn,
    src.move_cdc_ts_ms,
    src.move_cdc_lsn,
    src.account_cdc_ts_ms,
    src.account_cdc_lsn,
    src.journal_cdc_ts_ms,
    src.journal_cdc_lsn,
    dc.dim_updated_at as customer_dim_updated_at
from {{ ref('sil_journal_entries_enriched') }} src
left join {{ ref('dim_account') }} da
    on da.account_code = src.account_code
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
    on tgt.account_move_line_id = src.account_move_line_id
where tgt.account_move_line_id is null
   or src.silver_updated_at > coalesce(
        tgt.source_silver_updated_at,
        '1900-01-01'::timestamp
   )
   or coalesce(src.source_version_key, '__NULL__')
      <> coalesce(tgt.source_version_key, '__NULL__')
   or coalesce(dc.customer_sk, '__NULL__')
      <> coalesce(tgt.customer_sk, '__NULL__')
   or coalesce(da.account_sk, '__NULL__')
      <> coalesce(tgt.account_sk, '__NULL__')
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
