-- GRAIN  : 1 email channel x 1 send month.
-- SOURCE : fact_email_campaign.
-- RATIO  : tính lại từ additive counts; không AVG rate của từng blast.
{{ config(materialized='table') }}

with campaigns as (
    select
        fact.*,
        to_number(
            to_char(date_trunc('month', d.date_actual), 'YYYYMMDD')
        ) as month_date_key
    from {{ ref('fact_email_campaign') }} fact
    join {{ ref('dim_date') }} d
        on d.date_key = fact.send_date_key
    where fact.channel_sk is not null
),

monthly as (
    select
        channel_sk,
        month_date_key,
        min(fact_email_sk) as src_fact_email_sk,
        count(*) as email_campaign_count,
        count(distinct campaign_sk) as campaign_count,
        sum(sent) as sent_count,
        sum(delivered) as delivered_count,
        sum(unique_opens) as open_count,
        sum(unique_clicks) as click_count,
        sum(bounced_total) as bounce_count,
        sum(unsubscribes) as unsubscribe_count,
        sum(spam_reports) as spam_report_count,
        sum(conversions) as conversion_count,
        sum(revenue_amount) as revenue_amount,
        sum(cost_amount) as cost_amount
    from campaigns
    group by channel_sk, month_date_key
)

select
    {{ dbt_utils.generate_surrogate_key([
        'monthly.channel_sk',
        'monthly.month_date_key'
    ]) }} as mart_email_perf_sk,
    monthly.src_fact_email_sk,
    monthly.channel_sk,
    monthly.month_date_key,
    monthly.email_campaign_count,
    monthly.campaign_count,
    monthly.sent_count,
    monthly.delivered_count,
    monthly.open_count,
    monthly.click_count,
    monthly.bounce_count,
    monthly.unsubscribe_count,
    monthly.spam_report_count,
    monthly.conversion_count,
    round(monthly.open_count / nullif(monthly.delivered_count, 0), 6) as open_pct,
    round(monthly.click_count / nullif(monthly.delivered_count, 0), 6) as click_pct,
    round(monthly.bounce_count / nullif(monthly.sent_count, 0), 6) as bounce_pct,
    round(monthly.click_count / nullif(monthly.open_count, 0), 6) as ctor,
    monthly.revenue_amount,
    monthly.cost_amount,
    round(monthly.revenue_amount / nullif(monthly.cost_amount, 0), 6) as roas,
    case
        when monthly.delivered_count = 0 then 'no_data'
        when monthly.open_count / nullif(monthly.delivered_count, 0) >= 0.25 then 'high'
        when monthly.open_count / nullif(monthly.delivered_count, 0) >= 0.15 then 'medium'
        else 'low'
    end as open_pct_segment
from monthly
