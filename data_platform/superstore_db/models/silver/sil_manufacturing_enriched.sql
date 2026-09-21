-- GRAIN: 1 mrp_production đã hoàn thành.
-- CDC của MO và toàn bộ scrap thuộc MO dùng để phát hiện thay đổi.
-- silver_updated_at chỉ đổi khi MO hoặc tập scrap thực sự đổi.
{{ config(
    materialized='incremental',
    incremental_strategy='merge',
    unique_key='mrp_production_id',
    on_schema_change='sync_all_columns'
) }}

with mo_latest as (
    select *
    from {{ ref('stg_mrp_production') }}
    qualify row_number() over (
        partition by mrp_production_id
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
workorder_agg as (
    select
        production_id,
        max(iff(is_deleted = false and state = 'done', qty_produced, null)) as qty_produced,
        listagg(
            mrp_workorder_id::varchar || ':'
            || coalesce(_cdc_ts_ms::varchar, '__NULL__') || ':'
            || coalesce(_cdc_lsn::varchar, '__NULL__'),
            '|'
        ) within group (order by mrp_workorder_id) as workorder_version_signature
    from workorder_latest
    where production_id is not null
    group by production_id
),
scrap_latest as (
    select *
    from {{ ref('stg_stock_scrap') }}
    qualify row_number() over (
        partition by stock_scrap_id
        order by _cdc_ts_ms desc, _cdc_lsn desc
    ) = 1
),
scrap_agg as (
    select
        production_id,
        sum(iff(is_deleted = false and state = 'done', scrap_qty, 0)) as scrap_qty,
        max(_cdc_ts_ms) as scrap_cdc_ts_ms,
        max(_cdc_lsn) as scrap_cdc_lsn,
        listagg(
            stock_scrap_id::varchar || ':'
            || coalesce(_cdc_ts_ms::varchar, '__NULL__') || ':'
            || coalesce(_cdc_lsn::varchar, '__NULL__'),
            '|'
        ) within group (
            order by stock_scrap_id
        ) as scrap_version_signature
    from scrap_latest
    where production_id is not null
    group by production_id
),
source_rows as (
    select
        mo.mrp_production_id,
        mo.product_id,
        mo.location_dest_id,
        mo.name as mo_name,
        mo.product_qty as qty_planned,
        coalesce(wa.qty_produced, iff(mo.state = 'done', mo.product_qty, mo.qty_producing))
            as qty_produced,
        coalesce(sc.scrap_qty, 0) as scrap_qty,
        mo.date_start,
        mo.date_finished,
        mo.bom_id,
        mo.state as mo_state,
        (coalesce(mo.is_deleted, false) or coalesce(mo.state, '') <> 'done') as is_deleted,
        mo._cdc_ts_ms as mo_cdc_ts_ms,
        mo._cdc_lsn as mo_cdc_lsn,
        sc.scrap_cdc_ts_ms,
        sc.scrap_cdc_lsn,
        sc.scrap_version_signature,
        wa.workorder_version_signature,
        {{ dbt_utils.generate_surrogate_key([
            'mo._cdc_ts_ms',
            'mo._cdc_lsn',
            'wa.workorder_version_signature',
            'sc.scrap_qty',
            'sc.scrap_version_signature'
    ]) }} as source_version_key
    from mo_latest mo
    left join workorder_agg wa
        on wa.production_id = mo.mrp_production_id
    left join scrap_agg sc
        on sc.production_id = mo.mrp_production_id
),
changed_rows as (
    select src.*
    from source_rows src
    {% if is_incremental() %}
    left join {{ this }} tgt
        on tgt.mrp_production_id = src.mrp_production_id
    where tgt.mrp_production_id is null
       or coalesce(src.source_version_key, '__NULL__')
          <> coalesce(tgt.source_version_key, '__NULL__')
    {% endif %}
)

select
    src.*,
    {{ pipeline_now() }} as silver_updated_at
from changed_rows src
