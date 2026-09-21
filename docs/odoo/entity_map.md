# Odoo Entity Map

Discovery target: Odoo 18 Community, PostgreSQL database `superstore_erp`, checked on 2026-09-07.

## Status definitions

- **Verified** — the model is registered when applicable, the PostgreSQL table and stated technical key exist, and the key decision is supported by the current database.
- **Missing** — the expected database object is absent.
- **Uninstalled** — the owning Odoo module is not installed.
- **Decision Needed** — the model/table exists, but a reliable business key still needs a governance decision.
- **Not Applicable** — the entity is intentionally outside the approved scope.

## Entity inventory

| Domain        | Entity                   | Odoo model                         | PostgreSQL table                       | Technical key               | Candidate business key                                                                             | CDC | Status              |
| ------------- | ------------------------ | ---------------------------------- | -------------------------------------- | --------------------------- | -------------------------------------------------------------------------------------------------- | :-: | ------------------- |
| Sales         | Sales order              | `sale.order`                       | `sale_order`                           | `id`                        | `(company_id, name)` — 21,156/21,156 populated and unique in this snapshot                         | Yes | **Verified**        |
| Sales         | Sales order line         | `sale.order.line`                  | `sale_order_line`                      | `id`                        | No stable natural key; use `id`                                                                    | Yes | **Verified**        |
| Finance       | Accounting document      | `account.move`                     | `account_move`                         | `id`                        | `(journal_id, name)` when posted — database partial unique index                                   | Yes | **Verified**        |
| Finance       | Journal line             | `account.move.line`                | `account_move_line`                    | `id`                        | No stable natural key; use `id`                                                                    | Yes | **Verified**        |
| Finance       | Chart of account item    | `account.account`                  | `account_account`                      | `id`                        | None approved; `code_store` is not a constraint-enforced scalar business key                       | Yes | **Decision Needed** |
| Finance       | Accounting journal       | `account.journal`                  | `account_journal`                      | `id`                        | `(company_id, code)` — database unique constraint                                                  | Yes | **Verified**        |
| Finance       | Payment                  | `account.payment`                  | `account_payment`                      | `id`                        | `(company_id, name)` is unique in the current snapshot but not constraint-enforced                 | Yes | **Decision Needed** |
| Finance       | Partial reconciliation   | `account.partial.reconcile`        | `account_partial_reconcile`            | `id`                        | No stable natural key; use `id`                                                                    | Yes | **Verified**        |
| Procurement   | Purchase order           | `purchase.order`                   | `purchase_order`                       | `id`                        | `(company_id, name)` — 2,218/2,218 populated and unique in this snapshot                           | Yes | **Verified**        |
| Procurement   | Purchase order line      | `purchase.order.line`              | `purchase_order_line`                  | `id`                        | No stable natural key; use `id`                                                                    | Yes | **Verified**        |
| Inventory     | Delivery/receipt         | `stock.picking`                    | `stock_picking`                        | `id`                        | `(company_id, name)` — database unique constraint                                                  | Yes | **Verified**        |
| Inventory     | Delivery carrier         | `delivery.carrier`                 | `delivery_carrier`                     | `id`                        | None approved; carrier name is mutable                                                              | Yes | **Decision Needed** |
| Inventory     | Inventory movement       | `stock.move`                       | `stock_move`                           | `id`                        | No stable natural key; use `id`                                                                    | Yes | **Verified**        |
| Inventory     | Stock location           | `stock.location`                   | `stock_location`                       | `id`                        | `(company_id, barcode)` — unique when `barcode` is populated; 35/50 currently populated            | Yes | **Verified**        |
| Inventory     | Stock valuation layer    | `stock.valuation.layer`            | `stock_valuation_layer`                | `id`                        | No stable natural key; use `id`                                                                    | Yes | **Verified**        |
| Inventory     | Current stock            | `stock.quant`                      | `stock_quant`                          | `id`                        | `(product_id, location_id, lot_id, package_id, owner_id, company_id)`                              | Yes | **Verified**        |
| Manufacturing | Manufacturing order      | `mrp.production`                   | `mrp_production`                       | `id`                        | `(company_id, name)` — database unique constraint                                                  | Yes | **Verified**        |
| Manufacturing | Work order               | `mrp.workorder`                    | `mrp_workorder`                        | `id`                        | `(production_id, name)` is unique in the current snapshot but not constraint-enforced              | Yes | **Decision Needed** |
| Manufacturing | Work center              | `mrp.workcenter`                   | `mrp_workcenter`                       | `id`                        | `(company_id, code)` is unique for the current 3 rows but not constraint-enforced                  | Yes | **Decision Needed** |
| Manufacturing | Work-center activity     | `mrp.workcenter.productivity`      | `mrp_workcenter_productivity`          | `id`                        | No stable natural key; use `id`                                                                    | Yes | **Verified**        |
| Manufacturing | Productivity loss reason | `mrp.workcenter.productivity.loss` | `mrp_workcenter_productivity_loss`     | `id`                        | None approved; `name` is not constraint-enforced                                                   | Yes | **Decision Needed** |
| Manufacturing | Scrap order              | `stock.scrap`                      | `stock_scrap`                          | `id`                        | `(company_id, name)` is unique for the current 215 rows but not constraint-enforced                | Yes | **Decision Needed** |
| Manufacturing | Bill of materials        | `mrp.bom`                          | `mrp_bom`                              | `id`                        | None approved; `code` is empty for all 20 current rows                                             | Yes | **Decision Needed** |
| CRM           | Lead/opportunity         | `crm.lead`                         | `crm_lead`                             | `id`                        | None approved; title `name` is not a durable business identifier                                   | Yes | **Decision Needed** |
| CRM           | Pipeline stage           | `crm.stage`                        | `crm_stage`                            | `id`                        | `(team_id, name)` is unique for the current 4 rows but not constraint-enforced                     | Yes | **Decision Needed** |
| CRM           | Lost reason              | `crm.lost.reason`                  | `crm_lost_reason`                      | `id`                        | `name` is unique for the current 3 rows but not constraint-enforced                                | Yes | **Decision Needed** |
| Marketing     | Campaign                 | `utm.campaign`                     | `utm_campaign`                         | `id`                        | `name` — database unique constraint                                                                | Yes | **Verified**        |
| Marketing     | Source                   | `utm.source`                       | `utm_source`                           | `id`                        | `name` — database unique constraint                                                                | Yes | **Verified**        |
| Marketing     | Medium                   | `utm.medium`                       | `utm_medium`                           | `id`                        | `name` — database unique constraint                                                                | Yes | **Verified**        |
| Reference     | Customer/vendor          | `res.partner`                      | `res_partner`                          | `id`                        | Use `id`; customer when `customer_rank > 0`, vendor when `supplier_rank > 0`; do not use `ref`     | Yes | **Verified**        |
| Reference     | Partner category/tag     | `res.partner.category`             | `res_partner_category`                 | `id`                        | None approved; the table has no current rows                                                       | Yes | **Decision Needed** |
| Reference     | Partner-category bridge  | N/A — M2M relation                 | `res_partner_res_partner_category_rel` | `(category_id, partner_id)` | Composite primary key `(category_id, partner_id)`                                                  | Yes | **Verified**        |
| Reference     | Country                  | `res.country`                      | `res_country`                          | `id`                        | `code` — database unique constraint                                                                | Yes | **Verified**        |
| Reference     | Country/state            | `res.country.state`                | `res_country_state`                    | `id`                        | `(country_id, code)` — database unique constraint                                                  | Yes | **Verified**        |
| Reference     | Product definition       | `product.template`                 | `product_template`                     | `id`                        | None approved; `name` is mutable and has no uniqueness constraint                                  | Yes | **Decision Needed** |
| Reference     | Product SKU              | `product.product`                  | `product_product`                      | `id`                        | `default_code` — 454/454 populated and unique in this snapshot; not constraint-enforced            | Yes | **Verified**        |
| Reference     | Product category         | `product.category`                 | `product_category`                     | `id`                        | None approved; `complete_name` is mutable and not constraint-enforced                              | Yes | **Decision Needed** |
| Reference     | Unit of measure          | `uom.uom`                          | `uom_uom`                              | `id`                        | `(category_id, name)` is unique for the current 28 rows but not constraint-enforced                | Yes | **Decision Needed** |
| Reference     | Odoo user                | `res.users`                        | `res_users`                            | `id`                        | `login` — database unique constraint                                                               | Yes | **Verified**        |
| Reference     | Warehouse                | `stock.warehouse`                  | `stock_warehouse`                      | `id`                        | `(company_id, code)` — database unique constraint                                                  | Yes | **Verified**        |
| Reference     | Product image            | `ir.attachment`                    | `ir_attachment`                        | `id`                        | `(res_model, res_id, res_field)` for `product.template`/`image_1920`; polymorphic, not FK-enforced | No  | **Verified**        |
| HR            | Employee                 | `hr.employee`                      | `hr_employee`                          | `id`                        | `work_email` is 46/46 unique in the current snapshot                                               | Yes | **Verified**        |
| HR            | Employment contract      | `hr.contract`                      | `hr_contract`                          | `id`                        | `(employee_id, date_start)` is unique for the current 89 rows                                      | Yes | **Verified**        |
| HR            | Department               | `hr.department`                    | `hr_department`                        | `id`                        | `(company_id, complete_name)` is unique for the current 10 rows but not constraint-enforced        | Yes | **Decision Needed** |
| HR            | Job position             | `hr.job`                           | `hr_job`                               | `id`                        | `(name, company_id, department_id)` — database unique constraint                                   | Yes | **Verified**        |

## Relationship flows

### Commercial, CRM, and marketing

```text
utm_campaign
  ├── crm_lead.campaign_id
  ├── sale_order.campaign_id
  └── account_move.campaign_id

marketing CSV/API source
  └── campaign_id
        └── utm_campaign.id (nối trong dbt/Snowflake, không ghi metric vào Odoo)

utm_source
  ├── crm_lead.source_id
  └── sale_order.source_id

utm_medium
  ├── crm_lead.medium_id
  └── sale_order.medium_id

crm_stage
  └── crm_lead.stage_id

crm_lost_reason
  └── crm_lead.lost_reason_id

crm_lead
  └── sale_order.opportunity_id

res_country
  ├── res_country_state.country_id
  │     └── res_partner.state_id
  └── res_partner.country_id

res_partner_category
  └── res_partner_res_partner_category_rel.category_id

res_partner
  ├── res_partner_res_partner_category_rel.partner_id
  ├── crm_lead.partner_id
  ├── sale_order.partner_id
  │     ├── sale_order_line.order_id
  │     │     ├── product_product via product_id
  │     │     ├── stock_move via sale_line_id
  │     │     └── mrp_production via sale_line_id
  │     └── stock_picking.sale_id
  │           └── stock_move.picking_id
  ├── purchase_order.partner_id
  │     └── purchase_order_line.order_id
  │           ├── product_product via product_id
  │           ├── stock_move via purchase_line_id
  │           └── account_move_line via purchase_line_id
  └── account_move.partner_id
        └── account_move_line.move_id
```

#### CRM lead-to-opportunity lifecycle

```text
crm_lead: new lead
  type = 'lead'
  active = true
  stage_id -> new
       │
       │ Convert to Opportunity
       │ same crm_lead.id
       │ type = 'opportunity'
       │ date_conversion = conversion timestamp
       │ partner_id = selected/created customer, or NULL
       │ user_id/team_id = wizard assignment when selected
       ▼
crm_lead: open opportunity
  type = 'opportunity'
  active = true
  stage_id -> New / Qualified / Proposition / another configured open stage
       ├── Mark Won
       │     stage_id -> crm_stage where is_won = true
       │     probability = automated_probability = 100
       │     date_closed = close timestamp
       │     active remains true
       └── Mark Lost
             active = false
             probability = automated_probability = 0
             date_closed = close timestamp
             lost_reason_id -> crm_lost_reason.id when supplied
             stage_id is retained; Lost is not necessarily a crm_stage row
```

### Product, image, and inventory

```text
product_category
  └── product_template.categ_id

uom_uom
  ├── product_template.uom_id / uom_po_id
  └── mrp_bom.product_uom_id

product_template
  ├── product_product.product_tmpl_id
  │     ├── sale_order_line.product_id
  │     ├── purchase_order_line.product_id
  │     ├── stock_move.product_id
  │     ├── stock_quant.product_id
  │     ├── stock_valuation_layer.product_id
  │     ├── stock_scrap.product_id
  │     ├── account_move_line.product_id
  │     ├── mrp_production.product_id
  │     └── mrp_workorder.product_id
  └── ir_attachment
        res_model = 'product.template'
        res_id = product_template.id
        res_field = 'image_1920'
        (polymorphic link; not a PostgreSQL FK)

stock_warehouse
  ├── sale_order.warehouse_id
  ├── stock_location.warehouse_id
  └── stock_move.warehouse_id

stock_location
  ├── stock_picking.location_id / location_dest_id
  ├── stock_move.location_id / location_dest_id
  ├── stock_quant.location_id
  ├── stock_scrap.location_id / scrap_location_id
  └── mrp_production.location_src_id / location_dest_id

stock_picking
  └── stock_move.picking_id

delivery_carrier
  ├── sale_order.carrier_id
  └── stock_picking.carrier_id

stock_move
  └── stock_valuation_layer.stock_move_id
```

The grain of `stock_quant` is not merely product × location. Lot/serial, package, owner, and company are also part of the identifying tuple when populated.

### Manufacturing

```text
sale_order_line
  └── mrp_production.sale_line_id

mrp_bom
  ├── mrp_production.bom_id
  └── stock_scrap.bom_id

mrp_workcenter
  ├── mrp_workorder.workcenter_id
  └── mrp_workcenter_productivity.workcenter_id

mrp_workcenter_productivity_loss
  └── mrp_workcenter_productivity.loss_id

mrp_production
  ├── mrp_workorder.production_id
  │     ├── mrp_workcenter_productivity via workorder_id
  │     ├── stock_scrap via workorder_id
  │     └── stock_move via workorder_id
  ├── stock_scrap.production_id
  ├── stock_move.production_id                 (finished goods)
  ├── stock_move.raw_material_production_id    (raw materials)
  └── stock_move.created_production_id          (created supply)
```

### Accounting

```text
account_journal
  ├── account_move.journal_id
  ├── account_move_line.journal_id
  └── account_payment.journal_id

account_account
  └── account_move_line.account_id

account_move
  ├── account_move_line.move_id
  │     ├── res_partner via partner_id
  │     ├── product_product via product_id
  │     └── purchase_order_line via purchase_line_id
  ├── account_payment.move_id
  └── stock_valuation_layer.account_move_id

account_move_line
  ├── stock_valuation_layer.account_move_line_id
  ├── account_partial_reconcile.debit_move_id
  └── account_partial_reconcile.credit_move_id
```

#### Customer receipt flow

```text
Customer invoice: account_move (move_type = 'out_invoice')
  └── account_move_line [account_type = 'asset_receivable']
        debit balance
        └── account_partial_reconcile.debit_move_id
              └── account_partial_reconcile.credit_move_id
                    └── account_move_line [payment receivable line]
                          └── account_move [payment journal entry]
                                └── account_payment.move_id
```

#### Vendor payment flow

```text
Vendor bill: account_move (move_type = 'in_invoice')
  └── account_move_line [account_type = 'liability_payable']
        credit balance
        └── account_partial_reconcile.credit_move_id
              └── account_partial_reconcile.debit_move_id
                    └── account_move_line [payment payable line]
                          └── account_move [payment journal entry]
                                └── account_payment.move_id
```

### Human resources

```text
res_users
  └── hr_employee.user_id

hr_department
  ├── hr_employee.department_id
  └── hr_contract.department_id

hr_job
  ├── hr_employee.job_id
  └── hr_contract.job_id

hr_employee
  ├── hr_employee.parent_id / coach_id
  └── hr_contract.employee_id
```

### Relationship population snapshot

| Relationship                                                                | Populated links | Verification note                        |
| --------------------------------------------------------------------------- | --------------: | ---------------------------------------- |
| `crm_lead.campaign_id → utm_campaign.id`                                    |          54,202 | FK verified                              |
| `crm_lead.source_id → utm_source.id`                                        |          51,006 | FK verified                              |
| `crm_lead.medium_id → utm_medium.id`                                        |          50,845 | FK verified                              |
| `crm_lead.stage_id → crm_stage.id`                                          |          84,564 | FK verified                              |
| `crm_lead.partner_id → res_partner.id`                                      |          21,156 | FK verified; customer is optional        |
| `sale_order.campaign_id → utm_campaign.id`                                  |           9,929 | FK verified                              |
| `account_move.campaign_id → utm_campaign.id`                                |           4,870 | FK verified                              |
| `sale_order.opportunity_id → crm_lead.id`                                   |               0 | Current snapshot is open; run generator with `--repair-crm` to backfill |
| `stock_picking.sale_id → sale_order.id`                                     |          21,156 | FK verified                              |
| `stock_move.sale_line_id → sale_order_line.id`                              |          47,705 | FK verified                              |
| `stock_move.purchase_line_id → purchase_order_line.id`                      |          39,880 | FK verified                              |
| `stock_location.warehouse_id → stock_warehouse.id`                          |              40 | FK verified                              |
| `stock_valuation_layer.stock_move_id → stock_move.id`                       |          98,143 | FK verified                              |
| `mrp_production.sale_line_id → sale_order_line.id`                          |               0 | FK exists; not populated in current data |
| `mrp_workorder.production_id → mrp_production.id`                           |           5,121 | FK verified                              |
| `mrp_workcenter_productivity.workorder_id → mrp_workorder.id`               |           5,845 | FK verified                              |
| `mrp_workcenter_productivity.loss_id → mrp_workcenter_productivity_loss.id` |           5,845 | FK verified                              |
| `stock_scrap.production_id → mrp_production.id`                             |             215 | FK verified                              |
| `account_payment.move_id → account_move.id`                                 |          11,108 | FK verified                              |
| `account_partial_reconcile.debit_move_id → account_move_line.id`            |          11,108 | FK verified                              |
| `account_partial_reconcile.credit_move_id → account_move_line.id`           |          11,108 | FK verified                              |
| `product_template.categ_id → product_category.id`                           |             454 | FK verified                              |
| `product_template.uom_id → uom_uom.id`                                      |             454 | FK verified                              |
| `res_partner_res_partner_category_rel.partner_id → res_partner.id`          |               0 | Composite-PK bridge is currently empty   |
| `hr_contract.employee_id → hr_employee.id`                                  |              89 | FK verified                              |
| Product image attachment → `product_template.id`                            |             442 | Polymorphic link; 0 orphan rows          |
