-- Mỗi dòng trả về là một variant có metric hoặc khoảng thời gian không hợp lệ.
select
    fact.variant_id
from {{ ref('fact_ab_test') }} fact
join {{ ref('dim_date') }} start_date
    on start_date.date_key = fact.start_date_key
join {{ ref('dim_date') }} end_date
    on end_date.date_key = fact.end_date_key
where end_date.date_actual < start_date.date_actual
   or fact.duration_days <> datediff(
        'day',
        start_date.date_actual,
        end_date.date_actual
   )
   or fact.budget_amount < 0
   or fact.spend_amount <> fact.budget_amount
   or fact.impressions < 0
   or fact.clicks < 0
   or fact.conversion_count < 0
   or fact.clicks > fact.impressions
   or fact.conversion_count > fact.clicks
   or fact.revenue_amount < 0
   or fact.ctr not between 0 and 1
   or fact.conv_pct not between 0 and 1
   or fact.roas < 0
   or fact.cpa_amount < 0
