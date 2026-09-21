-- GRAIN: 1 stock_valuation_layer hiện hành, enriched với stock_move hiện hành.
-- CDC của valuation/move chỉ dùng phát hiện thay đổi. silver_updated_at là thời điểm
-- dòng thực sự được INSERT/UPDATE tại Silver; create_date chỉ phục vụ reporting.
{{ config(
    materialized='incremental',
    incremental_strategy='merge',
    unique_key='stock_valuation_layer_id',
    on_schema_change='sync_all_columns',
    full_refresh=false
) }}

with valuation_latest as (
    select *
    from {{ ref('stg_stock_valuation_layer') }}
    qualify row_number() over (
        partition by stock_valuation_layer_id
        order by _cdc_ts_ms desc, _cdc_lsn desc
    ) = 1
),
move_latest as (
    select *
    from {{ ref('stg_stock_move') }}
    qualify row_number() over (
        partition by stock_move_id
        order by _cdc_ts_ms desc, _cdc_lsn desc
    ) = 1
),
source_rows as (
    select
        svl.*,
        sm.reference,
        sm.location_id,
        sm.location_dest_id,
        sm._cdc_ts_ms as move_cdc_ts_ms,
        sm._cdc_lsn as move_cdc_lsn,
        {{ dbt_utils.generate_surrogate_key([
            'svl._cdc_ts_ms',
            'svl._cdc_lsn',
            'sm._cdc_ts_ms',
            'sm._cdc_lsn'
        ]) }} as source_version_key
    from valuation_latest svl
    left join move_latest sm
        on sm.stock_move_id = svl.stock_move_id
),
changed_rows as (
    select src.*
    from source_rows src
    {% if is_incremental() %}
    left join {{ this }} tgt
        on tgt.stock_valuation_layer_id = src.stock_valuation_layer_id
    where tgt.stock_valuation_layer_id is null
       or coalesce(src.source_version_key, '__NULL__')
          <> coalesce(tgt.source_version_key, '__NULL__')
    {% endif %}
)

select
    src.*,
    {{ pipeline_now() }} as silver_updated_at
from changed_rows src
