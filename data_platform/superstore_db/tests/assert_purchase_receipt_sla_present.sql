-- PO line đã nhận hàng phải resolve được receipt date, warehouse và trạng thái late.
select
    purchase_order_line_id
from {{ ref('fact_purchase') }}
where qty_received > 0
  and is_deleted = false
  and (
      received_date_key is null
      or warehouse_sk is null
      or days_vs_planned is null
      or days_late is null
      or is_late_delivery is null
  )
