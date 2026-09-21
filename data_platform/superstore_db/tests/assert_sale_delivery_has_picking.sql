select
    stock_move_id
from {{ ref('fact_inventory_movement') }}
where movement_type = 'sale_out'
  and is_deleted = false
  and picking_id is null
