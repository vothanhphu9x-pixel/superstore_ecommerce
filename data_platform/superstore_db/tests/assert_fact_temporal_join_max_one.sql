-- Mỗi fact source chỉ được match tối đa một version của từng SCD2 dimension.
select 'fact_sales' as model_name, sol.sale_order_line_id as business_key, 'customer' as dimension_name
from {{ ref('sil_order_lines_enriched') }} sol
join {{ ref('dim_customer') }} dim
  on dim.partner_id = sol.partner_id
 and sol.silver_updated_at >= dim.dbt_valid_from
 and sol.silver_updated_at < coalesce(dim.dbt_valid_to, '9999-12-31'::timestamp)
group by 1, 2, 3 having count(*) > 1

union all

select 'fact_sales', sol.sale_order_line_id, 'product'
from {{ ref('sil_order_lines_enriched') }} sol
join {{ ref('dim_product') }} dim
  on dim.product_id = sol.product_id
 and sol.silver_updated_at >= dim.dbt_valid_from
 and sol.silver_updated_at < coalesce(dim.dbt_valid_to, '9999-12-31'::timestamp)
group by 1, 2, 3 having count(*) > 1

union all

select 'fact_sales', sol.sale_order_line_id, 'employee'
from {{ ref('sil_order_lines_enriched') }} sol
join {{ ref('dim_employee') }} dim
  on dim.user_id = sol.user_id
 and sol.silver_updated_at >= dim.dbt_valid_from
 and sol.silver_updated_at < coalesce(dim.dbt_valid_to, '9999-12-31'::timestamp)
group by 1, 2, 3 having count(*) > 1

union all

select 'fact_purchase', src.purchase_order_line_id, 'vendor'
from {{ ref('sil_purchase_order_lines_enriched') }} src
join {{ ref('dim_customer') }} dim
  on dim.partner_id = src.partner_id
 and src.silver_updated_at >= dim.dbt_valid_from
 and src.silver_updated_at < coalesce(dim.dbt_valid_to, '9999-12-31'::timestamp)
group by 1, 2, 3 having count(*) > 1

union all

select 'fact_purchase', src.purchase_order_line_id, 'product'
from {{ ref('sil_purchase_order_lines_enriched') }} src
join {{ ref('dim_product') }} dim
  on dim.product_id = src.product_id
 and src.silver_updated_at >= dim.dbt_valid_from
 and src.silver_updated_at < coalesce(dim.dbt_valid_to, '9999-12-31'::timestamp)
group by 1, 2, 3 having count(*) > 1

union all

select 'fact_purchase', src.purchase_order_line_id, 'employee'
from {{ ref('sil_purchase_order_lines_enriched') }} src
join {{ ref('dim_employee') }} dim
  on dim.user_id = src.user_id
 and src.silver_updated_at >= dim.dbt_valid_from
 and src.silver_updated_at < coalesce(dim.dbt_valid_to, '9999-12-31'::timestamp)
group by 1, 2, 3 having count(*) > 1

union all

select 'fact_crm_funnel', src.crm_lead_id, 'customer'
from {{ ref('sil_crm_lead_enriched') }} src
join {{ ref('dim_customer') }} dim
  on dim.partner_id = src.partner_id
 and src.silver_updated_at >= dim.dbt_valid_from
 and src.silver_updated_at < coalesce(dim.dbt_valid_to, '9999-12-31'::timestamp)
group by 1, 2, 3 having count(*) > 1

union all

select 'fact_inventory_movement', src.stock_move_id, 'product'
from {{ ref('sil_stock_movement_enriched') }} src
join {{ ref('dim_product') }} dim
  on dim.product_id = src.product_id
 and src.silver_updated_at >= dim.dbt_valid_from
 and src.silver_updated_at < coalesce(dim.dbt_valid_to, '9999-12-31'::timestamp)
group by 1, 2, 3 having count(*) > 1

union all

select 'fact_inventory_valuation', src.stock_valuation_layer_id, 'product'
from {{ ref('sil_stock_valuation_enriched') }} src
join {{ ref('dim_product') }} dim
  on dim.product_id = src.product_id
 and src.silver_updated_at >= dim.dbt_valid_from
 and src.silver_updated_at < coalesce(dim.dbt_valid_to, '9999-12-31'::timestamp)
group by 1, 2, 3 having count(*) > 1

union all

select 'fact_journal_entries', src.account_move_line_id, 'customer'
from {{ ref('sil_journal_entries_enriched') }} src
join {{ ref('dim_customer') }} dim
  on dim.partner_id = src.partner_id
 and src.silver_updated_at >= dim.dbt_valid_from
 and src.silver_updated_at < coalesce(dim.dbt_valid_to, '9999-12-31'::timestamp)
group by 1, 2, 3 having count(*) > 1

union all

select 'fact_payment_allocation', src.account_partial_reconcile_id, 'customer'
from {{ ref('sil_invoice_payment_status') }} src
join {{ ref('dim_customer') }} dim
  on dim.partner_id = src.partner_id
 and src.silver_updated_at >= dim.dbt_valid_from
 and src.silver_updated_at < coalesce(dim.dbt_valid_to, '9999-12-31'::timestamp)
group by 1, 2, 3 having count(*) > 1

union all

select 'fact_manufacturing', src.mrp_production_id, 'product'
from {{ ref('sil_manufacturing_enriched') }} src
join {{ ref('dim_product') }} dim
  on dim.product_id = src.product_id
 and src.silver_updated_at >= dim.dbt_valid_from
 and src.silver_updated_at < coalesce(dim.dbt_valid_to, '9999-12-31'::timestamp)
group by 1, 2, 3 having count(*) > 1

union all

select 'fact_customer_invoice', src.move_id, 'customer'
from {{ ref('sil_customer_invoices_enriched') }} src
join {{ ref('dim_customer') }} dim
  on dim.partner_id = src.partner_id
 and src.silver_updated_at >= dim.dbt_valid_from
 and src.silver_updated_at < coalesce(dim.dbt_valid_to, '9999-12-31'::timestamp)
group by 1, 2, 3 having count(*) > 1

union all

select 'fact_inventory_balance', fact.fact_inv_bal_sk, 'product'
from {{ ref('fact_inventory_balance') }} fact
join {{ ref('dim_product') }} dim
  on dim.product_id = fact.product_id
 and fact.snapshot_captured_at >= dim.dbt_valid_from
 and fact.snapshot_captured_at < coalesce(dim.dbt_valid_to, '9999-12-31'::timestamp)
group by 1, 2, 3 having count(*) > 1
