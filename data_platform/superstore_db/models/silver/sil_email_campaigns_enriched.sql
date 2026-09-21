-- GRAIN: 1 email campaign/blast trong snapshot CSV mới nhất.
-- Rebuild table để correction và row bị xóa trong full-file snapshot được phản ánh đúng.
{{ config(materialized='table') }}

with source_batches as (
    select
        *,
        coalesce(source_loaded_at, ingested_at) as effective_loaded_at
    from {{ ref('stg_email_campaigns') }}
),
latest_batch as (
    select max(effective_loaded_at) as effective_loaded_at
    from source_batches
),
email_latest as (
    select src.*
    from source_batches src
    cross join latest_batch batch
    where src.effective_loaded_at = batch.effective_loaded_at
    qualify row_number() over (
        partition by email_id
        order by ingested_at desc, record_hash desc
    ) = 1
)

select
    email_id,
    source_campaign_id,
    campaign_id,
    year,
    send_date,
    month,
    quarter,
    email_type,
    goal,
    list_name,
    subject_line,
    sent,
    list_size,
    delivered,
    bounced_total,
    hard_bounce,
    soft_bounce,
    deliverability,
    opens,
    unique_opens,
    open_rate,
    clicks,
    unique_clicks,
    ctr,
    ctor,
    unsubscribes,
    unsubscribe_rate,
    spam_reports,
    conversions,
    revenue_usd,
    cost_usd,
    roas,
    revenue_per_email,
    source_batch_id,
    source_file_hash,
    effective_loaded_at as source_loaded_at,
    ingested_at,
    record_hash as source_version_key,
    effective_loaded_at as silver_updated_at
from email_latest
