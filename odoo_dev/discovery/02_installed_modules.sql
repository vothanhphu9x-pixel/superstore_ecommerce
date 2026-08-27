\set ON_ERROR_STOP on

WITH expected(module_name) AS (
    VALUES
        ('base'),
        ('contacts'),
        ('product'),
        ('sale_management'),
        ('sale_stock'),
        ('crm'),
        ('purchase'),
        ('purchase_stock'),
        ('stock'),
        ('mrp'),
        ('account'),
        ('hr'),
        ('hr_contract'),
        ('utm')
)
SELECT
    expected.module_name,
    COALESCE(module.state, 'missing') AS state,
    module.latest_version
FROM expected
LEFT JOIN ir_module_module AS module
    ON module.name = expected.module_name
ORDER BY expected.module_name;

SELECT
    name,
    state,
    latest_version
FROM ir_module_module
WHERE state = 'installed'
ORDER BY name;