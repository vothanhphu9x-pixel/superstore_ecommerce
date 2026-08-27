\set ON_ERROR_STOP on

WITH expected(domain_name, table_name) AS (
    VALUES
        ('sales', 'sale_order'),
        ('sales', 'sale_order_line'),

        ('finance', 'account_move'),
        ('finance', 'account_move_line'),
        ('finance', 'account_account'),
        ('finance', 'account_journal'),
        ('finance', 'account_payment'),
        ('finance', 'account_partial_reconcile'),

        ('procurement', 'purchase_order'),
        ('procurement', 'purchase_order_line'),

        ('inventory', 'stock_move'),
        ('inventory', 'stock_picking'),
        ('inventory', 'stock_location'),
        ('inventory', 'stock_valuation_layer'),
        ('inventory', 'stock_quant'),

        ('manufacturing', 'mrp_production'),
        ('manufacturing', 'mrp_workorder'),
        ('manufacturing', 'stock_scrap'),
        ('manufacturing', 'mrp_workcenter_productivity'),
        ('manufacturing', 'mrp_workcenter'),
        ('manufacturing', 'mrp_workcenter_productivity_loss'),
        ('manufacturing', 'mrp_bom'),

        ('crm', 'crm_lead'),
        ('crm', 'crm_stage'),
        ('crm', 'crm_lost_reason'),

        ('marketing', 'utm_campaign'),
        ('marketing', 'utm_source'),
        ('marketing', 'utm_medium'),

        ('reference', 'res_partner'),
        ('reference', 'res_partner_category'),
        ('reference', 'res_partner_res_partner_category_rel'),
        ('reference', 'res_country'),
        ('reference', 'res_country_state'),
        ('reference', 'product_template'),
        ('reference', 'product_product'),
        ('reference', 'product_category'),
        ('reference', 'uom_uom'),
        ('reference', 'hr_employee'),
        ('reference', 'hr_contract'),
        ('reference', 'hr_department'),
        ('reference', 'hr_job'),
        ('reference', 'res_users'),
        ('reference', 'stock_warehouse')
)
SELECT
    expected.domain_name,
    expected.table_name,
    CASE
        WHEN tables.table_name IS NULL THEN 'missing'
        ELSE 'verified'
    END AS verification_status,
    COALESCE(stats.n_live_tup, 0) AS estimated_rows
FROM expected
LEFT JOIN information_schema.tables AS tables
    ON tables.table_schema = 'public'
   AND tables.table_name = expected.table_name
LEFT JOIN pg_stat_user_tables AS stats
    ON stats.schemaname = 'public'
   AND stats.relname = expected.table_name
ORDER BY expected.domain_name, expected.table_name;