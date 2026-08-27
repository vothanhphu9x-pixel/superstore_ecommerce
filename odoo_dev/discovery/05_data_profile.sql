\set ON_ERROR_STOP on

SELECT
    COUNT(*) AS total_partners,
    COUNT(*) FILTER (WHERE customer_rank > 0) AS customers,
    COUNT(*) FILTER (WHERE supplier_rank > 0) AS suppliers,
    COUNT(*) FILTER (
        WHERE email IS NULL OR BTRIM(email) = ''
    ) AS missing_email
FROM res_partner;

SELECT
    COUNT(*) AS product_variants,
    COUNT(*) FILTER (
        WHERE default_code IS NULL OR BTRIM(default_code) = ''
    ) AS missing_sku,
    COUNT(DISTINCT default_code) FILTER (
        WHERE default_code IS NOT NULL
          AND BTRIM(default_code) <> ''
    ) AS distinct_sku
FROM product_product;

SELECT
    state,
    COUNT(*) AS order_count
FROM sale_order
GROUP BY state
ORDER BY state;

SELECT
    state,
    COUNT(*) AS purchase_order_count
FROM purchase_order
GROUP BY state
ORDER BY state;

SELECT
    usage,
    COUNT(*) AS location_count
FROM stock_location
GROUP BY usage
ORDER BY usage;

SELECT
    state,
    COUNT(*) AS stock_move_count
FROM stock_move
GROUP BY state
ORDER BY state;

SELECT
    move_type,
    state,
    COUNT(*) AS accounting_document_count
FROM account_move
GROUP BY move_type, state
ORDER BY move_type, state;

SELECT
    table_name,
    column_name,
    data_type
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name IN (
      'product_template',
      'product_product'
  )
  AND column_name IN (
      'name',
      'default_code',
      'list_price',
      'standard_price',
      'description_sale'
  )
ORDER BY table_name, ordinal_position;

SELECT
    COUNT(*) AS employee_count
FROM hr_employee;

SELECT
    to_regclass('public.sale_commission') IS NOT NULL
        AS custom_commission_table_exists;