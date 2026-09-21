-- GRAIN: 1 stock_move. JOIN: stg_stock_move + stg_stock_picking (header, cross-lane) +
-- stg_stock_location (src/dest, cross-lane) — không cần SCD2 riêng nên join thẳng vào SILVER.
-- DERIVED: movement_type resolve qua location.usage của src/dest (sale_out|purchase_in|transfer|
-- mfg_consume|mfg_output|scrap|inventory_adj). ⚠️ Heuristic: Odoo core dùng CHUNG usage='inventory'
-- cho cả 2 loại location "Scrap" và "Inventory adjustment" (không phân biệt được bằng usage) —
-- disambiguate bằng complete_name ILIKE '%scrap%', cần xác nhận với ETL gốc nếu tên location thật
-- khác quy ước này.
{{ config(
    materialized='incremental',
    incremental_strategy='merge',
    unique_key='stock_move_id',
    on_schema_change='sync_all_columns',
    full_refresh=false
) }}

with move_latest as (
    select *
    from {{ ref('stg_stock_move') }}
    qualify row_number() over (partition by stock_move_id order by _cdc_ts_ms desc, _cdc_lsn desc) = 1
),
picking_latest as (
    select *
    from {{ ref('stg_stock_picking') }}
    qualify row_number() over (partition by picking_id order by _cdc_ts_ms desc, _cdc_lsn desc) = 1
),
carrier_latest as (
    select *
    from {{ ref('stg_delivery_carrier') }}
    qualify row_number() over (partition by carrier_id order by _cdc_ts_ms desc, _cdc_lsn desc) = 1
),
location_latest as (
    select *
    from {{ ref('stg_stock_location') }}
    qualify row_number() over (partition by location_id order by _cdc_ts_ms desc, _cdc_lsn desc) = 1
),
source_rows as (
    select
        m.stock_move_id,
        m.purchase_order_line_id,
        m.sale_order_line_id,
        m.date,
        m.product_id,
        m.quantity                                         as qty_done,
        m.origin,
        m.reference,
        m.state,
        (coalesce(m.is_deleted, false) or coalesce(pk.is_deleted, false)) as is_deleted,
        m.picking_id,
        pk.carrier_id,
        carrier.carrier_name                               as ship_mode,
        pk.carrier_tracking_ref,
        pk.carrier_price                                   as carrier_price_amount,
        pk.state                                           as picking_state,
        pk.scheduled_date,
        pk.date_done,
        pk.date_deadline,
        pk.has_deadline_issue                              as odoo_has_deadline_issue,
        m.location_id,
        m.location_dest_id,
        loc_src.usage                                      as src_usage,
        loc_dst.usage                                      as dest_usage,
        case
            when loc_src.usage = 'supplier' and loc_dst.usage = 'internal' then 'purchase_in'
            when loc_src.usage = 'internal' and loc_dst.usage = 'customer' then 'sale_out'
            when loc_src.usage = 'internal' and loc_dst.usage = 'internal' then 'transfer'
            when loc_dst.usage = 'production' then 'mfg_consume'
            when loc_src.usage = 'production' then 'mfg_output'
            when loc_dst.usage = 'inventory' and loc_dst.complete_name ilike '%scrap%' then 'scrap'
            when loc_src.usage = 'inventory' and loc_src.complete_name ilike '%scrap%' then 'scrap'
            when loc_dst.usage = 'inventory' or loc_src.usage = 'inventory' then 'inventory_adj'
            else 'other'
        end                                                as movement_type,
        m._cdc_ts_ms                                       as move_cdc_ts_ms,
        m._cdc_lsn                                         as move_cdc_lsn,
        pk._cdc_ts_ms                                      as picking_cdc_ts_ms,
        pk._cdc_lsn                                        as picking_cdc_lsn,
        carrier._cdc_ts_ms                                 as carrier_cdc_ts_ms,
        carrier._cdc_lsn                                   as carrier_cdc_lsn,
        loc_src._cdc_ts_ms                                 as src_location_cdc_ts_ms,
        loc_src._cdc_lsn                                   as src_location_cdc_lsn,
        loc_dst._cdc_ts_ms                                 as dest_location_cdc_ts_ms,
        loc_dst._cdc_lsn                                   as dest_location_cdc_lsn,
        {{ dbt_utils.generate_surrogate_key([
            'm._cdc_ts_ms',
            'm._cdc_lsn',
            'pk._cdc_ts_ms',
            'pk._cdc_lsn',
            'carrier._cdc_ts_ms',
            'carrier._cdc_lsn',
            'loc_src._cdc_ts_ms',
            'loc_src._cdc_lsn',
            'loc_dst._cdc_ts_ms',
            'loc_dst._cdc_lsn'
        ]) }}                                             as source_version_key
    from move_latest m
    left join picking_latest pk on pk.picking_id = m.picking_id
    left join carrier_latest carrier on carrier.carrier_id = pk.carrier_id
    left join location_latest loc_src on loc_src.location_id = m.location_id
    left join location_latest loc_dst on loc_dst.location_id = m.location_dest_id
),
changed_rows as (
    select src.*
    from source_rows src
    {% if is_incremental() %}
    left join {{ this }} tgt on tgt.stock_move_id = src.stock_move_id
    where tgt.stock_move_id is null
       or coalesce(src.source_version_key, '__NULL__')
          <> coalesce(tgt.source_version_key, '__NULL__')
    {% endif %}
)

select
    src.*,
    {{ pipeline_now() }} as silver_updated_at
from changed_rows src
