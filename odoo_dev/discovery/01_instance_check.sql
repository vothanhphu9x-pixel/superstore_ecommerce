\set ON_ERROR_STOP on

SELECT
    current_database() AS database_name,
    current_user AS connected_user,
    current_setting('server_version') AS postgres_version;

SELECT
    name AS module_name,
    state,
    latest_version
FROM ir_module_module
WHERE name = 'base';

SELECT
    target.table_name,
    to_regclass('public.' || target.table_name) IS NOT NULL
        AS exists_in_database
FROM (
    VALUES
        ('res_partner'),
        ('product_template'),
        ('product_product'),
        ('sale_order'),
        ('sale_order_line'),
        ('purchase_order'),
        ('purchase_order_line'),
        ('stock_move'),
        ('stock_quant'),
        ('account_move'),
        ('account_move_line'),
        ('mrp_production'),
        ('hr_employee')
) AS target(table_name)
ORDER BY target.table_name;