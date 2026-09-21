-- GRAIN   : 1 campaign × 1 date × 1 channel.
-- SOURCE  : silver → sil_ad_performance_daily_enriched.
-- DERIVED : measures/ratios ngày giữ nguyên từ source; Mart phải tính lại ratio từ SUM.
-- LƯU Ý   : reported_revenue_amount là doanh thu do nguồn marketing báo cáo,
--           không đồng nghĩa doanh thu ERP đã được ghi nhận/attributed.
{{ config(materialized='table') }}

select
    {{ dbt_utils.generate_surrogate_key([
        'src.campaign_id',
        'src.date',
        'src.channel'
    ]) }} as fact_ad_spend_sk,
    src.campaign_id,
    src.date as spend_date,
    src.channel,
    to_number(to_char(src.date, 'YYYYMMDD')) as spend_date_key,
    dcamp.campaign_sk,
    dch.channel_sk,
    src.campaign_name,
    src.channel_label,
    src.channel_type,
    src.spend_usd as spend_amount,
    src.revenue_usd as reported_revenue_amount,
    src.impressions,
    src.reach,
    src.clicks,
    src.leads,
    src.conversions,
    src.is_underperformer,
    src.ctr,
    src.cpc_usd as cpc_amount,
    src.cpm_usd as cpm_amount,
    src.frequency,
    src.conv_rate as conversion_rate,
    src.cpa_usd as cpa_amount,
    src.cpl_usd as cpl_amount,
    src.roas,
    src.lead_quality_score,
    src.ingested_at,
    src.silver_updated_at as source_silver_updated_at,
    src.source_version_key
from {{ ref('sil_ad_performance_daily_enriched') }} src
left join {{ ref('dim_campaign') }} dcamp
    on dcamp.utm_campaign_id = src.campaign_id
left join {{ ref('dim_channel') }} dch
    on dch.channel_code = src.channel
