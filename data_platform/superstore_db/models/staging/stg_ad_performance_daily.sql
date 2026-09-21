-- (đổi tên từ stg_ad_spend_raw, naming_convention §5.3 — grain là daily performance, không chỉ spend)
-- Ánh xạ 1-1 CSV data_source/ad_performance_daily.csv. GRAIN: 1 date × campaign_id × channel.
-- Batch load, KHÔNG qua Debezium/Kafka. Staging giữ append-only; Silver chọn bản mới nhất
-- theo ingested_at và chỉ phát sinh update khi nội dung business thực sự đổi.
-- ⚠️ CSV KHÔNG có cột "source" — bản nháp trước có cột này là sai, đã loại bỏ (domain-de.dbml).
{{ config(
    materialized='incremental',
    incremental_strategy='append',
    on_schema_change='sync_all_columns'
) }}
select
    raw_data:date::date                    as date,
    raw_data:campaign_id::string           as source_campaign_id,
    try_to_number(raw_data:campaign_id::string) as campaign_id,
    raw_data:campaign_name::string         as campaign_name,
    raw_data:channel::string               as channel,
    raw_data:channel_label::string         as channel_label,
    raw_data:channel_type::string          as channel_type,
    raw_data:year::number                  as year,
    raw_data:month::number                 as month,
    raw_data:quarter::string               as quarter,
    try_to_decimal(raw_data:spend_usd::string, 38, 6)          as spend_usd,
    try_to_number(raw_data:impressions::string)                as impressions,
    try_to_number(raw_data:reach::string)                      as reach,
    try_to_number(raw_data:clicks::string)                     as clicks,
    try_to_decimal(raw_data:ctr::string, 38, 6)                as ctr,
    try_to_decimal(raw_data:cpc_usd::string, 38, 6)            as cpc_usd,
    try_to_decimal(raw_data:cpm_usd::string, 38, 6)            as cpm_usd,
    try_to_decimal(raw_data:frequency::string, 38, 6)          as frequency,
    try_to_number(raw_data:leads::string)                      as leads,
    try_to_number(raw_data:conversions::string)                as conversions,
    try_to_decimal(raw_data:conv_rate::string, 38, 6)          as conv_rate,
    try_to_decimal(raw_data:cpa_usd::string, 38, 6)            as cpa_usd,
    try_to_decimal(raw_data:cpl_usd::string, 38, 6)            as cpl_usd,
    try_to_decimal(raw_data:revenue_usd::string, 38, 6)        as revenue_usd,
    try_to_decimal(raw_data:roas::string, 38, 6)               as roas,
    try_to_decimal(raw_data:lead_quality_score::string, 38, 6) as lead_quality_score,
    upper(trim(raw_data:is_underperformer::string)) in ('YES', 'TRUE', '1')
                                                                as is_underperformer,
    raw_data:_source_batch_id::string                            as source_batch_id,
    raw_data:_source_file_hash::string                           as source_file_hash,
    raw_data:_source_loaded_at::timestamp_ntz                    as source_loaded_at,
    raw_data:record_hash::string                                as record_hash,
    raw_data:ingested_at::timestamp_ntz                         as ingested_at
from {{ source('bronze', 'ad_performance_daily') }}
{{ incremental_filter() }}
