-- Paid attribution chỉ hợp lệ khi campaign/channel đó thực sự có ad spend trong ngày order.
with paid_spend as (
    select distinct
        spend_date_key,
        campaign_sk,
        channel_sk
    from {{ ref('fact_ad_spend') }}
    where campaign_sk is not null
      and channel_sk is not null
),
sales_orders as (
    select distinct
        order_id,
        order_date_key,
        campaign_sk,
        channel_sk
    from {{ ref('fact_sales') }}
    where order_state in ('sale', 'done')
      and is_deleted = false
      and coalesce(is_cancelled, false) = false
      and campaign_sk is not null
)

select
    sales.order_id
from sales_orders sales
left join paid_spend spend
    on spend.spend_date_key = sales.order_date_key
   and spend.campaign_sk = sales.campaign_sk
   and spend.channel_sk = sales.channel_sk
where spend.campaign_sk is null
