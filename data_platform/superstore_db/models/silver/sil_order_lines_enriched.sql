-- GRAIN: 1 sale_order_line hiện hành. CDC của line/header chỉ dùng phát hiện thay đổi.
-- silver_updated_at là thời điểm dòng thực sự được INSERT/UPDATE tại Silver;
-- date_order chỉ phục vụ phân tích business time.
{{ config(
    materialized='incremental',
    incremental_strategy='merge',
    unique_key='sale_order_line_id',
    on_schema_change='sync_all_columns',
    full_refresh=false
) }}

with order_latest as (
    select *
    from {{ ref('stg_sale_order') }}
    qualify row_number() over (partition by order_id order by _cdc_ts_ms desc, _cdc_lsn desc) = 1
),
line_latest as (
    select *
    from {{ ref('stg_sale_order_line') }}
    qualify row_number() over (
        partition by sale_order_line_id
        order by _cdc_ts_ms desc, _cdc_lsn desc
    ) = 1
),
source_rows as (
    select
        sol.sale_order_line_id,
        sol.order_id,
        so.name                                                            as order_name,
        (so.name ilike 'SR%')                                              as is_return,
        cast(null as int)                                                  as return_of_order_id,
        sol.product_id,
        so.partner_id,
        so.user_id,
        so.warehouse_id,
        so.campaign_id,
        so.medium_id,
        so.opportunity_id,
        so.date_order,
        sol.product_uom_qty                                                as quantity,
        sol.qty_delivered                                                  as quantity_delivered,
        sol.price_unit,
        sol.discount / 100.0                                               as discount_pct,
        sol.product_uom_qty * sol.price_unit * (1 - sol.discount / 100.0)  as revenue_amount,
        so.state                                                           as order_state,
        so.invoice_status,
        so.delivery_status,
        (so.state = 'cancel')                                              as is_cancelled,
        (coalesce(sol.is_deleted, false) or coalesce(so.is_deleted, false)) as is_deleted,
        sol._cdc_ts_ms                                                     as line_cdc_ts_ms,
        sol._cdc_lsn                                                       as line_cdc_lsn,
        so._cdc_ts_ms                                                      as order_cdc_ts_ms,
        so._cdc_lsn                                                        as order_cdc_lsn,
        {{ dbt_utils.generate_surrogate_key([
            'sol._cdc_ts_ms',
            'sol._cdc_lsn',
            'so._cdc_ts_ms',
            'so._cdc_lsn'
        ]) }}                                                              as source_version_key
    from line_latest sol
    join order_latest so on so.order_id = sol.order_id
),
changed_rows as (
    select src.*
    from source_rows src
    {% if is_incremental() %}
    left join {{ this }} tgt on tgt.sale_order_line_id = src.sale_order_line_id
    where tgt.sale_order_line_id is null
       or coalesce(src.source_version_key, '__NULL__')
          <> coalesce(tgt.source_version_key, '__NULL__')
    {% endif %}
)

select
    src.*,
    {{ pipeline_now() }} as silver_updated_at
from changed_rows src
