-- GRAIN  : 1 customer version x 1 payment month.
-- SOURCE : fact_payment_allocation.
-- DSO    : weighted average theo allocated_amount; chỉ customer invoice/inbound payment.
{{ config(materialized='table') }}

with allocations as (
    select
        fact.fact_payment_alloc_sk,
        fact.customer_sk,
        to_number(
            to_char(date_trunc('month', d.date_actual), 'YYYYMMDD')
        ) as month_date_key,
        fact.allocated_amount,
        fact.dso_days
    from {{ ref('fact_payment_allocation') }} fact
    join {{ ref('dim_date') }} d
        on d.date_key = fact.payment_date_key
    where fact.is_deleted = false
      and fact.customer_sk is not null
      and fact.invoice_move_type = 'out_invoice'
      and fact.payment_type = 'inbound'
      and fact.dso_days is not null
      and fact.allocated_amount > 0
),

monthly as (
    select
        customer_sk,
        month_date_key,
        min(fact_payment_alloc_sk) as src_fact_payment_alloc_sk,
        count(*) as allocation_count,
        sum(allocated_amount) as total_allocated_amount,
        sum(dso_days * allocated_amount)
            / nullif(sum(allocated_amount), 0) as weighted_dso_days
    from allocations
    group by customer_sk, month_date_key
)

select
    {{ dbt_utils.generate_surrogate_key([
        'monthly.customer_sk',
        'monthly.month_date_key'
    ]) }} as mart_dso_sk,
    monthly.src_fact_payment_alloc_sk,
    monthly.customer_sk,
    monthly.month_date_key,
    monthly.allocation_count,
    monthly.total_allocated_amount,
    round(monthly.weighted_dso_days, 2) as weighted_dso_days
from monthly
