-- GRAIN   : 1 customer invoice/refund (account_move) hiện hành.
-- SOURCE  : silver -> sil_customer_invoices_enriched.
-- PURPOSE : invoice lifecycle và open balance; không phụ thuộc việc invoice đã có allocation.
{{ config(
    materialized='incremental',
    incremental_strategy='merge',
    unique_key='move_id',
    on_schema_change='sync_all_columns'
) }}

select
    {{ dbt_utils.generate_surrogate_key(['src.move_id']) }} as fact_customer_invoice_sk,
    src.move_id,
    src.invoice_number,
    src.partner_id,
    src.move_type,
    src.move_state,
    src.payment_state,
    to_number(to_char(src.accounting_date, 'YYYYMMDD')) as accounting_date_key,
    to_number(to_char(src.invoice_date, 'YYYYMMDD')) as invoice_date_key,
    to_number(to_char(src.invoice_date_due, 'YYYYMMDD')) as due_date_key,
    dc.customer_sk,
    src.journal_id,
    src.campaign_id,
    src.currency_id,
    src.company_id,
    case
        when src.move_type = 'out_refund' then -src.amount_untaxed
        else src.amount_untaxed
    end as net_revenue_amount,
    case
        when src.move_type = 'out_refund' then -src.amount_total
        else src.amount_total
    end as invoice_amount,
    case
        when src.move_type = 'out_refund' then -src.amount_residual
        else src.amount_residual
    end as outstanding_amount,
    src.is_deleted,
    src.silver_updated_at as source_silver_updated_at,
    src.source_version_key,
    src._cdc_ts_ms,
    src._cdc_lsn,
    dc.dim_updated_at as customer_dim_updated_at
from {{ ref('sil_customer_invoices_enriched') }} src
left join {{ ref('dim_customer') }} dc
    on dc.partner_id = src.partner_id
   and src.silver_updated_at >= dc.dbt_valid_from
   and src.silver_updated_at < coalesce(
        dc.dbt_valid_to,
        '9999-12-31'::timestamp
   )
{% if is_incremental() %}
left join {{ this }} tgt
    on tgt.move_id = src.move_id
where tgt.move_id is null
   or src.silver_updated_at > coalesce(
        tgt.source_silver_updated_at,
        '1900-01-01'::timestamp
   )
   or coalesce(src.source_version_key, '__NULL__')
      <> coalesce(tgt.source_version_key, '__NULL__')
   or coalesce(dc.customer_sk, '__NULL__')
      <> coalesce(tgt.customer_sk, '__NULL__')
   or coalesce(
        dc.dim_updated_at,
        '1900-01-01'::timestamp
   ) > coalesce(
        tgt.customer_dim_updated_at,
        '1900-01-01'::timestamp
   )
{% endif %}
