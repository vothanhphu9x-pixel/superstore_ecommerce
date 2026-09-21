-- GRAIN: 1 mrp_workcenter_productivity block hiện hành.
-- Enrich loss type, Work Order và MO/scrap nhưng không aggregate OEE tại đây.
-- silver_updated_at chỉ đổi khi một source ảnh hưởng tới block thực sự đổi.
{{ config(
    materialized='incremental',
    incremental_strategy='merge',
    unique_key='productivity_block_id',
    on_schema_change='sync_all_columns',
    full_refresh=false
) }}

with block_latest as (
    select *
    from {{ ref('stg_mrp_workcenter_productivity') }}
    qualify row_number() over (
        partition by productivity_block_id
        order by _cdc_ts_ms desc, _cdc_lsn desc
    ) = 1
),
loss_latest as (
    select *
    from {{ ref('stg_mrp_workcenter_productivity_loss') }}
    qualify row_number() over (
        partition by loss_id
        order by _cdc_ts_ms desc, _cdc_lsn desc
    ) = 1
),
workorder_latest as (
    select *
    from {{ ref('stg_mrp_workorder') }}
    qualify row_number() over (
        partition by mrp_workorder_id
        order by _cdc_ts_ms desc, _cdc_lsn desc
    ) = 1
),
source_rows as (
    select
        b.productivity_block_id,
        b.workorder_id as mrp_workorder_id,
        wo.production_id as mrp_production_id,
        coalesce(b.workcenter_id, wo.workcenter_id) as workcenter_id,
        b.date_start,
        b.date_end,
        l.loss_type,
        l.name as loss_reason,
        b.duration as duration_minutes,
        wo.duration_expected as duration_est,
        mo.qty_produced,
        coalesce(mo.scrap_qty, 0) as scrap_qty,
        (
            coalesce(b.is_deleted, false)
            or coalesce(wo.is_deleted, false)
            or coalesce(wo.state, '') <> 'done'
            or coalesce(mo.is_deleted, false)
        ) as is_deleted,
        b._cdc_ts_ms as block_cdc_ts_ms,
        b._cdc_lsn as block_cdc_lsn,
        l._cdc_ts_ms as loss_cdc_ts_ms,
        l._cdc_lsn as loss_cdc_lsn,
        wo._cdc_ts_ms as workorder_cdc_ts_ms,
        wo._cdc_lsn as workorder_cdc_lsn,
        mo.source_version_key as manufacturing_source_version_key,
        {{ dbt_utils.generate_surrogate_key([
            'b._cdc_ts_ms',
            'b._cdc_lsn',
            'l._cdc_ts_ms',
            'l._cdc_lsn',
            'wo._cdc_ts_ms',
            'wo._cdc_lsn',
            'mo.source_version_key'
        ]) }} as source_version_key
    from block_latest b
    left join loss_latest l
        on l.loss_id = b.loss_id
    left join workorder_latest wo
        on wo.mrp_workorder_id = b.workorder_id
    left join {{ ref('sil_manufacturing_enriched') }} mo
        on mo.mrp_production_id = wo.production_id
),
changed_rows as (
    select src.*
    from source_rows src
    {% if is_incremental() %}
    left join {{ this }} tgt
        on tgt.productivity_block_id = src.productivity_block_id
    where tgt.productivity_block_id is null
       or coalesce(src.source_version_key, '__NULL__')
          <> coalesce(tgt.source_version_key, '__NULL__')
    {% endif %}
)

select
    src.*,
    {{ pipeline_now() }} as silver_updated_at
from changed_rows src
