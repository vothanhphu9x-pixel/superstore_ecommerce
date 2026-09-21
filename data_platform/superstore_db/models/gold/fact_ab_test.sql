-- GRAIN   : 1 hàng = 1 A/B test variant (variant_id thuộc test_id).
-- SOURCE  : silver → sil_ab_test_enriched.
-- DERIVED : spend_amount = budget_usd vì nguồn ghi nhận actual budget theo từng variant.
-- LINK    : campaign_id là utm_campaign.id thật; channel map bằng channel_code.
-- REFRESH : rebuild từ full-file snapshot mới nhất; correction, row bị xóa khỏi file và
--           thay đổi dimension key đều được phản ánh mà không phụ thuộc global watermark.
{{ config(materialized='table') }}

select
    {{ dbt_utils.generate_surrogate_key([
        'src.variant_id'
    ]) }} as fact_ab_test_sk,
    src.variant_id,
    src.test_id,
    src.test_name,
    src.variant_name,
    src.campaign_id,
    src.channel as channel_code,
    to_number(to_char(src.start_date, 'YYYYMMDD')) as start_date_key,
    to_number(to_char(src.end_date, 'YYYYMMDD')) as end_date_key,
    src.duration_days,
    dch.channel_sk,
    dcamp.campaign_sk,
    src.is_winner,
    src.budget_usd as budget_amount,
    src.impressions,
    src.clicks,
    src.conversions as conversion_count,
    src.budget_usd as spend_amount,
    src.revenue_usd as revenue_amount,
    src.insight,
    src.ctr,
    src.conv_rate as conv_pct,
    src.roas,
    src.cpa_usd as cpa_amount,
    src.ingested_at,
    src.silver_updated_at as source_silver_updated_at,
    src.source_version_key
from {{ ref('sil_ab_test_enriched') }} src
left join {{ ref('dim_channel') }} dch
    on dch.channel_code = src.channel
left join {{ ref('dim_campaign') }} dcamp
    on dcamp.utm_campaign_id = src.campaign_id
