-- GRAIN  : 1 customer version x 1 snapshot date.
-- SOURCE : fact_customer_invoice; bao phủ cả invoice chưa từng được thanh toán.
-- SNAPSHOT: MERGE theo customer/date. Khi chạy lại trong ngày, customer vừa tất toán được
--           ghi về 0 thay vì để lại số dư cũ.
{{ config(
    materialized='incremental',
    incremental_strategy='merge',
    unique_key=['customer_sk', 'snapshot_date_key'],
    on_schema_change='sync_all_columns'
) }}

with open_invoices as (
    select
        fact_customer_invoice_sk,
        move_id,
        customer_sk,
        due_date_key,
        outstanding_amount,
        case
            when due_date_key is null then 'unclassified'
            when due.date_actual >= {{ pipeline_today() }} then 'not_due'
            when datediff('day', due.date_actual, {{ pipeline_today() }}) <= 30 then '0-30'
            when datediff('day', due.date_actual, {{ pipeline_today() }}) <= 60 then '31-60'
            when datediff('day', due.date_actual, {{ pipeline_today() }}) <= 90 then '61-90'
            else '90+'
        end as aging_bucket
    from {{ ref('fact_customer_invoice') }} invoice
    left join {{ ref('dim_date') }} due
        on due.date_key = invoice.due_date_key
    where invoice.is_deleted = false
      and invoice.move_type = 'out_invoice'
      and invoice.move_state = 'posted'
      and invoice.outstanding_amount > 0
      and invoice.customer_sk is not null
),

current_balances as (
    select
        customer_sk,
        min(fact_customer_invoice_sk) as src_fact_customer_invoice_sk,
        sum(iff(aging_bucket = 'not_due', outstanding_amount, 0)) as bucket_not_due,
        sum(iff(aging_bucket = '0-30', outstanding_amount, 0)) as bucket_0_30,
        sum(iff(aging_bucket = '31-60', outstanding_amount, 0)) as bucket_31_60,
        sum(iff(aging_bucket = '61-90', outstanding_amount, 0)) as bucket_61_90,
        sum(iff(aging_bucket = '90+', outstanding_amount, 0)) as bucket_over_90,
        sum(iff(aging_bucket = 'unclassified', outstanding_amount, 0)) as bucket_unclassified,
        sum(outstanding_amount) as total_outstanding_amount,
        count(distinct move_id) as invoice_count
    from open_invoices
    group by customer_sk
),

snapshot_customers as (
    select customer_sk
    from current_balances
    {% if is_incremental() %}
    union
    select customer_sk
    from {{ this }}
    where snapshot_date_key = to_number(to_char({{ pipeline_today() }}, 'YYYYMMDD'))
    {% endif %}
)

select
    {{ dbt_utils.generate_surrogate_key([
        'population.customer_sk',
        pipeline_today()
    ]) }} as mart_ar_aging_sk,
    balances.src_fact_customer_invoice_sk,
    population.customer_sk,
    to_number(to_char({{ pipeline_today() }}, 'YYYYMMDD')) as snapshot_date_key,
    {{ pipeline_now() }} as snapshot_captured_at,
    coalesce(balances.bucket_not_due, 0) as bucket_not_due,
    coalesce(balances.bucket_0_30, 0) as bucket_0_30,
    coalesce(balances.bucket_31_60, 0) as bucket_31_60,
    coalesce(balances.bucket_61_90, 0) as bucket_61_90,
    coalesce(balances.bucket_over_90, 0) as bucket_over_90,
    coalesce(balances.bucket_unclassified, 0) as bucket_unclassified,
    coalesce(balances.total_outstanding_amount, 0) as total_outstanding_amount,
    coalesce(balances.invoice_count, 0) as invoice_count
from snapshot_customers population
left join current_balances balances
    on balances.customer_sk = population.customer_sk
