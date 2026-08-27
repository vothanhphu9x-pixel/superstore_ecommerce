# Source of Truth Matrix

| Data/capability          | Operational source of truth         | Analytical source                  | Access strategy                              |
| ------------------------ | ----------------------------------- | ---------------------------------- | -------------------------------------------- |
| Customer business record | Odoo `res_partner`                  | Snowflake customer dimension       | Live read from Odoo                          |
| Product/SKU              | Odoo product tables                 | Snowflake product dimension        | Catalog uses approved analytical fields      |
| Current stock            | Odoo `stock_quant`                  | Latest governed inventory snapshot | Only physical/internal locations             |
| Inventory movement       | Odoo `stock_move`                   | Inventory movement fact            | Completed movements only                     |
| Sales order              | Odoo sales tables                   | Sales fact                         | Customer access filtered by JWT `partner_id` |
| Delivery status          | Odoo `stock_picking`                | Delivery mart                      | Live status from Odoo                        |
| Invoice status           | Odoo `account_move`                 | Finance mart                       | Live customer status from Odoo               |
| Accounting ledger        | Odoo `account_move_line`            | Finance facts/marts                | Posted documents for official reporting      |
| Purchase order           | Odoo purchase tables                | Procurement fact                   | Business writes through Odoo                 |
| Manufacturing            | Odoo MRP tables                     | Manufacturing/OEE facts            | Analytics downstream                         |
| Dashboard KPI            | Derived from Odoo CDC               | Snowflake gold/mart                | Internal read-only                           |
| Customer web identity    | Separate application identity store | Not an Odoo business entity        | Link to verified `partner_id`                |
| Business knowledge       | Approved Markdown documents         | Qdrant snapshot                    | Public/internal content separated            |
| Marketing CSV            | Approved external source            | Snowflake marketing models         | Do not label as Odoo data                    |

## Governing principle

Odoo is the operational source of truth.

Snowflake is the analytical source of truth.

Snowflake must not be used for current customer ownership, current order status,
current delivery status or current invoice status.
