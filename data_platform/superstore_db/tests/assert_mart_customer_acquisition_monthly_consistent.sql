-- Mỗi dòng trả về là một channel-month aggregate không khớp additive measures.
select
    month_date_key,
    channel_sk
from {{ ref('mart_customer_acquisition') }}
where new_customer_count < 1
   or attributed_customer_count > new_customer_count
   or total_first_order_value_amount < 0
   or total_cac_amount < 0
   or total_ltv_amount < total_first_order_value_amount
   or cac_recovered_customer_count > attributed_customer_count
   or repeat_customer_count > new_customer_count
   or cac_recovery_pct not between 0 and 1
   or repeat_customer_pct not between 0 and 1
   or ltv_cac_ratio < 0
