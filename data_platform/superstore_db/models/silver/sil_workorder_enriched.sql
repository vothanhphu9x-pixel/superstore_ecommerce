-- GRAIN: 1 mrp_workorder đã hoàn thành.
-- duration_actual chỉ cộng productivity block có loss_type='productive'.
-- silver_updated_at chỉ đổi khi Work Order hoặc tập productive block thực sự đổi.
{{ config(
    materialized='incremental',
    incremental_strategy='merge',
    unique_key='mrp_workorder_id',
    on_schema_change='sync_all_columns',
    full_refresh=false
) }}

with workorder_latest as (
    select *
    from {{ ref('stg_mrp_workorder') }}
    qualify row_number() over (
        partition by mrp_workorder_id
        order by _cdc_ts_ms desc, _cdc_lsn desc
    ) = 1
),
productivity_latest as (
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
productive_agg as (
    select
        p.workorder_id,
        sum(p.duration) as duration_actual,
        max(p._cdc_ts_ms) as productivity_cdc_ts_ms,
        max(p._cdc_lsn) as productivity_cdc_lsn,
        listagg(
            p.productivity_block_id::varchar || ':'
            || coalesce(p._cdc_ts_ms::varchar, '__NULL__') || ':'
            || coalesce(p._cdc_lsn::varchar, '__NULL__'),
            '|'
        ) within group (
            order by p.productivity_block_id
        ) as productive_version_signature
    from productivity_latest p
    join loss_latest l
        on l.loss_id = p.loss_id
       and l.loss_type = 'productive'
    where p.is_deleted = false
      and p.workorder_id is not null
    group by p.workorder_id
),
source_rows as (
    select
        wo.mrp_workorder_id,
        wo.production_id,
        wo.workcenter_id,
        wo.name as operation_name,
        wo.date_start,
        wo.date_finished,
        wo.qty_produced,
        wo.duration_expected as duration_est,
        coalesce(pa.duration_actual, 0) as duration_actual,
        wo.state as wo_state,
        (coalesce(wo.is_deleted, false) or coalesce(wo.state, '') <> 'done') as is_deleted,
        wo._cdc_ts_ms as workorder_cdc_ts_ms,
        wo._cdc_lsn as workorder_cdc_lsn,
        pa.productivity_cdc_ts_ms,
        pa.productivity_cdc_lsn,
        pa.productive_version_signature,
        {{ dbt_utils.generate_surrogate_key([
            'wo._cdc_ts_ms',
            'wo._cdc_lsn',
            'pa.duration_actual',
            'pa.productive_version_signature'
        ]) }} as source_version_key
    from workorder_latest wo
    left join productive_agg pa
        on pa.workorder_id = wo.mrp_workorder_id
),
changed_rows as (
    select src.*
    from source_rows src
    {% if is_incremental() %}
    left join {{ this }} tgt
        on tgt.mrp_workorder_id = src.mrp_workorder_id
    where tgt.mrp_workorder_id is null
       or coalesce(src.source_version_key, '__NULL__')
          <> coalesce(tgt.source_version_key, '__NULL__')
    {% endif %}
)

select
    src.*,
    {{ pipeline_now() }} as silver_updated_at
from changed_rows src
