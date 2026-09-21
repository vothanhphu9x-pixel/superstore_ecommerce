select mart_oee_sk
from {{ ref('mart_oee_by_workcenter_monthly') }}
where productivity_block_count <= 0
   or work_order_count <= 0
   or productive_minutes < 0
   or availability_loss_minutes < 0
   or duration_est_minutes < 0
   or availability_pct not between 0 and 1
   or performance_pct not between 0 and 1
   or quality_pct not between 0 and 1
   or oee_pct not between 0 and 1
   or defect_rate_pct not between 0 and 1
   or abs(oee_pct - availability_pct * performance_pct * quality_pct) > 0.00001
