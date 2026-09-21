-- Fact incremental phải tự re-key khi dimension SCD1/lookup được backfill hoặc correction,
-- kể cả source Silver không đổi và source_silver_updated_at vẫn giữ nguyên.
with medium_latest as (
    select *
    from {{ ref('stg_utm_medium') }}
    where is_deleted = false
    qualify row_number() over (
        partition by utm_medium_id
        order by _cdc_ts_ms desc, _cdc_lsn desc
    ) = 1
),
sales_expected as (
    select
        src.sale_order_line_id,
        warehouse.warehouse_sk,
        campaign.campaign_sk,
        channel.channel_sk
    from {{ ref('sil_order_lines_enriched') }} src
    left join {{ ref('dim_warehouse') }} warehouse
        on warehouse.warehouse_id = src.warehouse_id
    left join {{ ref('dim_campaign') }} campaign
        on campaign.utm_campaign_id = src.campaign_id
    left join medium_latest medium
        on medium.utm_medium_id = src.medium_id
    left join {{ ref('dim_channel') }} channel
        on channel.channel_code = lower(medium.name)
),
crm_expected as (
    select
        src.crm_lead_id,
        campaign.campaign_sk,
        channel.channel_sk
    from {{ ref('sil_crm_lead_enriched') }} src
    left join {{ ref('dim_campaign') }} campaign
        on campaign.utm_campaign_id = src.campaign_id
    left join medium_latest medium
        on medium.utm_medium_id = src.medium_id
    left join {{ ref('dim_channel') }} channel
        on channel.channel_code = lower(medium.name)
)

select
    'fact_sales' as model_name,
    fact.sale_order_line_id::varchar as business_key,
    'warehouse/campaign/channel' as lookup_name
from {{ ref('fact_sales') }} fact
join sales_expected expected
    on expected.sale_order_line_id = fact.sale_order_line_id
where not equal_null(fact.warehouse_sk, expected.warehouse_sk)
   or not equal_null(fact.campaign_sk, expected.campaign_sk)
   or not equal_null(fact.channel_sk, expected.channel_sk)

union all

select
    'fact_crm_funnel',
    fact.crm_lead_id::varchar,
    'campaign/channel'
from {{ ref('fact_crm_funnel') }} fact
join crm_expected expected
    on expected.crm_lead_id = fact.crm_lead_id
where not equal_null(fact.campaign_sk, expected.campaign_sk)
   or not equal_null(fact.channel_sk, expected.channel_sk)
