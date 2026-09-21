-- Một picking giao khách có thể có nhiều stock_move, nhưng các thuộc tính header
-- dùng để aggregate delivery phải đồng nhất giữa mọi move của cùng picking.
select
    picking_id
from {{ ref('fact_inventory_movement') }}
where movement_type = 'sale_out'
  and is_deleted = false
  and picking_state = 'done'
  and picking_id is not null
group by picking_id
having count(distinct warehouse_sk) > 1
    or count(distinct ship_mode) > 1
    or count(distinct date_done) > 1
    or count(distinct scheduled_date) > 1
    or count(distinct date_deadline) > 1
