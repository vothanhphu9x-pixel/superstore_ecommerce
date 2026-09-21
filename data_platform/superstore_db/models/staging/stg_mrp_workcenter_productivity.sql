-- 1:1 mrp.workcenter.productivity. GRAIN: 1 CDC event (append-only) — block-grain, nguồn OEE gốc.
-- SOURCE: bronze CDC topic odoo.mrp.workcenter.productivity.
-- sil_oee_blocks_enriched giữ block-grain; sil_workorder_enriched tổng hợp block productive.
{{ config(
    materialized='incremental',
    incremental_strategy='append',
    on_schema_change='sync_all_columns'
) }}
select
    raw_data:id::number                    as productivity_block_id,
    raw_data:workorder_id::number          as workorder_id,
    raw_data:workcenter_id::number         as workcenter_id,
    raw_data:loss_id::number               as loss_id,
    {{ deb_ts('raw_data:date_start') }}    as date_start,
    {{ deb_ts('raw_data:date_end') }}      as date_end,
    raw_data:duration::number              as duration,
    raw_data:cdc_status::string            as cdc_status,
    raw_data:is_deleted::boolean           as is_deleted,
    raw_data:_cdc_ts_ms::number            as _cdc_ts_ms,
    raw_data:_cdc_lsn::number              as _cdc_lsn,
    raw_data:ingested_at::timestamp_ntz    as ingested_at
from {{ source('bronze', 'mrp_workcenter_productivity') }}
{{ incremental_filter() }}
