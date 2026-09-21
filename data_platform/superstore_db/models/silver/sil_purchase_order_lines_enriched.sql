-- GRAIN: 1 purchase_order_line hiện hành. CDC của line/header chỉ dùng phát hiện thay đổi.
-- silver_updated_at là thời điểm dòng thực sự được INSERT/UPDATE tại Silver;
-- date_order/date_planned giữ nguyên cho business analysis.
{{ config(
    materialized='incremental',
    incremental_strategy='merge',
    unique_key='purchase_order_line_id',
    on_schema_change='sync_all_columns',
    full_refresh=false
) }}

with line_latest as (
    select *
    from {{ ref('stg_purchase_order_line') }}
    qualify row_number() over (
        partition by purchase_order_line_id
        order by _cdc_ts_ms desc, _cdc_lsn desc
    ) = 1
),
order_latest as (
    select *
    from {{ ref('stg_purchase_order') }}
    qualify row_number() over (
        partition by order_id
        order by _cdc_ts_ms desc, _cdc_lsn desc
    ) = 1
),
source_rows as (
    select
        pol.purchase_order_line_id,
        pol.order_id,
        po.name as order_name,
        po.partner_id,
        po.user_id,
        pol.product_id,
        po.date_order,
        pol.date_planned,
        pol.product_qty,
        pol.qty_received,
        pol.price_unit,
        pol.discount,
        pol.price_subtotal,
        po.state as po_state,
        (coalesce(pol.is_deleted, false) or coalesce(po.is_deleted, false)) as is_deleted,
        pol._cdc_ts_ms as line_cdc_ts_ms,
        pol._cdc_lsn as line_cdc_lsn,
        po._cdc_ts_ms as order_cdc_ts_ms,
        po._cdc_lsn as order_cdc_lsn,
        {{ dbt_utils.generate_surrogate_key([
            'pol._cdc_ts_ms',
            'pol._cdc_lsn',
            'po._cdc_ts_ms',
            'po._cdc_lsn'
        ]) }} as source_version_key
    from line_latest pol
    join order_latest po on po.order_id = pol.order_id
),
changed_rows as (
    select src.*
    from source_rows src
    {% if is_incremental() %}
    left join {{ this }} tgt on tgt.purchase_order_line_id = src.purchase_order_line_id
    where tgt.purchase_order_line_id is null
       or coalesce(src.source_version_key, '__NULL__')
          <> coalesce(tgt.source_version_key, '__NULL__')
    {% endif %}
)

select
    src.*,
    {{ pipeline_now() }} as silver_updated_at
from changed_rows src
