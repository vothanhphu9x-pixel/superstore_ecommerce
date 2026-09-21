-- GRAIN   : 1 hàng = 1 purchase_order_line
-- SOURCE  : silver → sil_purchase_order_lines_enriched
-- DERIVED : receipt_date/warehouse/late KPI lấy từ purchase receipt stock_move đã done.
-- TEST    : unique(fact_purchase_sk), not_null(vendor_sk), relationships(dim_product, dim_date)
-- CROSS-DOMAIN: stock_move.purchase_line_id là FK chuẩn tới purchase_order_line.id; không parse
-- origin dạng text. Nếu một PO line được nhận nhiều lần, received_date là lần nhận cuối cùng.
-- vendor/product/buyer temporal join theo Silver processing time; business dates chỉ dùng
-- cho reporting và date dimension.
{{ config(
    materialized='incremental',
    incremental_strategy='merge',
    unique_key='purchase_order_line_id',
    on_schema_change='sync_all_columns'
) }}

with receipt_moves as (
    select
        purchase_order_line_id,
        location_dest_id,
        qty_done,
        date_done,
        silver_updated_at
    from {{ ref('sil_stock_movement_enriched') }}
    where purchase_order_line_id is not null
      and is_deleted = false
      and movement_type = 'purchase_in'
      and picking_state = 'done'
      and date_done is not null
),
receipts as (
    select
        purchase_order_line_id,
        max(date_done) as received_date,
        max_by(location_dest_id, date_done) as receipt_location_id,
        sum(qty_done) as movement_received_qty,
        count(*) as receipt_move_count,
        max(silver_updated_at) as receipt_silver_updated_at
    from receipt_moves
    group by purchase_order_line_id
)

select
    {{ dbt_utils.generate_surrogate_key(['src.purchase_order_line_id']) }} as fact_purchase_sk,
    src.purchase_order_line_id,
    src.order_id,
    src.order_name,
    to_number(to_char(src.date_order, 'YYYYMMDD'))      as order_date_key,
    to_number(to_char(src.date_planned, 'YYYYMMDD'))   as planned_date_key,
    to_number(to_char(receipt.received_date, 'YYYYMMDD')) as received_date_key,
    dc.customer_sk                                     as vendor_sk,
    de.employee_sk                                     as buyer_sk,
    receipt_location.warehouse_sk                      as warehouse_sk,
    dp.product_sk,
    src.product_qty,
    src.qty_received,
    src.price_unit,
    src.discount / 100.0                               as discount_pct,
    src.price_subtotal                                 as total_amount,
    receipt.movement_received_qty,
    receipt.receipt_move_count,
    datediff('day', src.date_planned, receipt.received_date) as days_vs_planned,
    greatest(
        datediff('day', src.date_planned, receipt.received_date),
        0
    )                                                   as days_late,
    case
        when receipt.received_date is null or src.date_planned is null then null
        else receipt.received_date > src.date_planned
    end                                                 as is_late_delivery,
    src.po_state,
    src.is_deleted,
    src.silver_updated_at                              as source_silver_updated_at,
    src.source_version_key,
    receipt.receipt_silver_updated_at,
    src.line_cdc_ts_ms,
    src.line_cdc_lsn,
    src.order_cdc_ts_ms,
    src.order_cdc_lsn,
    dc.dim_updated_at                                  as vendor_dim_updated_at,
    de.dim_updated_at                                  as buyer_dim_updated_at,
    dp.dim_updated_at                                  as product_dim_updated_at,
    receipt_location.dim_updated_at                    as location_dim_updated_at
from {{ ref('sil_purchase_order_lines_enriched') }} src
left join {{ ref('dim_customer') }} dc
    on dc.partner_id = src.partner_id
   and src.silver_updated_at >= dc.dbt_valid_from
   and src.silver_updated_at < coalesce(dc.dbt_valid_to, '9999-12-31'::timestamp)
left join {{ ref('dim_employee') }} de
    on de.user_id = src.user_id
   and src.silver_updated_at >= de.dbt_valid_from
   and src.silver_updated_at < coalesce(de.dbt_valid_to, '9999-12-31'::timestamp)
left join {{ ref('dim_product') }} dp
    on dp.product_id = src.product_id
   and src.silver_updated_at >= dp.dbt_valid_from
   and src.silver_updated_at < coalesce(dp.dbt_valid_to, '9999-12-31'::timestamp)
left join receipts receipt
    on receipt.purchase_order_line_id = src.purchase_order_line_id
left join {{ ref('dim_location') }} receipt_location
    on receipt_location.location_id = receipt.receipt_location_id
{% if is_incremental() %}
left join {{ this }} tgt
    on tgt.purchase_order_line_id = src.purchase_order_line_id
where tgt.purchase_order_line_id is null
   or src.silver_updated_at > coalesce(
        tgt.source_silver_updated_at,
        '1900-01-01'::timestamp
   )
   or coalesce(
        receipt.receipt_silver_updated_at,
        '1900-01-01'::timestamp
   ) > coalesce(
        tgt.receipt_silver_updated_at,
        '1900-01-01'::timestamp
   )
   or coalesce(dc.customer_sk, '__NULL__') <> coalesce(tgt.vendor_sk, '__NULL__')
   or coalesce(dp.product_sk, '__NULL__') <> coalesce(tgt.product_sk, '__NULL__')
   or coalesce(de.employee_sk, '__NULL__') <> coalesce(tgt.buyer_sk, '__NULL__')
   or coalesce(receipt_location.warehouse_sk, '__NULL__')
      <> coalesce(tgt.warehouse_sk, '__NULL__')
   or coalesce(
        dc.dim_updated_at,
        '1900-01-01'::timestamp
   ) > coalesce(
        tgt.vendor_dim_updated_at,
        '1900-01-01'::timestamp
   )
   or coalesce(
        de.dim_updated_at,
        '1900-01-01'::timestamp
   ) > coalesce(
        tgt.buyer_dim_updated_at,
        '1900-01-01'::timestamp
   )
   or coalesce(
        dp.dim_updated_at,
        '1900-01-01'::timestamp
   ) > coalesce(
        tgt.product_dim_updated_at,
        '1900-01-01'::timestamp
   )
   or coalesce(
        receipt_location.dim_updated_at,
        '1900-01-01'::timestamp
   ) > coalesce(
        tgt.location_dim_updated_at,
        '1900-01-01'::timestamp
   )
{% endif %}
