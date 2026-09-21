-- GRAIN: 1 A/B test variant trong snapshot CSV mới nhất.
-- Rebuild table để correction và row bị xóa trong full-file snapshot được phản ánh đúng.
{{ config(materialized='table') }}

with source_batches as (
    select
        *,
        coalesce(source_loaded_at, ingested_at) as effective_loaded_at
    from {{ ref('stg_ab_test') }}
),
latest_batch as (
    select max(effective_loaded_at) as effective_loaded_at
    from source_batches
),
test_latest as (
    select src.*
    from source_batches src
    cross join latest_batch batch
    where src.effective_loaded_at = batch.effective_loaded_at
    qualify row_number() over (
        partition by variant_id
        order by ingested_at desc, record_hash desc
    ) = 1
)

select
    test_id,
    variant_id,
    source_campaign_id,
    campaign_id,
    year,
    test_name,
    channel,
    start_date,
    end_date,
    duration_days,
    variant_name,
    is_winner,
    budget_usd,
    impressions,
    clicks,
    ctr,
    conversions,
    conv_rate,
    revenue_usd,
    roas,
    cpa_usd,
    insight,
    source_batch_id,
    source_file_hash,
    effective_loaded_at as source_loaded_at,
    ingested_at,
    record_hash as source_version_key,
    effective_loaded_at as silver_updated_at
from test_latest
