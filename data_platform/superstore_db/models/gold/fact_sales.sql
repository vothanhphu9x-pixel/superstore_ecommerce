-- GRAIN   : 1 hàng = 1 order line (sale_order_line_id)
-- SOURCE  : silver → sil_order_lines_enriched
-- DERIVED : revenue_amount đã tính sẵn ở silver. cost_amount dùng product version tại
--           silver_updated_at.
-- TEST    : unique(fact_sales_sk), not_null(customer_sk), not_null(order_date_key),
--           relationships(dim_customer, dim_product, dim_date, dim_warehouse, dim_channel, dim_employee)
-- channel_sk resolve qua medium_id → stg_utm_medium.name ≈ dim_channel.channel_code (cùng kỹ
-- thuật sil_channel_enriched/fact_crm_funnel — JOIN theo TÊN, không phải FK id).
-- customer/product/employee temporal join theo Silver processing time; date_order chỉ dùng
-- cho reporting và date dimension.
-- opportunity_id được truyền từ sale_order để attribution về CRM cohort. on_schema_change thêm
-- cột khi deploy; source_version_key của Silver phát hiện cả backfill và thay đổi về sau nên
-- không cần full-refresh fact_sales chỉ vì bổ sung opportunity_id.
{{ config(
    materialized='incremental',
    incremental_strategy='merge',
    unique_key='sale_order_line_id',
    on_schema_change='sync_all_columns'
) }}

select
    {{ dbt_utils.generate_surrogate_key(['sol.sale_order_line_id']) }} as fact_sales_sk,
    sol.sale_order_line_id,
    sol.order_id,
    sol.opportunity_id,
    sol.order_name,
    to_number(to_char(sol.date_order, 'YYYYMMDD'))     as order_date_key,
    dc.customer_sk,
    dp.product_sk,
    dw.warehouse_sk,
    dcamp.campaign_sk,
    dch.channel_sk,
    de.employee_sk                                     as salesperson_sk,
    sol.quantity,
    sol.quantity_delivered,
    sol.price_unit,
    sol.discount_pct,
    sol.revenue_amount,
    round(sol.quantity * dp.standard_cost_amount, 2)   as cost_amount,
    round(sol.revenue_amount - (sol.quantity * dp.standard_cost_amount), 2) as gross_profit_amount,
    sol.order_state,
    sol.invoice_status,
    sol.delivery_status,
    sol.is_cancelled,
    sol.is_deleted,
    sol.silver_updated_at                              as source_silver_updated_at,
    sol.source_version_key,
    sol.line_cdc_ts_ms,
    sol.line_cdc_lsn,
    sol.order_cdc_ts_ms,
    sol.order_cdc_lsn,
    dc.dim_updated_at                                  as customer_dim_updated_at,
    dp.dim_updated_at                                  as product_dim_updated_at,
    de.dim_updated_at                                  as employee_dim_updated_at
from {{ ref('sil_order_lines_enriched') }} sol
left join {{ ref('dim_customer') }} dc
    on dc.partner_id = sol.partner_id
   and sol.silver_updated_at >= dc.dbt_valid_from
   and sol.silver_updated_at < coalesce(dc.dbt_valid_to, '9999-12-31'::timestamp)
left join {{ ref('dim_product') }} dp
    on dp.product_id = sol.product_id
   and sol.silver_updated_at >= dp.dbt_valid_from
   and sol.silver_updated_at < coalesce(dp.dbt_valid_to, '9999-12-31'::timestamp)
left join {{ ref('dim_employee') }} de
    on de.user_id = sol.user_id
   and sol.silver_updated_at >= de.dbt_valid_from
   and sol.silver_updated_at < coalesce(de.dbt_valid_to, '9999-12-31'::timestamp)
left join {{ ref('dim_warehouse') }} dw
    on dw.warehouse_id = sol.warehouse_id
left join {{ ref('dim_campaign') }} dcamp
    on dcamp.utm_campaign_id = sol.campaign_id
left join (
    select *
    from {{ ref('stg_utm_medium') }}
    where is_deleted = false
    qualify row_number() over (
        partition by utm_medium_id
        order by _cdc_ts_ms desc, _cdc_lsn desc
    ) = 1
) md
    on md.utm_medium_id = sol.medium_id
left join {{ ref('dim_channel') }} dch
    on dch.channel_code = lower(md.name)
{% if is_incremental() %}
left join {{ this }} tgt
    on tgt.sale_order_line_id = sol.sale_order_line_id
where tgt.sale_order_line_id is null
   or sol.silver_updated_at > coalesce(
        tgt.source_silver_updated_at,
        '1900-01-01'::timestamp
   )
   or coalesce(dc.customer_sk, '__NULL__') <> coalesce(tgt.customer_sk, '__NULL__')
   or coalesce(dp.product_sk, '__NULL__') <> coalesce(tgt.product_sk, '__NULL__')
   or coalesce(de.employee_sk, '__NULL__') <> coalesce(tgt.salesperson_sk, '__NULL__')
   -- Bắt late-arriving/correction của các dimension SCD1 lookup dù order source không đổi.
   or coalesce(dw.warehouse_sk, '__NULL__') <> coalesce(tgt.warehouse_sk, '__NULL__')
   or coalesce(dcamp.campaign_sk, '__NULL__') <> coalesce(tgt.campaign_sk, '__NULL__')
   or coalesce(dch.channel_sk, '__NULL__') <> coalesce(tgt.channel_sk, '__NULL__')
   or coalesce(dc.dim_updated_at, '1900-01-01'::timestamp) > coalesce(
        tgt.customer_dim_updated_at,
        '1900-01-01'::timestamp
   )
   or coalesce(dp.dim_updated_at, '1900-01-01'::timestamp) > coalesce(
        tgt.product_dim_updated_at,
        '1900-01-01'::timestamp
   )
   or coalesce(
        de.dim_updated_at,
        '1900-01-01'::timestamp
   ) > coalesce(
        tgt.employee_dim_updated_at,
        '1900-01-01'::timestamp
   )
{% endif %}
