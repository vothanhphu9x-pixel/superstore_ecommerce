-- Delivery KPI không được âm thầm dồn toàn bộ dữ liệu mô phỏng vào Unknown.
select
    stock_move_id
from {{ ref('fact_inventory_movement') }}
where movement_type = 'sale_out'
  and is_deleted = false
  and picking_state = 'done'
  and ship_mode is null
