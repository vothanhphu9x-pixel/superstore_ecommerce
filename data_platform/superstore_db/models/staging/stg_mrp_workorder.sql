-- 1:1 mrp.workorder. GRAIN: 1 CDC event (append-only). SOURCE: bronze CDC topic odoo.mrp.workorder
{{ config(
    materialized='incremental',
    incremental_strategy='append',
    on_schema_change='sync_all_columns'
) }}
select
    raw_data:id::number                    as mrp_workorder_id,
    raw_data:name::string                  as name,
    raw_data:production_id::number         as production_id,
    raw_data:workcenter_id::number         as workcenter_id,
    raw_data:state::string                 as state,
    {{ deb_ts('raw_data:date_start') }}    as date_start,
    {{ deb_ts('raw_data:date_finished') }} as date_finished,
    raw_data:duration_expected::number     as duration_expected,
    raw_data:qty_produced::number          as qty_produced,
    -- field thật tên 'duration', KHÔNG phải 'duration_actual' (domain-de.dbml note)
    raw_data:duration::number              as duration,
    raw_data:cdc_status::string            as cdc_status,
    raw_data:is_deleted::boolean           as is_deleted,
    raw_data:_cdc_ts_ms::number            as _cdc_ts_ms,
    raw_data:_cdc_lsn::number              as _cdc_lsn,
    raw_data:ingested_at::timestamp_ntz    as ingested_at
from {{ source('bronze', 'mrp_workorder') }}
{{ incremental_filter() }}
