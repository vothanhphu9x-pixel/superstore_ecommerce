select mart_email_perf_sk
from {{ ref('mart_email_performance') }}
where email_campaign_count <= 0
   or campaign_count < 0
   or sent_count < 0
   or delivered_count < 0
   or open_count < 0
   or click_count < 0
   or bounce_count < 0
   or delivered_count + bounce_count <> sent_count
   or open_count > delivered_count
   or click_count > delivered_count
   or open_pct not between 0 and 1
   or click_pct not between 0 and 1
   or bounce_pct not between 0 and 1
   or ctor not between 0 and 1
   or roas < 0
