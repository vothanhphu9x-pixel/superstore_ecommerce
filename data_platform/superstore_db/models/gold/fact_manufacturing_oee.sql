-- GRAIN   : 1 hàng = 1 mrp_workcenter_productivity block.
-- SOURCE  : silver → sil_oee_blocks_enriched.
-- OEE     : Availability/Performance/Quality được aggregate ở mart, không tính tại đây.
-- LƯU Ý   : qty_produced/scrap_qty lặp theo các block của cùng MO; mart phải dedup theo MO.
{{ config(
    materialized='incremental',
    incremental_strategy='merge',
    unique_key='productivity_block_id',
    on_schema_change='sync_all_columns'
) }}

select
    {{ dbt_utils.generate_surrogate_key([
        'src.productivity_block_id'
    ]) }}                                                as fact_oee_sk,
    src.productivity_block_id,
    src.mrp_workorder_id,
    src.mrp_production_id,
    to_number(
        to_char(src.date_start, 'YYYYMMDD')
    )                                                   as block_date_key,
    dw.workcenter_sk,
    src.loss_type,
    src.loss_reason,
    src.duration_minutes,
    src.duration_est,
    src.qty_produced,
    src.scrap_qty,
    src.is_deleted,
    src.silver_updated_at                               as source_silver_updated_at,
    src.source_version_key,
    src.block_cdc_ts_ms,
    src.block_cdc_lsn,
    src.loss_cdc_ts_ms,
    src.loss_cdc_lsn,
    src.workorder_cdc_ts_ms,
    src.workorder_cdc_lsn,
    src.manufacturing_source_version_key
from {{ ref('sil_oee_blocks_enriched') }} src
left join {{ ref('dim_workcenter') }} dw
    on dw.workcenter_id = src.workcenter_id

{% if is_incremental() %}
left join {{ this }} tgt
    on tgt.productivity_block_id = src.productivity_block_id
where tgt.productivity_block_id is null
   or src.silver_updated_at > coalesce(
        tgt.source_silver_updated_at,
        '1900-01-01'::timestamp
   )
   or coalesce(src.source_version_key, '__NULL__')
      <> coalesce(tgt.source_version_key, '__NULL__')
   or coalesce(dw.workcenter_sk, '__NULL__')
      <> coalesce(tgt.workcenter_sk, '__NULL__')
{% endif %}
