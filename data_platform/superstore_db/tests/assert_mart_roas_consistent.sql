select mart_roas_sk
from {{ ref('mart_roas_by_channel') }}
where spend_amount < 0
   or revenue_attributed_amount < 0
   or new_customers < 0
   or (
        spend_amount > 0
        and abs(roas - revenue_attributed_amount / spend_amount) > 0.00001
   )
   or (
        new_customers > 0
        and abs(cac_amount - spend_amount / new_customers) > 0.01
   )
   or (spend_amount = 0 and roas is not null)
