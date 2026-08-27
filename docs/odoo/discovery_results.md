# Odoo Discovery Results

## Status definitions

- **Verified** — model is registered, its PostgreSQL table and `id` primary key exist, and the stated key decision is supported by the current database.
- **Missing** — the expected database object is absent.
- **Uninstalled** — the owning Odoo module is not installed.
- **Decision Needed** — the model/table exists, but a reliable business key still needs a governance decision.
- **Not Applicable** — the entity is intentionally outside the approved scope.

## Identification

- Jira issue: SUP-62 Validate odoo configuration and establish source-of-truth map
- Discovery date: YYYY-MM-DD
- Odoo edition: Community
- Odoo series: 18.0
- Odoo source commit: `788c2f3f19a3a2c70e2efcc683e21965c634b6de`
- PostgreSQL database: `superstore_erp`
- PostgreSQL user used for discovery: `odoo`

## Runtime verification

| Check               | Result   | Evidence                   |
| ------------------- | -------- | -------------------------- |
| Odoo binary         | verified | `make -C odoo_dev version` |
| Odoo startup        | verified | Startup log                |
| HTTP login          | verified | `GET /web/login`           |
| Database connection | verified | `01_instance_check.sql`    |
| Core module         | verified | `ir_module_module`         |

## Installed modules

| Module          | State     | Version  | Required by scope |
| --------------- | --------- | -------- | ----------------- |
| base            | installed | 18.0.1.3 | Yes               |
| contacts        | installed | 18.0.1.0 | Yes               |
| product         | installed | 18       | Yes               |
| sale_management | installed | 18       | Yes               |
| sale_stock      | installed | 18       | Yes               |
| crm             | installed | 18       | Confirm           |
| purchase        | installed | 18       | Yes               |
| purchase_stock  | installed | 18       | Yes               |
| stock           | installed | 18       | Yes               |
| mrp             | installed | 18       | Yes               |
| account         | installed | 18       | Yes               |
| hr              | installed | 18       | Yes               |
| hr_contract     | installed | 19       | Yes               |
| utm             | installed | 18       | Yes               |

## Entity counts

- Total partners: 2026
- Customers: 2000
- Suppliers: 20
- Partners missing email: 4
- Product variants: 454
- Product variants missing SKU: 0
- Employees: 46
- Sales order states:
  - sale: 20.862
  - cacel: 294
- Purchase order states: 2218
- Stock location usages:
  - internal: 35
  - view: 8
  - inventory: 2
  - transit: 2
  - customer: 1
  - supplier: 1
  - production: 1
- Accounting document states:
  - entry / posted: 11,108
  - in_invoice / posted: 2,218
  - out_invoice / posted: 9,867

## Relationship quality

| Relationship                                            | Orphan rows | Status   |
| ------------------------------------------------------- | ----------: | -------- |
| `sale_order.partner_id → res_partner.id`                |           0 | verified |
| `sale_order_line.order_id → sale_order.id`              |           0 | verified |
| `sale_order_line.product_id → product_product.id`       |           0 | verified |
| `product_product.product_tmpl_id → product_template.id` |           0 | verified |
| `purchase_order_line.order_id → purchase_order.id`      |           0 | verified |
| `account_move_line.move_id → account_move.id`           |           0 | verified |

## Important observations

- Email technical-key suitability: verified
- SKU business-key suitability: verified - `454/454 product variants have SKU`
- Product cost physical table: verified - `product_product (standard_price)`
- Product description availability: missing
- Custom commission table: uninstalled
- Missing expected tables: verified
- Product image source: Verified — stored via `ir_attachment`.

## Unverified assumptions

- None identified.

## Decisions required

- Commission module scope: Decision Needed — commission is not currently an approved business capability.
- Missing module installation: Not Applicable — all required modules are installed.
- External marketing data ownership: Decision Needed — ownership and source-of-truth boundaries for external marketing data are not yet defined.
