-- GRAIN       : 1 commercial customer đã có ít nhất 1 confirmed order.
-- TYPE        : accumulating fact; các metric LTV/order/payback thay đổi theo thời gian.
-- SOURCE      : fact_sales + dim_customer + fact_ad_spend.
-- ATTRIBUTION : campaign/channel của first confirmed order; paid spend cùng ngày được
--               chia đều cho số khách mới cùng campaign × channel × acquisition date.
-- REFRESH     : full table recompute để customer cũ được cập nhật khi có order/spend mới.
{{ config(materialized='table') }}

with sales_lines as (
    select
        dc.commercial_partner_id,
        fs.order_id,
        fs.order_date_key,
        fs.campaign_sk,
        fs.channel_sk,
        fs.revenue_amount
    from {{ ref('fact_sales') }} fs
    join {{ ref('dim_customer') }} dc
        on dc.customer_sk = fs.customer_sk
    where fs.is_deleted = false
      and coalesce(fs.is_cancelled, false) = false
      and fs.order_state in ('sale', 'done')
      and dc.commercial_partner_id is not null
),
orders as (
    select
        commercial_partner_id,
        order_id,
        order_date_key,
        campaign_sk,
        channel_sk,
        sum(revenue_amount) as order_revenue_amount
    from sales_lines
    group by
        commercial_partner_id,
        order_id,
        order_date_key,
        campaign_sk,
        channel_sk
),
ranked_orders as (
    select
        *,
        row_number() over (
            partition by commercial_partner_id
            order by order_date_key, order_id
        ) as customer_order_number,
        sum(order_revenue_amount) over (
            partition by commercial_partner_id
            order by order_date_key, order_id
            rows between unbounded preceding and current row
        ) as cumulative_revenue_amount
    from orders
),
first_orders as (
    select
        commercial_partner_id,
        order_id as first_order_id,
        order_date_key as acquisition_date_key,
        campaign_sk,
        channel_sk,
        order_revenue_amount as first_order_value_amount
    from ranked_orders
    where customer_order_number = 1
),
customer_lifetime as (
    select
        commercial_partner_id,
        count(*) as order_count,
        sum(order_revenue_amount) as ltv_to_date_amount,
        max(order_date_key) as last_order_date_key
    from orders
    group by commercial_partner_id
),
acquisition_cohorts as (
    select
        acquisition_date_key,
        campaign_sk,
        channel_sk,
        count(*) as acquired_customer_count
    from first_orders
    group by acquisition_date_key, campaign_sk, channel_sk
),
ad_spend as (
    select
        spend_date_key,
        campaign_sk,
        channel_sk,
        sum(spend_amount) as spend_amount
    from {{ ref('fact_ad_spend') }}
    group by spend_date_key, campaign_sk, channel_sk
),
attributed_customers as (
    select
        fo.*,
        case
            when fo.campaign_sk is null or fo.channel_sk is null then null
            else ads.spend_amount / nullif(cohort.acquired_customer_count, 0)
        end as cac_amount
    from first_orders fo
    join acquisition_cohorts cohort
        on cohort.acquisition_date_key = fo.acquisition_date_key
       and equal_null(cohort.campaign_sk, fo.campaign_sk)
       and equal_null(cohort.channel_sk, fo.channel_sk)
    left join ad_spend ads
        on ads.spend_date_key = fo.acquisition_date_key
       and ads.campaign_sk = fo.campaign_sk
       and ads.channel_sk = fo.channel_sk
),
payback as (
    select
        acq.commercial_partner_id,
        min(
            case
                when acq.cac_amount is not null
                 and ro.cumulative_revenue_amount >= acq.cac_amount
                    then ro.order_date_key
            end
        ) as payback_date_key
    from attributed_customers acq
    join ranked_orders ro
        on ro.commercial_partner_id = acq.commercial_partner_id
    group by acq.commercial_partner_id
),
current_customers as (
    select
        dc.customer_sk,
        dc.partner_id as commercial_partner_id,
        dc.segment as customer_segment
    from {{ ref('dim_customer') }} dc
    where dc.is_current = true
      and dc.partner_id = dc.commercial_partner_id
)

select
    {{ dbt_utils.generate_surrogate_key([
        'acq.commercial_partner_id'
    ]) }} as fact_cac_sk,
    acq.commercial_partner_id as partner_id,
    dc.customer_sk,
    acq.campaign_sk,
    acq.channel_sk,
    acq.acquisition_date_key,
    to_number(to_char({{ pipeline_today() }}, 'YYYYMMDD')) as as_of_date_key,
    acq.first_order_id,
    dc.customer_segment,
    acq.first_order_value_amount,
    round(acq.cac_amount, 2) as cac_amount,
    life.ltv_to_date_amount,
    life.order_count,
    greatest(
        datediff('month', acquisition_date.date_actual, {{ pipeline_today() }}) + 1,
        1
    ) as months_active,
    round(
        life.order_count * 12.0
        / nullif(
            greatest(
                datediff('month', acquisition_date.date_actual, {{ pipeline_today() }}) + 1,
                1
            ),
            0
        ),
        2
    ) as actual_orders_per_year,
    life.last_order_date_key,
    (life.order_count >= 2) as is_repeat_customer,
    payback.payback_date_key,
    datediff(
        'day',
        acquisition_date.date_actual,
        payback_date.date_actual
    ) as payback_period_days,
    (payback.payback_date_key is not null) as is_cac_recovered,
    round(
        life.ltv_to_date_amount / nullif(acq.cac_amount, 0),
        4
    ) as ltv_cac_ratio,
    'first_order_utm' as attribution_model
from attributed_customers acq
join customer_lifetime life
    on life.commercial_partner_id = acq.commercial_partner_id
join current_customers dc
    on dc.commercial_partner_id = acq.commercial_partner_id
join {{ ref('dim_date') }} acquisition_date
    on acquisition_date.date_key = acq.acquisition_date_key
left join payback
    on payback.commercial_partner_id = acq.commercial_partner_id
left join {{ ref('dim_date') }} payback_date
    on payback_date.date_key = payback.payback_date_key
