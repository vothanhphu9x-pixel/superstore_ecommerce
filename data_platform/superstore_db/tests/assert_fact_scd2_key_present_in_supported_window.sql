-- Chỉ yêu cầu SK khi Silver processing time nằm trong SCD2 window mà dimension thực sự có.
with customer_window as (
    select
        partner_id,
        min(dbt_valid_from) as supported_from,
        max(coalesce(dbt_valid_to, '9999-12-31'::timestamp)) as supported_to
    from {{ ref('dim_customer') }}
    group by partner_id
),
product_window as (
    select
        product_id,
        min(dbt_valid_from) as supported_from,
        max(coalesce(dbt_valid_to, '9999-12-31'::timestamp)) as supported_to
    from {{ ref('dim_product') }}
    group by product_id
),
employee_window as (
    select
        user_id,
        min(dbt_valid_from) as supported_from,
        max(coalesce(dbt_valid_to, '9999-12-31'::timestamp)) as supported_to
    from {{ ref('dim_employee') }}
    where user_id is not null
    group by user_id
)

select 'fact_sales' as model_name, src.sale_order_line_id as business_key, 'customer' as dimension_name
from {{ ref('sil_order_lines_enriched') }} src
join customer_window win on win.partner_id = src.partner_id
left join {{ ref('fact_sales') }} fact on fact.sale_order_line_id = src.sale_order_line_id
where src.silver_updated_at >= win.supported_from
  and src.silver_updated_at < win.supported_to
  and fact.customer_sk is null

union all

select 'fact_sales', src.sale_order_line_id, 'product'
from {{ ref('sil_order_lines_enriched') }} src
join product_window win on win.product_id = src.product_id
left join {{ ref('fact_sales') }} fact on fact.sale_order_line_id = src.sale_order_line_id
where src.silver_updated_at >= win.supported_from
  and src.silver_updated_at < win.supported_to
  and fact.product_sk is null

union all

select 'fact_sales', src.sale_order_line_id, 'employee'
from {{ ref('sil_order_lines_enriched') }} src
join employee_window win on win.user_id = src.user_id
left join {{ ref('fact_sales') }} fact on fact.sale_order_line_id = src.sale_order_line_id
where src.silver_updated_at >= win.supported_from
  and src.silver_updated_at < win.supported_to
  and fact.salesperson_sk is null

union all

select 'fact_purchase', src.purchase_order_line_id, 'vendor'
from {{ ref('sil_purchase_order_lines_enriched') }} src
join customer_window win on win.partner_id = src.partner_id
left join {{ ref('fact_purchase') }} fact
  on fact.purchase_order_line_id = src.purchase_order_line_id
where src.silver_updated_at >= win.supported_from
  and src.silver_updated_at < win.supported_to
  and fact.vendor_sk is null

union all

select 'fact_purchase', src.purchase_order_line_id, 'product'
from {{ ref('sil_purchase_order_lines_enriched') }} src
join product_window win on win.product_id = src.product_id
left join {{ ref('fact_purchase') }} fact
  on fact.purchase_order_line_id = src.purchase_order_line_id
where src.silver_updated_at >= win.supported_from
  and src.silver_updated_at < win.supported_to
  and fact.product_sk is null

union all

select 'fact_purchase', src.purchase_order_line_id, 'employee'
from {{ ref('sil_purchase_order_lines_enriched') }} src
join employee_window win on win.user_id = src.user_id
left join {{ ref('fact_purchase') }} fact
  on fact.purchase_order_line_id = src.purchase_order_line_id
where src.silver_updated_at >= win.supported_from
  and src.silver_updated_at < win.supported_to
  and fact.buyer_sk is null

union all

select 'fact_crm_funnel', src.crm_lead_id, 'customer'
from {{ ref('sil_crm_lead_enriched') }} src
join customer_window win on win.partner_id = src.partner_id
left join {{ ref('fact_crm_funnel') }} fact on fact.crm_lead_id = src.crm_lead_id
where src.silver_updated_at >= win.supported_from
  and src.silver_updated_at < win.supported_to
  and fact.customer_sk is null

union all

select 'fact_inventory_movement', src.stock_move_id, 'product'
from {{ ref('sil_stock_movement_enriched') }} src
join product_window win on win.product_id = src.product_id
left join {{ ref('fact_inventory_movement') }} fact on fact.stock_move_id = src.stock_move_id
where src.silver_updated_at >= win.supported_from
  and src.silver_updated_at < win.supported_to
  and fact.product_sk is null

union all

select 'fact_inventory_valuation', src.stock_valuation_layer_id, 'product'
from {{ ref('sil_stock_valuation_enriched') }} src
join product_window win on win.product_id = src.product_id
left join {{ ref('fact_inventory_valuation') }} fact
  on fact.stock_valuation_layer_id = src.stock_valuation_layer_id
where src.silver_updated_at >= win.supported_from
  and src.silver_updated_at < win.supported_to
  and fact.product_sk is null

union all

select 'fact_journal_entries', src.account_move_line_id, 'customer'
from {{ ref('sil_journal_entries_enriched') }} src
join customer_window win on win.partner_id = src.partner_id
left join {{ ref('fact_journal_entries') }} fact
  on fact.account_move_line_id = src.account_move_line_id
where src.silver_updated_at >= win.supported_from
  and src.silver_updated_at < win.supported_to
  and fact.customer_sk is null

union all

select 'fact_payment_allocation', src.account_partial_reconcile_id, 'customer'
from {{ ref('sil_invoice_payment_status') }} src
join customer_window win on win.partner_id = src.partner_id
left join {{ ref('fact_payment_allocation') }} fact
  on fact.account_partial_reconcile_id = src.account_partial_reconcile_id
where src.silver_updated_at >= win.supported_from
  and src.silver_updated_at < win.supported_to
  and fact.customer_sk is null

union all

select 'fact_manufacturing', src.mrp_production_id, 'product'
from {{ ref('sil_manufacturing_enriched') }} src
join product_window win on win.product_id = src.product_id
left join {{ ref('fact_manufacturing') }} fact
  on fact.mrp_production_id = src.mrp_production_id
where src.silver_updated_at >= win.supported_from
  and src.silver_updated_at < win.supported_to
  and fact.product_sk is null

union all

select 'fact_customer_invoice', src.move_id, 'customer'
from {{ ref('sil_customer_invoices_enriched') }} src
join customer_window win on win.partner_id = src.partner_id
left join {{ ref('fact_customer_invoice') }} fact
  on fact.move_id = src.move_id
where src.silver_updated_at >= win.supported_from
  and src.silver_updated_at < win.supported_to
  and fact.customer_sk is null

union all

select 'fact_inventory_balance', fact.fact_inv_bal_sk, 'product'
from {{ ref('fact_inventory_balance') }} fact
join product_window win on win.product_id = fact.product_id
where fact.snapshot_captured_at >= win.supported_from
  and fact.snapshot_captured_at < win.supported_to
  and fact.product_sk is null
