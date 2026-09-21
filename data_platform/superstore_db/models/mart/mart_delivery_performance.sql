-- GRAIN  : 1 completion month × 1 warehouse × 1 ship_mode.
-- SOURCE : fact_inventory_movement, deduplicate stock_move về stock_picking trước aggregate.
-- SLA    : ưu tiên date_deadline; nếu không có thì dùng scheduled_date.
-- ON TIME: bao gồm cả giao đúng ngày và giao sớm (SLA variance <= 0).
-- SHIP MODE: lấy từ delivery.carrier qua stock_picking.carrier_id; Unknown chỉ còn là
--            trạng thái chất lượng dữ liệu có chủ đích cho transfer ngoài generator.
-- REFRESH: table rebuild để correction làm mất/đổi group được phản ánh đầy đủ.
{{ config(materialized='table') }}

with delivery_pickings as (
    select
        fact.fact_inv_move_sk,
        fact.picking_id,
        fact.warehouse_sk,
        coalesce(fact.ship_mode, 'Unknown') as ship_mode,
        to_number(to_char(fact.date_done, 'YYYYMMDD')) as delivery_date_key,
        case
            when fact.date_deadline is not null then fact.days_vs_deadline
            else fact.days_vs_schedule
        end as days_vs_sla_days,
        case
            when fact.date_deadline is not null then 'deadline'
            when fact.scheduled_date is not null then 'schedule'
            else 'none'
        end as sla_basis
    from {{ ref('fact_inventory_movement') }} fact
    where fact.is_deleted = false
      and fact.movement_type = 'sale_out'
      and fact.picking_state = 'done'
      and fact.picking_id is not null
      and fact.date_done is not null
    qualify row_number() over (
        partition by fact.picking_id
        order by fact.stock_move_id
    ) = 1
),
deliveries as (
    select
        picking.fact_inv_move_sk,
        picking.picking_id,
        picking.warehouse_sk,
        picking.ship_mode,
        to_number(
            to_char(date_trunc('month', d.date_actual), 'YYYYMMDD')
        ) as month_date_key,
        picking.days_vs_sla_days,
        picking.sla_basis
    from delivery_pickings picking
    join {{ ref('dim_date') }} d
        on d.date_key = picking.delivery_date_key
    where picking.warehouse_sk is not null
),
monthly as (
    select
        warehouse_sk,
        ship_mode,
        month_date_key,
        min(fact_inv_move_sk) as src_fact_inv_move_sk,
        count(*) as total_deliveries,
        count_if(days_vs_sla_days <= 0) as on_time_count,
        count_if(days_vs_sla_days > 0) as late_count,
        count_if(days_vs_sla_days < 0) as early_count,
        count_if(days_vs_sla_days is null) as no_sla_count,
        count_if(sla_basis = 'deadline') as deadline_sla_count,
        count_if(sla_basis = 'schedule') as schedule_sla_count,
        avg(iff(days_vs_sla_days > 0, days_vs_sla_days, null)) as avg_days_late
    from deliveries
    group by warehouse_sk, ship_mode, month_date_key
)

select
    {{ dbt_utils.generate_surrogate_key([
        'monthly.warehouse_sk',
        'monthly.ship_mode',
        'monthly.month_date_key'
    ]) }} as mart_delivery_sk,
    monthly.src_fact_inv_move_sk,
    monthly.warehouse_sk,
    monthly.month_date_key,
    monthly.ship_mode,
    monthly.total_deliveries,
    monthly.on_time_count,
    monthly.late_count,
    monthly.early_count,
    monthly.no_sla_count,
    monthly.deadline_sla_count,
    monthly.schedule_sla_count,
    round(
        monthly.on_time_count * 1.0
        / nullif(monthly.total_deliveries - monthly.no_sla_count, 0),
        4
    ) as on_time_pct,
    round(monthly.avg_days_late, 2) as avg_days_late
from monthly
