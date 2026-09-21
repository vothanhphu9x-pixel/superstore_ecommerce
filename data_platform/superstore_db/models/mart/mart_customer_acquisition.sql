-- GRAIN   : 1 acquisition month × 1 acquisition channel.
-- SOURCE  : fact_customer_acquisition (1 row/customer).
-- RATIO   : tính lại từ aggregate; tuyệt đối không AVG ltv_cac_ratio từng customer.
{{ config(materialized='table') }}

with customer_acquisition as (
    select
        to_number(
            to_char(date_trunc('month', d.date_actual), 'YYYYMMDD')
        ) as month_date_key,
        fact.channel_sk,
        fact.first_order_value_amount,
        fact.cac_amount,
        fact.ltv_to_date_amount,
        fact.payback_period_days,
        fact.is_cac_recovered,
        fact.is_repeat_customer,
        fact.as_of_date_key
    from {{ ref('fact_customer_acquisition') }} fact
    join {{ ref('dim_date') }} d
        on d.date_key = fact.acquisition_date_key
),
monthly as (
    select
        month_date_key,
        channel_sk,
        max(as_of_date_key) as as_of_date_key,
        count(*) as new_customer_count,
        count(cac_amount) as attributed_customer_count,
        sum(first_order_value_amount) as total_first_order_value_amount,
        sum(cac_amount) as total_cac_amount,
        sum(ltv_to_date_amount) as total_ltv_amount,
        avg(payback_period_days) as avg_payback_days,
        count_if(is_cac_recovered) as cac_recovered_customer_count,
        count_if(is_repeat_customer) as repeat_customer_count
    from customer_acquisition
    group by month_date_key, channel_sk
)

select
    {{ dbt_utils.generate_surrogate_key([
        'm.month_date_key',
        'm.channel_sk'
    ]) }} as mart_cac_sk,
    m.month_date_key,
    m.channel_sk,
    coalesce(dch.channel_code, 'unattributed') as channel_code,
    m.as_of_date_key,
    m.new_customer_count,
    m.attributed_customer_count,
    m.total_first_order_value_amount,
    m.total_cac_amount,
    m.total_ltv_amount,
    round(
        m.total_ltv_amount / nullif(m.total_cac_amount, 0),
        4
    ) as ltv_cac_ratio,
    round(m.avg_payback_days, 2) as avg_payback_days,
    m.cac_recovered_customer_count,
    round(
        m.cac_recovered_customer_count * 1.0
        / nullif(m.attributed_customer_count, 0),
        4
    ) as cac_recovery_pct,
    m.repeat_customer_count,
    round(
        m.repeat_customer_count * 1.0
        / nullif(m.new_customer_count, 0),
        4
    ) as repeat_customer_pct,
    case
        when m.total_cac_amount is null or m.total_cac_amount = 0 then 'unattributed'
        when m.total_ltv_amount / m.total_cac_amount >= 3 then 'high'
        when m.total_ltv_amount / m.total_cac_amount >= 1 then 'medium'
        else 'low'
    end as ltv_segment
from monthly m
left join {{ ref('dim_channel') }} dch
    on dch.channel_sk = m.channel_sk
