-- GRAIN   : 1 email campaign/blast (email_id), không phải 1 recipient.
-- SOURCE  : silver → sil_email_campaigns_enriched.
-- DERIVED : count/rate measures giữ nguyên từ source; Mart phải tính lại rate từ SUM.
-- LINK    : campaign_id là utm_campaign.id thật; toàn bộ dòng map channel email_marketing.
{{ config(materialized='table') }}

select
    {{ dbt_utils.generate_surrogate_key(['src.email_id']) }} as fact_email_sk,
    src.email_id,
    src.campaign_id,
    'email_marketing' as channel_code,
    dcamp.campaign_sk,
    dch.channel_sk,
    to_number(to_char(src.send_date, 'YYYYMMDD')) as send_date_key,
    src.email_type,
    src.goal,
    src.list_name,
    src.subject_line,
    src.sent,
    src.list_size,
    src.delivered,
    src.bounced_total,
    src.hard_bounce,
    src.soft_bounce,
    src.opens,
    src.unique_opens,
    src.clicks,
    src.unique_clicks,
    src.unsubscribes,
    src.spam_reports,
    src.conversions,
    src.revenue_usd as revenue_amount,
    src.cost_usd as cost_amount,
    src.deliverability as deliverability_pct,
    src.open_rate as open_pct,
    src.ctr,
    src.ctor,
    src.unsubscribe_rate as unsubscribe_pct,
    src.roas,
    src.revenue_per_email,
    src.ingested_at,
    src.silver_updated_at as source_silver_updated_at,
    src.source_version_key
from {{ ref('sil_email_campaigns_enriched') }} src
left join {{ ref('dim_campaign') }} dcamp
    on dcamp.utm_campaign_id = src.campaign_id
left join {{ ref('dim_channel') }} dch
    on dch.channel_code = 'email_marketing'
