# Odoo Entity Map

Discovery target: Odoo 18 Community, PostgreSQL database `superstore_erp`, checked on 2026-08-25.

## Status definitions

- **Verified** — model is registered, its PostgreSQL table and `id` primary key exist, and the stated key decision is supported by the current database.
- **Missing** — the expected database object is absent.
- **Uninstalled** — the owning Odoo module is not installed.
- **Decision Needed** — the model/table exists, but a reliable business key still needs a governance decision.
- **Not Applicable** — the entity is intentionally outside the approved scope.

## Entity inventory

| Domain        | Entity              | Odoo model            | PostgreSQL table      | Technical key | Candidate business key                                                                                        | Status              |
| ------------- | ------------------- | --------------------- | --------------------- | ------------- | ------------------------------------------------------------------------------------------------------------- | ------------------- |
| Reference     | Customer/vendor     | `res.partner`         | `res_partner`         | `id`          | Use `id`; customer when `customer_rank > 0`, vendor when `supplier_rank > 0`; one partner may have both roles | **Verified**        |
| Reference     | Odoo user           | `res.users`           | `res_users`           | `id`          | `login` — database unique constraint; 5/5 populated and unique                                                | **Verified**        |
| Reference     | Product definition  | `product.template`    | `product_template`    | `id`          | None approved; `name` is mutable and has no uniqueness constraint                                             | **Decision Needed** |
| Reference     | Product SKU         | `product.product`     | `product_product`     | `id`          | `default_code` — 454/454 populated and unique in this snapshot; not constraint-enforced                       | **Verified**        |
| Reference     | Product image       | `ir.attachment`       | `ir_attachment`       | `id`          | `(res_model, res_id, res_field)` for `product.template`/`image_1920`; polymorphic, not FK-enforced            | **Verified**        |
| Sales         | Sales order         | `sale.order`          | `sale_order`          | `id`          | `(company_id, name)` — 21,156/21,156 populated and unique in this snapshot                                    | **Verified**        |
| Sales         | Sales order line    | `sale.order.line`     | `sale_order_line`     | `id`          | No stable natural key; use `id`                                                                               | **Verified**        |
| Procurement   | Purchase order      | `purchase.order`      | `purchase_order`      | `id`          | `(company_id, name)` — 2,218/2,218 populated and unique in this snapshot                                      | **Verified**        |
| Procurement   | Purchase line       | `purchase.order.line` | `purchase_order_line` | `id`          | No stable natural key; use `id`                                                                               | **Verified**        |
| Inventory     | Delivery/receipt    | `stock.picking`       | `stock_picking`       | `id`          | `(company_id, name)` — database unique constraint                                                             | **Verified**        |
| Inventory     | Inventory movement  | `stock.move`          | `stock_move`          | `id`          | No stable natural key; use `id`                                                                               | **Verified**        |
| Inventory     | Current stock       | `stock.quant`         | `stock_quant`         | `id`          | `(product_id, location_id, lot_id, package_id, owner_id, company_id)` — 3,211/3,211 unique in this snapshot   | **Verified**        |
| Finance       | Accounting document | `account.move`        | `account_move`        | `id`          | `(journal_id, name)` when posted — database partial unique index; 23,193/23,193 valid and unique              | **Verified**        |
| Finance       | Journal line        | `account.move.line`   | `account_move_line`   | `id`          | No stable natural key; use `id`                                                                               | **Verified**        |
| Manufacturing | Manufacturing order | `mrp.production`      | `mrp_production`      | `id`          | `(company_id, name)` — database unique constraint; 1,707/1,707 unique                                         | **Verified**        |
| Manufacturing | Work order          | `mrp.workorder`       | `mrp_workorder`       | `id`          | `(production_id, name)` is unique for 5,121 current rows but is not constraint-enforced                       | **Decision Needed** |
| CRM           | Lead/opportunity    | `crm.lead`            | `crm_lead`            | `id`          | None approved; title `name` is not a durable business identifier                                              | **Decision Needed** |
| HR            | Employee            | `hr.employee`         | `hr_employee`         | `id`          | `work_email` is 46/46 unique now                                                                              | **Verified**        |
| HR            | Employment contract | `hr.contract`         | `hr_contract`         | `id`          | `(employee_id, date_start)` is unique for 89 current rows                                                     | **Verified**        |
| Marketing     | Campaign            | `utm.campaign`        | `utm_campaign`        | `id`          | `name` — database unique constraint; 16/16 populated and unique                                               | **Verified**        |

## Relationship flows

Notation: the parent entity is shown above its children. Labels name the child foreign-key column. All ordinary links below are PostgreSQL foreign keys unless explicitly marked as polymorphic.

### Commercial, CRM, and marketing

```text
utm_campaign
  ├── crm_lead.campaign_id
  ├── sale_order.campaign_id
  └── account_move.campaign_id

crm_lead
  └── sale_order.opportunity_id

res_partner
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
product_template
  ├── product_product.product_tmpl_id
  │     ├── sale_order_line.product_id
  │     ├── purchase_order_line.product_id
  │     ├── stock_move.product_id
  │     ├── stock_quant.product_id
  │     ├── account_move_line.product_id
  │     ├── mrp_production.product_id
  │     └── mrp_workorder.product_id
  └── ir_attachment
        res_model = 'product.template'
        res_id = product_template.id
        res_field = 'image_1920'
        (polymorphic link; not a PostgreSQL FK)

stock_location
  ├── stock_picking.location_id / location_dest_id
  ├── stock_move.location_id / location_dest_id
  ├── stock_quant.location_id
  └── mrp_production.location_src_id / location_dest_id

stock_picking
  └── stock_move.picking_id
```

The grain of `stock_quant` is not merely product × location. Lot/serial, package, owner, and company are also part of the identifying tuple when populated.

### Manufacturing

```text
sale_order_line
  └── mrp_production.sale_line_id

mrp_bom
  └── mrp_production.bom_id

mrp_production
  ├── mrp_workorder.production_id
  │     ├── mrp_workcenter via workcenter_id
  │     └── stock_move via workorder_id
  ├── stock_move.production_id                 (finished goods)
  ├── stock_move.raw_material_production_id    (raw materials)
  └── stock_move.created_production_id          (created supply)
```

### Accounting

```text
account_move
  └── account_move_line.move_id
        ├── account_account via account_id
        ├── account_journal via journal_id
        ├── res_partner via partner_id
        ├── product_product via product_id
        └── purchase_order_line via purchase_line_id
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

| Relationship                                           | Populated links | Verification note                        |
| ------------------------------------------------------ | --------------: | ---------------------------------------- |
| `crm_lead.campaign_id → utm_campaign.id`               |          54,202 | FK verified                              |
| `crm_lead.stage_id → crm_stage.id`                     |          84,564 | FK verified                              |
| `crm_lead.partner_id → res_partner.id`                 |          21,156 | FK verified; customer is optional        |
| `sale_order.campaign_id → utm_campaign.id`             |           9,929 | FK verified                              |
| `account_move.campaign_id → utm_campaign.id`           |           4,870 | FK verified                              |
| `sale_order.opportunity_id → crm_lead.id`              |               0 | FK exists; not populated in current data |
| `stock_picking.sale_id → sale_order.id`                |          21,156 | FK verified                              |
| `stock_move.sale_line_id → sale_order_line.id`         |          47,705 | FK verified                              |
| `stock_move.purchase_line_id → purchase_order_line.id` |          39,880 | FK verified                              |
| `mrp_production.sale_line_id → sale_order_line.id`     |               0 | FK exists; not populated in current data |
| `mrp_workorder.production_id → mrp_production.id`      |           5,121 | FK verified                              |
| `hr_contract.employee_id → hr_employee.id`             |              89 | FK verified                              |
| Product image attachment → `product_template.id`       |             442 | Polymorphic link; 0 orphan rows          |
