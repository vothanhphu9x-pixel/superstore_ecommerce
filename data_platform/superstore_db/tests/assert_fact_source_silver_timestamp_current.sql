-- Fact phải giữ đúng Silver processing timestamp của source row hiện hành.
-- Test này bắt trường hợp Silver đã update nhưng Fact incremental chưa reprocess row tương ứng.
select
    'fact_sales' as model_name,
    src.sale_order_line_id as business_key,
    src.silver_updated_at as expected_timestamp,
    fact.source_silver_updated_at as actual_timestamp
from {{ ref('sil_order_lines_enriched') }} src
join {{ ref('fact_sales') }} fact
    on fact.sale_order_line_id = src.sale_order_line_id
where fact.source_silver_updated_at <> src.silver_updated_at

union all

select
    'fact_email_campaign',
    hash(src.email_id),
    src.silver_updated_at,
    fact.source_silver_updated_at
from {{ ref('sil_email_campaigns_enriched') }} src
join {{ ref('fact_email_campaign') }} fact
    on fact.email_id = src.email_id
where fact.source_silver_updated_at <> src.silver_updated_at

union all

select
    'fact_purchase',
    src.purchase_order_line_id,
    src.silver_updated_at,
    fact.source_silver_updated_at
from {{ ref('sil_purchase_order_lines_enriched') }} src
join {{ ref('fact_purchase') }} fact
    on fact.purchase_order_line_id = src.purchase_order_line_id
where fact.source_silver_updated_at <> src.silver_updated_at

union all

select
    'fact_crm_funnel',
    src.crm_lead_id,
    src.silver_updated_at,
    fact.source_silver_updated_at
from {{ ref('sil_crm_lead_enriched') }} src
join {{ ref('fact_crm_funnel') }} fact
    on fact.crm_lead_id = src.crm_lead_id
where fact.source_silver_updated_at <> src.silver_updated_at

union all

select
    'fact_inventory_movement',
    src.stock_move_id,
    src.silver_updated_at,
    fact.source_silver_updated_at
from {{ ref('sil_stock_movement_enriched') }} src
join {{ ref('fact_inventory_movement') }} fact
    on fact.stock_move_id = src.stock_move_id
where fact.source_silver_updated_at <> src.silver_updated_at

union all

select
    'fact_inventory_valuation',
    src.stock_valuation_layer_id,
    src.silver_updated_at,
    fact.source_silver_updated_at
from {{ ref('sil_stock_valuation_enriched') }} src
join {{ ref('fact_inventory_valuation') }} fact
    on fact.stock_valuation_layer_id = src.stock_valuation_layer_id
where fact.source_silver_updated_at <> src.silver_updated_at

union all

select
    'fact_journal_entries',
    src.account_move_line_id,
    src.silver_updated_at,
    fact.source_silver_updated_at
from {{ ref('sil_journal_entries_enriched') }} src
join {{ ref('fact_journal_entries') }} fact
    on fact.account_move_line_id = src.account_move_line_id
where fact.source_silver_updated_at <> src.silver_updated_at

union all

select
    'fact_payment_allocation',
    src.account_partial_reconcile_id,
    src.silver_updated_at,
    fact.source_silver_updated_at
from {{ ref('sil_invoice_payment_status') }} src
join {{ ref('fact_payment_allocation') }} fact
    on fact.account_partial_reconcile_id = src.account_partial_reconcile_id
where fact.source_silver_updated_at <> src.silver_updated_at

union all

select
    'fact_manufacturing',
    src.mrp_production_id,
    src.silver_updated_at,
    fact.source_silver_updated_at
from {{ ref('sil_manufacturing_enriched') }} src
join {{ ref('fact_manufacturing') }} fact
    on fact.mrp_production_id = src.mrp_production_id
where fact.source_silver_updated_at <> src.silver_updated_at

union all

select
    'fact_workorder',
    src.mrp_workorder_id,
    src.silver_updated_at,
    fact.source_silver_updated_at
from {{ ref('sil_workorder_enriched') }} src
join {{ ref('fact_workorder') }} fact
    on fact.mrp_workorder_id = src.mrp_workorder_id
where fact.source_silver_updated_at <> src.silver_updated_at

union all

select
    'fact_manufacturing_oee',
    src.productivity_block_id,
    src.silver_updated_at,
    fact.source_silver_updated_at
from {{ ref('sil_oee_blocks_enriched') }} src
join {{ ref('fact_manufacturing_oee') }} fact
    on fact.productivity_block_id = src.productivity_block_id
where fact.source_silver_updated_at <> src.silver_updated_at

union all

select
    'fact_ad_spend',
    hash(src.campaign_id, src.date, src.channel),
    src.silver_updated_at,
    fact.source_silver_updated_at
from {{ ref('sil_ad_performance_daily_enriched') }} src
join {{ ref('fact_ad_spend') }} fact
    on fact.campaign_id = src.campaign_id
   and fact.spend_date = src.date
   and fact.channel = src.channel
where fact.source_silver_updated_at <> src.silver_updated_at
