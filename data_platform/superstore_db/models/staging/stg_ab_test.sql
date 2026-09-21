-- Ánh xạ 1-1 CSV data_source/ab_test_results.csv.
-- GRAIN: 1 variant_id (thuộc test_id). Batch load, KHÔNG qua Debezium/Kafka.
-- Staging append-only; Silver chọn version mới nhất và nhận diện correction bằng record_hash.
{{ config(
    materialized='incremental',
    incremental_strategy='append',
    on_schema_change='sync_all_columns'
) }}
select
    raw_data:test_id::string               as test_id,
    raw_data:variant_id::string            as variant_id,
    raw_data:campaign_id::string           as source_campaign_id,
    try_to_number(raw_data:campaign_id::string) as campaign_id,
    raw_data:year::number                  as year,
    raw_data:test_name::string             as test_name,
    raw_data:channel::string               as channel,
    raw_data:start_date::date              as start_date,
    raw_data:end_date::date                as end_date,
    try_to_number(raw_data:duration_days::string) as duration_days,
    raw_data:variant_name::string          as variant_name,
    upper(trim(raw_data:is_winner::string)) in ('YES', 'TRUE', '1') as is_winner,
    try_to_decimal(raw_data:budget_usd::string, 38, 6) as budget_usd,
    try_to_number(raw_data:impressions::string)        as impressions,
    try_to_number(raw_data:clicks::string)             as clicks,
    try_to_decimal(raw_data:ctr::string, 38, 6)        as ctr,
    try_to_number(raw_data:conversions::string)        as conversions,
    try_to_decimal(raw_data:conv_rate::string, 38, 6)  as conv_rate,
    try_to_decimal(raw_data:revenue_usd::string, 38, 6) as revenue_usd,
    try_to_decimal(raw_data:roas::string, 38, 6)       as roas,
    try_to_decimal(raw_data:cpa_usd::string, 38, 6)    as cpa_usd,
    raw_data:insight::string               as insight,
    raw_data:_source_batch_id::string      as source_batch_id,
    raw_data:_source_file_hash::string     as source_file_hash,
    raw_data:_source_loaded_at::timestamp_ntz as source_loaded_at,
    raw_data:record_hash::string           as record_hash,
    raw_data:ingested_at::timestamp_ntz    as ingested_at
from {{ source('bronze', 'ab_test') }}
{{ incremental_filter() }}
