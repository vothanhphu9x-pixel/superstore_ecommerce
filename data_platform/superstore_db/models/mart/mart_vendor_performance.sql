-- GRAIN  : 1 purchase order month × 1 vendor version key.
-- SOURCE : fact_purchase.
-- LATE   : nhận từ receipt stock_move qua fact_purchase. Mẫu số chỉ gồm dòng có đủ
--          planned_date + received_date; thiếu dữ liệu được tách riêng, không tính là on-time.
-- REFRESH: table rebuild để correction/cancellation xóa được aggregate group cũ.
{{ config(materialized='table') }}

with purchases as (
    select
        fact.fact_purchase_sk,
        fact.order_id,
        fact.vendor_sk,
        to_number(
            to_char(date_trunc('month', d.date_actual), 'YYYYMMDD')
        ) as month_date_key,
        fact.product_qty,
        fact.qty_received,
        fact.total_amount,
        fact.received_date_key,
        fact.days_late,
        fact.is_late_delivery
    from {{ ref('fact_purchase') }} fact
    join {{ ref('dim_date') }} d
        on d.date_key = fact.order_date_key
    where fact.is_deleted = false
      and fact.vendor_sk is not null
      and fact.po_state in ('purchase', 'done')
),
monthly as (
    select
        vendor_sk,
        month_date_key,
        min(fact_purchase_sk) as src_fact_purchase_sk,
        count(*) as purchase_line_count,
        count(distinct order_id) as po_count,
        sum(coalesce(qty_received, 0)) as qty_received,
        sum(coalesce(product_qty, 0)) as product_qty,
        sum(total_amount) as purchase_amount,
        count_if(received_date_key is not null) as received_line_count,
        count_if(is_late_delivery = true) as late_count,
        count_if(is_late_delivery = false) as on_time_count,
        count_if(is_late_delivery is null) as unmeasured_line_count,
        avg(iff(is_late_delivery = true, days_late, null)) as avg_days_late
    from purchases
    group by vendor_sk, month_date_key
)

select
    {{ dbt_utils.generate_surrogate_key([
        'monthly.vendor_sk',
        'monthly.month_date_key'
    ]) }} as mart_vendor_perf_sk,
    monthly.src_fact_purchase_sk,
    monthly.vendor_sk,
    monthly.month_date_key,
    monthly.purchase_line_count,
    monthly.po_count,
    monthly.qty_received,
    monthly.product_qty,
    round(
        monthly.qty_received * 1.0 / nullif(monthly.product_qty, 0),
        4
    ) as fill_rate_pct,
    monthly.purchase_amount,
    monthly.received_line_count,
    monthly.on_time_count,
    monthly.late_count,
    monthly.unmeasured_line_count,
    round(
        monthly.received_line_count * 1.0
        / nullif(monthly.purchase_line_count, 0),
        4
    ) as receipt_coverage_pct,
    round(
        monthly.on_time_count * 1.0
        / nullif(monthly.on_time_count + monthly.late_count, 0),
        4
    ) as on_time_delivery_pct,
    round(
        monthly.late_count * 1.0
        / nullif(monthly.on_time_count + monthly.late_count, 0),
        4
    ) as late_delivery_pct,
    round(monthly.avg_days_late, 2) as avg_days_late,
    case
        when monthly.received_line_count = 0 then 'not_available'
        when monthly.unmeasured_line_count > 0 then 'partial'
        else 'available'
    end as late_measurement_status
from monthly
