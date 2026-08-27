\set ON_ERROR_STOP on

SELECT
    constraints.table_name,
    key_columns.column_name,
    referenced.table_name AS referenced_table,
    referenced.column_name AS referenced_column,
    constraints.constraint_name
FROM information_schema.table_constraints AS constraints
JOIN information_schema.key_column_usage AS key_columns
    ON constraints.constraint_name = key_columns.constraint_name
   AND constraints.table_schema = key_columns.table_schema
JOIN information_schema.constraint_column_usage AS referenced
    ON constraints.constraint_name = referenced.constraint_name
   AND constraints.table_schema = referenced.table_schema
WHERE constraints.table_schema = 'public'
  AND constraints.constraint_type = 'FOREIGN KEY'
  AND constraints.table_name IN (
      'sale_order',
      'sale_order_line',
      'purchase_order',
      'purchase_order_line',
      'product_product',
      'stock_move',
      'stock_quant',
      'account_move',
      'account_move_line',
      'mrp_production',
      'hr_employee',
      'hr_contract'
  )
ORDER BY
    constraints.table_name,
    key_columns.column_name;

SELECT
    'sale_order.partner_id -> res_partner.id' AS relationship,
    COUNT(*) AS orphan_rows
FROM sale_order AS child
LEFT JOIN res_partner AS parent
    ON parent.id = child.partner_id
WHERE child.partner_id IS NOT NULL
  AND parent.id IS NULL

UNION ALL

SELECT
    'sale_order_line.order_id -> sale_order.id',
    COUNT(*)
FROM sale_order_line AS child
LEFT JOIN sale_order AS parent
    ON parent.id = child.order_id
WHERE child.order_id IS NOT NULL
  AND parent.id IS NULL

UNION ALL

SELECT
    'sale_order_line.product_id -> product_product.id',
    COUNT(*)
FROM sale_order_line AS child
LEFT JOIN product_product AS parent
    ON parent.id = child.product_id
WHERE child.product_id IS NOT NULL
  AND parent.id IS NULL

UNION ALL

SELECT
    'product_product.product_tmpl_id -> product_template.id',
    COUNT(*)
FROM product_product AS child
LEFT JOIN product_template AS parent
    ON parent.id = child.product_tmpl_id
WHERE child.product_tmpl_id IS NOT NULL
  AND parent.id IS NULL

UNION ALL

SELECT
    'purchase_order_line.order_id -> purchase_order.id',
    COUNT(*)
FROM purchase_order_line AS child
LEFT JOIN purchase_order AS parent
    ON parent.id = child.order_id
WHERE child.order_id IS NOT NULL
  AND parent.id IS NULL

UNION ALL

SELECT
    'account_move_line.move_id -> account_move.id',
    COUNT(*)
FROM account_move_line AS child
LEFT JOIN account_move AS parent
    ON parent.id = child.move_id
WHERE child.move_id IS NOT NULL
  AND parent.id IS NULL

ORDER BY relationship;