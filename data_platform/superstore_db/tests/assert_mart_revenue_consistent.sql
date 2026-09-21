select
    mart_revenue_sk
from {{ ref('mart_revenue_monthly') }}
where sale_line_count <= 0
   or sales_order_count <= 0
   or missing_cost_line_count < 0
   or (
        missing_cost_line_count = 0
        and (
            cogs_amount is null
            or gross_profit_amount is null
            or abs(gross_profit_amount - (revenue_amount - cogs_amount)) > 0.01
        )
   )
   or (
        missing_cost_line_count > 0
        and (cogs_amount is not null or gross_profit_amount is not null)
   )
