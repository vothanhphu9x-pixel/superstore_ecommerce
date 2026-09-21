-- GRAIN: 1 campaign × 1 date × 1 channel trong snapshot CSV mới nhất.
-- Rebuild table có chủ đích: CSV là full snapshot, vì vậy row bị xóa khỏi file
-- phải biến mất khỏi Silver thay vì tồn tại mãi trong incremental MERGE.
{{ config(materialized='table') }}

with source_batches as (
    select
        *,
        coalesce(source_loaded_at, ingested_at) as effective_loaded_at
    from {{ ref('stg_ad_performance_daily') }}
),
latest_batch as (
    select max(effective_loaded_at) as effective_loaded_at
    from source_batches
),
ad_latest as (
    select src.*
    from source_batches src
    cross join latest_batch batch
    where src.effective_loaded_at = batch.effective_loaded_at
    qualify row_number() over (
        partition by campaign_id, date, channel
        order by ingested_at desc, record_hash desc
    ) = 1
)

select
    source_campaign_id,
    campaign_id,
    campaign_name,
    date,
    channel,
    channel_label,
    channel_type,
    year,
    month,
    quarter,
    spend_usd,
    impressions,
    reach,
    clicks,
    ctr,
    cpc_usd,
    cpm_usd,
    frequency,
    leads,
    conversions,
    conv_rate,
    cpa_usd,
    cpl_usd,
    revenue_usd,
    roas,
    lead_quality_score,
    is_underperformer,
    source_batch_id,
    source_file_hash,
    effective_loaded_at as source_loaded_at,
    ingested_at,
    record_hash as source_version_key,
    effective_loaded_at as silver_updated_at
from ad_latest
