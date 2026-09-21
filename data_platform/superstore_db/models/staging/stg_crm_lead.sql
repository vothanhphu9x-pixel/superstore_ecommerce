-- 1:1 crm.lead. GRAIN: 1 CDC event (append-only). SOURCE: bronze CDC topic odoo.crm.lead.
-- Silver dedup theo crm_lead_id trước khi tính funnel.
{{ config(
    materialized='incremental',
    incremental_strategy='append',
    on_schema_change='sync_all_columns'
) }}
select
    raw_data:id::number                    as crm_lead_id,
    raw_data:name::string                  as name,
    raw_data:type::string                  as type,
    raw_data:partner_id::number            as partner_id,
    raw_data:user_id::number               as user_id,
    raw_data:team_id::number               as team_id,
    raw_data:stage_id::number              as stage_id,
    raw_data:campaign_id::number           as campaign_id,
    raw_data:medium_id::number             as medium_id,
    raw_data:source_id::number             as source_id,
    raw_data:probability::number           as probability,
    raw_data:expected_revenue::number      as expected_revenue,
    -- false = lost lead (Odoo dùng active=False, KHÔNG có cột is_lost riêng)
    raw_data:active::boolean               as active,
    {{ deb_ts('raw_data:date_open') }}     as date_open,
    {{ deb_ts('raw_data:date_closed') }}   as date_closed,
    {{ deb_ts('raw_data:date_conversion') }} as date_conversion,
    {{ deb_ts('raw_data:date_last_stage_update') }} as date_last_stage_update,
    {{ deb_ts('raw_data:create_date') }}   as create_date,
    raw_data:lost_reason_id::number        as lost_reason_id,
    raw_data:cdc_status::string            as cdc_status,
    raw_data:is_deleted::boolean           as is_deleted,
    raw_data:_cdc_ts_ms::number            as _cdc_ts_ms,
    raw_data:_cdc_lsn::number              as _cdc_lsn,
    {{ deb_ts('raw_data:write_date') }}    as write_date,
    raw_data:ingested_at::timestamp_ntz    as ingested_at
from {{ source('bronze', 'crm_lead') }}
{{ incremental_filter() }}
