-- GRAIN   : 1 hàng = 1 stock_move (done)
-- SOURCE  : silver → sil_stock_movement_enriched
-- DERIVED : product_value_amount = qty_done × standard_cost_amount tại Silver processing time.
-- TEST    : unique(fact_inv_move_sk), not_null(product_sk), relationships(dim_product, dim_date, dim_warehouse, dim_location)
-- LINEAGE : purchase_order_line_id nối tới fact_purchase.purchase_order_line_id;
--           sale_order_line_id nối tới fact_sales.sale_order_line_id.
-- warehouse_sk = COALESCE(dest.warehouse_sk, src.warehouse_sk) — 1 trong 2 đầu move thường là
-- internal location gắn với 1 warehouse cụ thể, đầu kia (customer/supplier/production) không có.
-- Lưu ngày gốc của stock_picking và tự derive độ trễ thực tế. Không dùng riêng
-- odoo_has_deadline_issue vì cờ Odoo chỉ so date_deadline với scheduled_date.
{{ config(
    materialized='incremental',
    incremental_strategy='merge',
    unique_key='stock_move_id',
    on_schema_change='sync_all_columns'
) }}

select
    {{ dbt_utils.generate_surrogate_key(['sil.stock_move_id']) }} as fact_inv_move_sk,
    sil.stock_move_id,
    sil.picking_id,
    sil.purchase_order_line_id,
    sil.sale_order_line_id,
    to_number(to_char(sil.date, 'YYYYMMDD'))           as move_date_key,
    dp.product_sk,
    coalesce(dst.warehouse_sk, src.warehouse_sk)        as warehouse_sk,
    src.location_sk                                     as src_location_sk,
    dst.location_sk                                     as dest_location_sk,
    sil.movement_type,
    sil.qty_done,
    sil.is_deleted,
    round(sil.qty_done * dp.standard_cost_amount, 2)    as product_value_amount,
    sil.reference,
    sil.carrier_id,
    sil.ship_mode,
    sil.carrier_tracking_ref,
    sil.carrier_price_amount,
    sil.picking_state,
    case
        when sil.sale_order_line_id is not null then sil.picking_state
    end                                                 as delivery_status,
    case
        when sil.purchase_order_line_id is not null then sil.picking_state
    end                                                 as receipt_status,
    sil.scheduled_date,
    sil.date_done,
    sil.date_deadline,
    sil.odoo_has_deadline_issue,
    datediff(
        'day',
        sil.scheduled_date,
        sil.date_done
    )                                                   as days_vs_schedule,
    case
        when sil.date_done is null or sil.scheduled_date is null then null
        when sil.date_done > sil.scheduled_date then true
        else false
    end                                                 as is_late_vs_schedule,
    datediff(
        'day',
        sil.date_deadline,
        sil.date_done
    )                                                   as days_vs_deadline,
    case
        when sil.date_done is null or sil.date_deadline is null then null
        when sil.date_done > sil.date_deadline then true
        else false
    end                                                 as is_late_vs_deadline,
    sil.silver_updated_at                              as source_silver_updated_at,
    sil.source_version_key,
    sil.move_cdc_ts_ms,
    sil.move_cdc_lsn,
    sil.picking_cdc_ts_ms,
    sil.picking_cdc_lsn,
    sil.carrier_cdc_ts_ms,
    sil.carrier_cdc_lsn,
    dp.dim_updated_at                                   as product_dim_updated_at,
    src.dim_updated_at                                  as src_location_dim_updated_at,
    dst.dim_updated_at                                  as dest_location_dim_updated_at
from {{ ref('sil_stock_movement_enriched') }} sil
left join {{ ref('dim_product') }} dp
    on dp.product_id = sil.product_id
   and sil.silver_updated_at >= dp.dbt_valid_from
   and sil.silver_updated_at < coalesce(dp.dbt_valid_to, '9999-12-31'::timestamp)
left join {{ ref('dim_location') }} src
    on src.location_id = sil.location_id
left join {{ ref('dim_location') }} dst
    on dst.location_id = sil.location_dest_id
{% if is_incremental() %}
left join {{ this }} tgt
    on tgt.stock_move_id = sil.stock_move_id
where tgt.stock_move_id is null
   or sil.silver_updated_at > coalesce(
        tgt.source_silver_updated_at,
        '1900-01-01'::timestamp
   )
   or coalesce(dp.product_sk, '__NULL__') <> coalesce(tgt.product_sk, '__NULL__')
   or coalesce(src.location_sk, '__NULL__') <> coalesce(tgt.src_location_sk, '__NULL__')
   or coalesce(dst.location_sk, '__NULL__') <> coalesce(tgt.dest_location_sk, '__NULL__')
   or coalesce(
        dp.dim_updated_at,
        '1900-01-01'::timestamp
   ) > coalesce(
        tgt.product_dim_updated_at,
        '1900-01-01'::timestamp
   )
   or coalesce(
        src.dim_updated_at,
        '1900-01-01'::timestamp
   ) > coalesce(
        tgt.src_location_dim_updated_at,
        '1900-01-01'::timestamp
   )
   or coalesce(
        dst.dim_updated_at,
        '1900-01-01'::timestamp
   ) > coalesce(
        tgt.dest_location_dim_updated_at,
        '1900-01-01'::timestamp
   )
{% endif %}
