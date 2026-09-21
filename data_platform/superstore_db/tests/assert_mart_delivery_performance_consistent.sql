select
    mart_delivery_sk
from {{ ref('mart_delivery_performance') }}
where total_deliveries <= 0
   or on_time_count < 0
   or late_count < 0
   or early_count < 0
   or no_sla_count < 0
   or on_time_count + late_count + no_sla_count <> total_deliveries
   or early_count > on_time_count
   or deadline_sla_count + schedule_sla_count + no_sla_count <> total_deliveries
   or on_time_pct not between 0 and 1
   or avg_days_late < 0
