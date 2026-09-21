select mart_dso_sk
from {{ ref('mart_dso_monthly') }}
where allocation_count <= 0
   or total_allocated_amount <= 0
   or weighted_dso_days is null
