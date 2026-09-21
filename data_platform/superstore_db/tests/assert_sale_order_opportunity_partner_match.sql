-- Opportunity gắn vào SO phải thuộc cùng partner.
with sale_orders as (
    select distinct order_id, partner_id, opportunity_id
    from {{ ref('sil_order_lines_enriched') }}
    where is_deleted = false
      and opportunity_id is not null
)

select
    so.order_id,
    so.partner_id as sale_partner_id,
    cl.partner_id as opportunity_partner_id
from sale_orders so
join {{ ref('sil_crm_lead_enriched') }} cl
  on so.opportunity_id = cl.crm_lead_id
where cl.is_deleted = false
  and so.partner_id <> cl.partner_id
