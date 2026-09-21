-- 1:1 crm.stage (lookup nhỏ). GRAIN: 1 CDC event (append-only). SOURCE: bronze CDC topic odoo.crm.stage
{{ config(
    materialized='incremental',
    incremental_strategy='append',
    on_schema_change='sync_all_columns'
) }}
select
    raw_data:id::number                    as stage_id,
    {{ deb_i18n('raw_data:name') }}                  as name,  -- jsonb i18n: crm.stage.name (translate=True)
    raw_data:sequence::number              as sequence,
    -- nguồn thật của fact_crm_funnel.is_won (lead.stage_id.is_won) — KHÔNG có cột is_won trên crm_lead
    raw_data:is_won::boolean               as is_won,
    raw_data:cdc_status::string            as cdc_status,
    raw_data:is_deleted::boolean           as is_deleted,
    raw_data:_cdc_ts_ms::number            as _cdc_ts_ms,
    raw_data:_cdc_lsn::number              as _cdc_lsn,
    raw_data:ingested_at::timestamp_ntz    as ingested_at
from {{ source('bronze', 'crm_stage') }}
{{ incremental_filter() }}
