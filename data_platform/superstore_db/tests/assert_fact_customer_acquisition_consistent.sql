-- Mỗi dòng trả về là một customer acquisition fact vi phạm grain/business rules.
select
    partner_id
from {{ ref('fact_customer_acquisition') }}
where order_count < 1
   or months_active < 1
   or first_order_value_amount < 0
   or ltv_to_date_amount < first_order_value_amount
   or last_order_date_key < acquisition_date_key
   or cac_amount < 0
   or ltv_cac_ratio < 0
   or payback_period_days < 0
   or is_repeat_customer <> (order_count >= 2)
   or is_cac_recovered <> (payback_date_key is not null)
