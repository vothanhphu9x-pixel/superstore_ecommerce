-- Won deal cần có ngày đóng để xác định sales cycle và cohort.
select crm_lead_id
from {{ ref('fact_crm_funnel') }}
where is_won
  and is_deleted = false
  and closed_date_key is null
