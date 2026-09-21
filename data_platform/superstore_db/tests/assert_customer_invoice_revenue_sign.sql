-- Invoice dương, credit note âm sau khi chuẩn hóa.
select move_id, move_type, net_revenue_amount
from {{ ref('fact_customer_invoice') }}
where is_deleted = false
  and move_state = 'posted'
  and (
       (move_type = 'out_invoice' and net_revenue_amount < 0)
    or (move_type = 'out_refund' and net_revenue_amount > 0)
  )
