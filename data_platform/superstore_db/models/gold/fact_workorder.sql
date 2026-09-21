-- GRAIN   : 1 hàng = 1 mrp_workorder đã hoàn thành.
-- SOURCE  : silver → sil_workorder_enriched.
-- DERIVED : duration_est từ duration_expected; duration_actual từ productive blocks.
-- LƯU Ý   : đây không phải fact OEE; không tách Availability/Performance/Quality.
{{ config(
    materialized='incremental',
    incremental_strategy='merge',
    unique_key='mrp_workorder_id',
    on_schema_change='sync_all_columns'
) }}

select
    {{ dbt_utils.generate_surrogate_key([
        'src.mrp_workorder_id'
    ]) }}                                                as fact_wo_sk,
    src.mrp_workorder_id,
    src.production_id                                   as mrp_production_id,
    to_number(
        to_char(src.date_start, 'YYYYMMDD')
    )                                                   as start_date_key,
    dw.workcenter_sk,
    src.operation_name,
    cast(null as int)                                   as sequence,
    src.qty_produced                                    as qty_producing,
    src.duration_est,
    src.duration_actual,
    src.wo_state,
    src.is_deleted,
    src.silver_updated_at                               as source_silver_updated_at,
    src.source_version_key,
    src.workorder_cdc_ts_ms,
    src.workorder_cdc_lsn,
    src.productivity_cdc_ts_ms,
    src.productivity_cdc_lsn
from {{ ref('sil_workorder_enriched') }} src
left join {{ ref('dim_workcenter') }} dw
    on dw.workcenter_id = src.workcenter_id

{% if is_incremental() %}
left join {{ this }} tgt
    on tgt.mrp_workorder_id = src.mrp_workorder_id
where tgt.mrp_workorder_id is null
   or src.silver_updated_at > coalesce(
        tgt.source_silver_updated_at,
        '1900-01-01'::timestamp
   )
   or coalesce(src.source_version_key, '__NULL__')
      <> coalesce(tgt.source_version_key, '__NULL__')
   or coalesce(dw.workcenter_sk, '__NULL__')
      <> coalesce(tgt.workcenter_sk, '__NULL__')
{% endif %}
