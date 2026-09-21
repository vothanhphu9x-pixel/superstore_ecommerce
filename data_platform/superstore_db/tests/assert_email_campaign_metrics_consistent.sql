-- Mỗi dòng trả về là một email blast có count/rate không hợp lệ.
select
    email_id
from {{ ref('sil_email_campaigns_enriched') }}
where coalesce(sent, -1) < 0
   or coalesce(list_size, -1) < 0
   or coalesce(delivered, -1) < 0
   or coalesce(bounced_total, -1) < 0
   or coalesce(hard_bounce, -1) < 0
   or coalesce(soft_bounce, -1) < 0
   or coalesce(opens, -1) < 0
   or coalesce(unique_opens, -1) < 0
   or coalesce(clicks, -1) < 0
   or coalesce(unique_clicks, -1) < 0
   or coalesce(unsubscribes, -1) < 0
   or coalesce(spam_reports, -1) < 0
   or coalesce(conversions, -1) < 0
   or delivered + bounced_total <> sent
   or hard_bounce + soft_bounce <> bounced_total
   or unique_opens > opens
   or opens > delivered
   or unique_clicks > clicks
   or clicks > delivered
   or conversions > unique_clicks
   or coalesce(deliverability, -1) not between 0 and 1
   or coalesce(open_rate, -1) not between 0 and 1
   or coalesce(ctr, -1) not between 0 and 1
   or coalesce(ctor, -1) not between 0 and 1
   or coalesce(unsubscribe_rate, -1) not between 0 and 1
   or coalesce(revenue_usd, -1) < 0
   or coalesce(cost_usd, -1) < 0
   or coalesce(roas, -1) < 0
   or coalesce(revenue_per_email, -1) < 0
