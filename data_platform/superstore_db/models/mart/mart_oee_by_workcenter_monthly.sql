-- GRAIN  : 1 workcenter x 1 month.
-- SOURCE : fact_manufacturing_oee (A/P) + fact_manufacturing (Q).
-- DEDUP  : duration_est phân bổ đúng 1 lần/workorder; output quantity dedup 1 lần/MO/workcenter.
{{ config(materialized='table') }}

with blocks as (
    select
        fact.*,
        to_number(
            to_char(date_trunc('month', d.date_actual), 'YYYYMMDD')
        ) as month_date_key
    from {{ ref('fact_manufacturing_oee') }} fact
    join {{ ref('dim_date') }} d
        on d.date_key = fact.block_date_key
    where fact.is_deleted = false
      and fact.workcenter_sk is not null
),

workorder_totals as (
    select
        workcenter_sk,
        mrp_workorder_id,
        max(duration_est) as duration_est,
        sum(iff(loss_type = 'productive', duration_minutes, 0)) as productive_minutes
    from blocks
    where mrp_workorder_id is not null
    group by workcenter_sk, mrp_workorder_id
),

allocated_blocks as (
    select
        block.*,
        case
            when block.loss_type = 'productive'
             and totals.productive_minutes > 0
                then totals.duration_est
                   * block.duration_minutes
                   / totals.productive_minutes
            else 0
        end as allocated_duration_est
    from blocks block
    left join workorder_totals totals
        on totals.workcenter_sk = block.workcenter_sk
       and totals.mrp_workorder_id = block.mrp_workorder_id
),

availability_performance as (
    select
        workcenter_sk,
        month_date_key,
        min(fact_oee_sk) as src_fact_oee_sk,
        count(*) as productivity_block_count,
        count(distinct mrp_workorder_id) as work_order_count,
        sum(iff(loss_type = 'productive', duration_minutes, 0)) as productive_minutes,
        sum(iff(loss_type = 'availability', duration_minutes, 0)) as availability_loss_minutes,
        sum(allocated_duration_est) as duration_est_minutes
    from allocated_blocks
    group by workcenter_sk, month_date_key
),

mo_workcenters as (
    select distinct
        workcenter_sk,
        mrp_production_id
    from blocks
    where mrp_production_id is not null
),

quality as (
    select
        map.workcenter_sk,
        to_number(
            to_char(date_trunc('month', d.date_actual), 'YYYYMMDD')
        ) as month_date_key,
        min(mfg.fact_mfg_sk) as src_fact_mfg_sk,
        count(distinct mfg.mrp_production_id) as manufacturing_order_count,
        sum(mfg.qty_produced) as qty_produced,
        sum(mfg.scrap_qty) as scrap_qty
    from mo_workcenters map
    join {{ ref('fact_manufacturing') }} mfg
        on mfg.mrp_production_id = map.mrp_production_id
       and mfg.is_deleted = false
    join {{ ref('dim_date') }} d
        on d.date_key = mfg.completion_date_key
    group by map.workcenter_sk, month_date_key
),

rates as (
    select
        ap.*,
        quality.src_fact_mfg_sk,
        quality.manufacturing_order_count,
        quality.qty_produced,
        quality.scrap_qty,
        ap.productive_minutes
            / nullif(ap.productive_minutes + ap.availability_loss_minutes, 0)
            as availability_pct,
        least(
            greatest(
                ap.duration_est_minutes / nullif(ap.productive_minutes, 0),
                0.0
            ),
            1.0
        ) as performance_pct,
        least(
            greatest(
                (quality.qty_produced - quality.scrap_qty)
                    / nullif(quality.qty_produced, 0),
                0.0
            ),
            1.0
        ) as quality_pct
    from availability_performance ap
    left join quality
        on quality.workcenter_sk = ap.workcenter_sk
       and quality.month_date_key = ap.month_date_key
),

scored as (
    select
        *,
        availability_pct * performance_pct * quality_pct as oee_pct
    from rates
)

select
    {{ dbt_utils.generate_surrogate_key([
        'scored.workcenter_sk',
        'scored.month_date_key'
    ]) }} as mart_oee_sk,
    scored.src_fact_oee_sk,
    scored.src_fact_mfg_sk,
    scored.workcenter_sk,
    scored.month_date_key,
    scored.productivity_block_count,
    scored.work_order_count,
    coalesce(scored.manufacturing_order_count, 0) as manufacturing_order_count,
    scored.productive_minutes,
    scored.availability_loss_minutes,
    scored.duration_est_minutes,
    scored.qty_produced,
    scored.scrap_qty,
    round(scored.availability_pct, 6) as availability_pct,
    round(scored.performance_pct, 6) as performance_pct,
    round(scored.quality_pct, 6) as quality_pct,
    round(scored.oee_pct, 6) as oee_pct,
    round(1 - scored.quality_pct, 6) as defect_rate_pct,
    case
        when scored.oee_pct is null then 'no_data'
        when scored.oee_pct >= 0.85 then 'good'
        when scored.oee_pct >= 0.60 then 'average'
        else 'poor'
    end as oee_segment
from scored
