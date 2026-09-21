select
    mart_vendor_perf_sk
from {{ ref('mart_vendor_performance') }}
where purchase_line_count <= 0
   or po_count <= 0
   or product_qty < 0
   or qty_received < 0
   or fill_rate_pct < 0
   or received_line_count < 0
   or late_count < 0
   or on_time_count < 0
   or unmeasured_line_count < 0
   or received_line_count > purchase_line_count
   or on_time_count + late_count + unmeasured_line_count <> purchase_line_count
   or receipt_coverage_pct < 0
   or receipt_coverage_pct > 1
   or on_time_delivery_pct < 0
   or on_time_delivery_pct > 1
   or late_delivery_pct < 0
   or late_delivery_pct > 1
   or late_measurement_status not in ('available', 'partial', 'not_available')
