-- GRAIN  : 1 channel x 1 month.
-- SOURCE : fact_ad_spend + fact_sales + fact_customer_acquisition.
-- REFRESH: full rebuild để historical attribution/correction cập nhật toàn bộ kỳ liên quan.
{{ config(materialized='table') }}

with spend as (
    select
        fact.fact_ad_spend_sk,
        fact.channel_sk,
        to_number(
            to_char(date_trunc('month', d.date_actual), 'YYYYMMDD')
        ) as month_date_key,
        fact.spend_amount,
        0::number(38, 6) as revenue_attributed_amount,
        0 as new_customers,
        cast(null as varchar) as src_fact_sales_sk,
        cast(null as varchar) as src_fact_cac_sk
    from {{ ref('fact_ad_spend') }} fact
    join {{ ref('dim_date') }} d
        on d.date_key = fact.spend_date_key
),

sales as (
    select
        cast(null as varchar) as fact_ad_spend_sk,
        fact.channel_sk,
        to_number(
            to_char(date_trunc('month', d.date_actual), 'YYYYMMDD')
        ) as month_date_key,
        0::number(38, 6) as spend_amount,
        fact.revenue_amount as revenue_attributed_amount,
        0 as new_customers,
        fact.fact_sales_sk as src_fact_sales_sk,
        cast(null as varchar) as src_fact_cac_sk
    from {{ ref('fact_sales') }} fact
    join {{ ref('dim_date') }} d
        on d.date_key = fact.order_date_key
    where fact.is_deleted = false
      and coalesce(fact.is_cancelled, false) = false
      and fact.order_state in ('sale', 'done')
),

acquisitions as (
    select
        cast(null as varchar) as fact_ad_spend_sk,
        fact.channel_sk,
        to_number(
            to_char(date_trunc('month', d.date_actual), 'YYYYMMDD')
        ) as month_date_key,
        0::number(38, 6) as spend_amount,
        0::number(38, 6) as revenue_attributed_amount,
        1 as new_customers,
        cast(null as varchar) as src_fact_sales_sk,
        fact.fact_cac_sk as src_fact_cac_sk
    from {{ ref('fact_customer_acquisition') }} fact
    join {{ ref('dim_date') }} d
        on d.date_key = fact.acquisition_date_key
),

components as (
    select * from spend
    union all
    select * from sales
    union all
    select * from acquisitions
),

monthly as (
    select
        channel_sk,
        month_date_key,
        min(fact_ad_spend_sk) as src_fact_ad_spend_sk,
        min(src_fact_sales_sk) as src_fact_sales_sk,
        min(src_fact_cac_sk) as src_fact_cac_sk,
        sum(spend_amount) as spend_amount,
        sum(revenue_attributed_amount) as revenue_attributed_amount,
        sum(new_customers) as new_customers
    from components
    group by channel_sk, month_date_key
),

ratios as (
    select
        monthly.*,
        monthly.revenue_attributed_amount
            / nullif(monthly.spend_amount, 0) as roas,
        monthly.spend_amount
            / nullif(monthly.new_customers, 0) as cac_amount
    from monthly
)

select
    {{ dbt_utils.generate_surrogate_key([
        'ratios.channel_sk',
        'ratios.month_date_key'
    ]) }} as mart_roas_sk,
    ratios.src_fact_ad_spend_sk,
    ratios.src_fact_sales_sk,
    ratios.src_fact_cac_sk,
    ratios.channel_sk,
    coalesce(channel.channel_code, 'unattributed') as channel_code,
    ratios.month_date_key,
    ratios.revenue_attributed_amount,
    ratios.spend_amount,
    round(ratios.roas, 6) as roas,
    ratios.new_customers,
    round(ratios.cac_amount, 2) as cac_amount,
    case
        when ratios.spend_amount = 0 then 'no_spend'
        when ratios.roas >= 4 then 'high'
        when ratios.roas >= 2 then 'medium'
        else 'low'
    end as roas_segment
from ratios
left join {{ ref('dim_channel') }} channel
    on channel.channel_sk = ratios.channel_sk
