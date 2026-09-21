-- GRAIN   : 1 hàng = 1 month × 1 channel.
-- SOURCE  : fact_ad_spend + fact_crm_funnel + fact_sales + fact_customer_acquisition.
-- DERIVED : mọi ratio tính lại từ aggregate; không AVG/pass-through ratio nguồn.
-- MEANING : leads = CRM leads mở trong tháng; conversions = số lead cùng cohort có
--           confirmed order. platform_* giữ riêng để không nhầm platform conversion với ERP order.
-- COHORT  : CRM, linked Sales và customer acquisition quy về tháng mở CRM lead;
--           Ads quy về calendar month vì chưa có impression/click-level identity bridge.
-- REACH   : NULL vì daily reach không cộng được thành monthly unique reach;
--           source_daily_reach_sum chỉ giữ để audit.
-- REFRESH : full recompute vì source Fact có thể correction/backfill lịch sử.
{{ config(materialized='table') }}

with ad_monthly as (
    select
        to_number(
            to_char(date_trunc('month', d.date_actual), 'YYYYMMDD')
        ) as month_date_key,
        ad.channel_sk,
        sum(ad.impressions) as impressions,
        sum(ad.reach) as source_daily_reach_sum,
        sum(ad.clicks) as clicks,
        sum(ad.leads) as platform_leads,
        sum(ad.conversions) as platform_conversions,
        sum(ad.spend_amount) as spend_amount
    from {{ ref('fact_ad_spend') }} ad
    join {{ ref('dim_date') }} d
        on d.date_key = ad.spend_date_key
    group by month_date_key, ad.channel_sk
),
crm_monthly as (
    select
        to_number(
            to_char(date_trunc('month', d.date_actual), 'YYYYMMDD')
        ) as month_date_key,
        crm.channel_sk,
        count(*) as crm_leads,
        count_if(crm.lead_type = 'opportunity') as opportunities,
        count_if(crm.is_won) as won_opportunities
    from {{ ref('fact_crm_funnel') }} crm
    join {{ ref('dim_date') }} d
        on d.date_key = crm.open_date_key
    where crm.is_deleted = false
    group by month_date_key, crm.channel_sk
),
sales_orders as (
    select
        sales.opportunity_id,
        sales.order_id,
        sum(sales.revenue_amount) as revenue_amount
    from {{ ref('fact_sales') }} sales
    where sales.is_deleted = false
      and coalesce(sales.is_cancelled, false) = false
      and sales.order_state in ('sale', 'done')
      and sales.opportunity_id is not null
    group by sales.opportunity_id, sales.order_id
),
attributed_sales_monthly as (
    select
        to_number(
            to_char(date_trunc('month', d.date_actual), 'YYYYMMDD')
        ) as month_date_key,
        crm.channel_sk,
        count(distinct crm.crm_lead_id) as converted_leads,
        count(*) as confirmed_orders,
        sum(sales.revenue_amount) as revenue_amount
    from sales_orders sales
    join {{ ref('fact_crm_funnel') }} crm
        on crm.crm_lead_id = sales.opportunity_id
    join {{ ref('dim_date') }} d
        on d.date_key = crm.open_date_key
    where crm.is_deleted = false
    group by month_date_key, crm.channel_sk
),
acquisition_monthly as (
    select
        to_number(
            to_char(date_trunc('month', d.date_actual), 'YYYYMMDD')
        ) as month_date_key,
        crm.channel_sk,
        count(*) as new_customers
    from {{ ref('fact_customer_acquisition') }} acquisition
    join sales_orders sales
        on sales.order_id = acquisition.first_order_id
    join {{ ref('fact_crm_funnel') }} crm
        on crm.crm_lead_id = sales.opportunity_id
    join {{ ref('dim_date') }} d
        on d.date_key = crm.open_date_key
    where crm.is_deleted = false
    group by month_date_key, crm.channel_sk
),
monthly_components as (
    select
        month_date_key,
        channel_sk,
        impressions,
        source_daily_reach_sum,
        clicks,
        platform_leads,
        platform_conversions,
        0 as crm_leads,
        0 as opportunities,
        0 as won_opportunities,
        0 as converted_leads,
        0 as confirmed_orders,
        0 as new_customers,
        spend_amount,
        0::number(38, 6) as revenue_amount
    from ad_monthly

    union all

    select
        month_date_key,
        channel_sk,
        0, 0, 0, 0, 0,
        crm_leads,
        opportunities,
        won_opportunities,
        0, 0, 0,
        0::number(38, 6),
        0::number(38, 6)
    from crm_monthly

    union all

    select
        month_date_key,
        channel_sk,
        0, 0, 0, 0, 0, 0, 0, 0,
        converted_leads,
        confirmed_orders,
        0,
        0::number(38, 6),
        revenue_amount
    from attributed_sales_monthly

    union all

    select
        month_date_key,
        channel_sk,
        0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
        new_customers,
        0::number(38, 6),
        0::number(38, 6)
    from acquisition_monthly
),
funnel_monthly as (
    select
        month_date_key,
        channel_sk,
        sum(impressions) as impressions,
        sum(source_daily_reach_sum) as source_daily_reach_sum,
        sum(clicks) as clicks,
        sum(platform_leads) as platform_leads,
        sum(platform_conversions) as platform_conversions,
        sum(crm_leads) as leads,
        sum(opportunities) as opportunities,
        sum(won_opportunities) as won_opportunities,
        sum(converted_leads) as conversions,
        sum(confirmed_orders) as confirmed_orders,
        sum(new_customers) as new_customers,
        sum(spend_amount) as spend_amount,
        sum(revenue_amount) as revenue_amount
    from monthly_components
    group by month_date_key, channel_sk
)

select
    {{ dbt_utils.generate_surrogate_key([
        'funnel.month_date_key',
        'funnel.channel_sk'
    ]) }} as fact_funnel_sk,
    funnel.channel_sk,
    coalesce(channel.channel_code, 'unattributed') as channel_code,
    funnel.month_date_key,
    funnel.impressions,
    cast(null as number) as reach,
    funnel.source_daily_reach_sum,
    funnel.clicks,
    funnel.platform_leads,
    funnel.platform_conversions,
    funnel.leads,
    funnel.opportunities,
    funnel.won_opportunities,
    funnel.conversions,
    funnel.confirmed_orders,
    funnel.new_customers,
    funnel.spend_amount,
    funnel.revenue_amount,
    round(funnel.clicks / nullif(funnel.impressions, 0), 6) as ctr,
    round(funnel.leads / nullif(funnel.clicks, 0), 6) as click_to_lead_pct,
    round(funnel.opportunities / nullif(funnel.leads, 0), 6) as lead_to_opportunity_pct,
    round(funnel.won_opportunities / nullif(funnel.opportunities, 0), 6) as win_pct,
    round(funnel.conversions / nullif(funnel.leads, 0), 6) as lead_to_order_pct,
    round(funnel.conversions / nullif(funnel.impressions, 0), 6) as end_to_end_pct,
    round(funnel.revenue_amount / nullif(funnel.spend_amount, 0), 6) as roas,
    round(funnel.spend_amount / nullif(funnel.new_customers, 0), 2) as cac_amount,
    round(funnel.spend_amount / nullif(funnel.leads, 0), 2) as cpl_amount,
    round(funnel.spend_amount / nullif(funnel.clicks, 0), 4) as cpc_amount,
    round(funnel.spend_amount * 1000 / nullif(funnel.impressions, 0), 4) as cpm_amount,
    round(funnel.revenue_amount / nullif(funnel.leads, 0), 2) as revenue_per_lead
from funnel_monthly funnel
left join {{ ref('dim_channel') }} channel
    on channel.channel_sk = funnel.channel_sk
