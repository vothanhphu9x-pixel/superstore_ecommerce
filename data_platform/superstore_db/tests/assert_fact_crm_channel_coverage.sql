-- CRM funnel cần channel để phân tích conversion theo acquisition source.
select
    crm_lead_id
from {{ ref('fact_crm_funnel') }}
where is_deleted = false
  and channel_sk is null
