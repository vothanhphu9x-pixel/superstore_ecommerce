-- Current-state CDC rows bị xóa phải cập nhật cờ is_deleted xuống Gold,
-- không được để fact cũ tiếp tục xuất hiện trong Mart.
select 'fact_sales' as model_name, src.sale_order_line_id::varchar as business_key
from {{ ref('sil_order_lines_enriched') }} src
left join {{ ref('fact_sales') }} fact using (sale_order_line_id)
where fact.sale_order_line_id is null
   or coalesce(src.is_deleted, false) <> coalesce(fact.is_deleted, false)

union all
select 'fact_purchase', src.purchase_order_line_id::varchar
from {{ ref('sil_purchase_order_lines_enriched') }} src
left join {{ ref('fact_purchase') }} fact using (purchase_order_line_id)
where fact.purchase_order_line_id is null
   or coalesce(src.is_deleted, false) <> coalesce(fact.is_deleted, false)

union all
select 'fact_crm_funnel', src.crm_lead_id::varchar
from {{ ref('sil_crm_lead_enriched') }} src
left join {{ ref('fact_crm_funnel') }} fact using (crm_lead_id)
where fact.crm_lead_id is null
   or coalesce(src.is_deleted, false) <> coalesce(fact.is_deleted, false)

union all
select 'fact_inventory_movement', src.stock_move_id::varchar
from {{ ref('sil_stock_movement_enriched') }} src
left join {{ ref('fact_inventory_movement') }} fact using (stock_move_id)
where fact.stock_move_id is null
   or coalesce(src.is_deleted, false) <> coalesce(fact.is_deleted, false)

union all
select 'fact_inventory_valuation', src.stock_valuation_layer_id::varchar
from {{ ref('sil_stock_valuation_enriched') }} src
left join {{ ref('fact_inventory_valuation') }} fact using (stock_valuation_layer_id)
where fact.stock_valuation_layer_id is null
   or coalesce(src.is_deleted, false) <> coalesce(fact.is_deleted, false)

union all
select 'fact_journal_entries', src.account_move_line_id::varchar
from {{ ref('sil_journal_entries_enriched') }} src
left join {{ ref('fact_journal_entries') }} fact using (account_move_line_id)
where fact.account_move_line_id is null
   or coalesce(src.is_deleted, false) <> coalesce(fact.is_deleted, false)

union all
select 'fact_payment_allocation', src.account_partial_reconcile_id::varchar
from {{ ref('sil_invoice_payment_status') }} src
left join {{ ref('fact_payment_allocation') }} fact using (account_partial_reconcile_id)
where fact.account_partial_reconcile_id is null
   or coalesce(src.is_deleted, false) <> coalesce(fact.is_deleted, false)

union all
select 'fact_manufacturing', src.mrp_production_id::varchar
from {{ ref('sil_manufacturing_enriched') }} src
left join {{ ref('fact_manufacturing') }} fact using (mrp_production_id)
where fact.mrp_production_id is null
   or coalesce(src.is_deleted, false) <> coalesce(fact.is_deleted, false)

union all
select 'fact_workorder', src.mrp_workorder_id::varchar
from {{ ref('sil_workorder_enriched') }} src
left join {{ ref('fact_workorder') }} fact using (mrp_workorder_id)
where fact.mrp_workorder_id is null
   or coalesce(src.is_deleted, false) <> coalesce(fact.is_deleted, false)

union all
select 'fact_manufacturing_oee', src.productivity_block_id::varchar
from {{ ref('sil_oee_blocks_enriched') }} src
left join {{ ref('fact_manufacturing_oee') }} fact using (productivity_block_id)
where fact.productivity_block_id is null
   or coalesce(src.is_deleted, false) <> coalesce(fact.is_deleted, false)
