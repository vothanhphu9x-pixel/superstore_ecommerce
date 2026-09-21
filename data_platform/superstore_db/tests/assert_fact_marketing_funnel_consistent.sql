-- Mỗi dòng trả về là một channel-month có count/cost/rate không nhất quán.
select
    month_date_key,
    channel_sk
from {{ ref('fact_marketing_funnel') }}
where reach is not null
   or impressions < 0
   or source_daily_reach_sum < 0
   or clicks < 0
   or platform_leads < 0
   or platform_conversions < 0
   or leads < 0
   or opportunities < 0
   or won_opportunities < 0
   or conversions < 0
   or confirmed_orders < 0
   or new_customers < 0
   or spend_amount < 0
   or clicks > impressions
   or opportunities > leads
   or won_opportunities > opportunities
   or conversions > leads
   or ctr not between 0 and 1
   or click_to_lead_pct not between 0 and 1
   or lead_to_opportunity_pct not between 0 and 1
   or win_pct not between 0 and 1
   or lead_to_order_pct not between 0 and 1
   or end_to_end_pct not between 0 and 1
   or cac_amount < 0
   or cpl_amount < 0
   or cpc_amount < 0
   or cpm_amount < 0
