-- GRAIN  : 1 month × 1 customer region × 1 product category_l1.
-- SOURCE : fact_sales + historical dimension versions đã được resolve trong Fact.
-- REFRESH: table rebuild để correction/cancellation làm mất một group cũng được phản ánh;
--          incremental MERGE không xóa được group đã biến mất khỏi source aggregate.
{{ config(materialized='table') }}

with sales as (
    select
        fs.fact_sales_sk,
        fs.order_id,
        to_number(
            to_char(date_trunc('month', d.date_actual), 'YYYYMMDD')
        ) as month_date_key,
        coalesce(dc.region, 'Unknown') as region,
        coalesce(dp.category_l1, 'Unknown') as category_l1,
        fs.revenue_amount,
        fs.cost_amount
    from {{ ref('fact_sales') }} fs
    join {{ ref('dim_date') }} d
        on d.date_key = fs.order_date_key
    left join {{ ref('dim_customer') }} dc
        on dc.customer_sk = fs.customer_sk
    left join {{ ref('dim_product') }} dp
        on dp.product_sk = fs.product_sk
    where fs.is_deleted = false
      and coalesce(fs.is_cancelled, false) = false
      and fs.order_state in ('sale', 'done')
),
monthly as (
    select
        month_date_key,
        region,
        category_l1,
        min(fact_sales_sk) as src_fact_sales_sk,
        count(*) as sale_line_count,
        count(distinct order_id) as sales_order_count,
        sum(revenue_amount) as revenue_amount,
        count_if(cost_amount is null) as missing_cost_line_count,
        case
            when count_if(cost_amount is null) > 0 then null
            else sum(cost_amount)
        end as cogs_amount
    from sales
    group by month_date_key, region, category_l1
)

select
    {{ dbt_utils.generate_surrogate_key([
        'monthly.month_date_key',
        'monthly.region',
        'monthly.category_l1'
    ]) }} as mart_revenue_sk,
    monthly.src_fact_sales_sk,
    monthly.region,
    monthly.category_l1,
    monthly.month_date_key,
    monthly.sale_line_count,
    monthly.sales_order_count,
    monthly.revenue_amount,
    monthly.cogs_amount,
    case
        when monthly.missing_cost_line_count > 0 then null
        else monthly.revenue_amount - monthly.cogs_amount
    end as gross_profit_amount,
    monthly.missing_cost_line_count
from monthly
