-- Ánh xạ 1-1 CSV data_source/email_campaigns.csv. GRAIN: 1 email CAMPAIGN/blast gửi tới 1 list
-- (đã pre-aggregate — list_size/delivered/opens/clicks... là COUNT, KHÔNG phải 1 dòng/recipient).
-- Batch load qua csv_loader/loader.py, KHÔNG qua Debezium/Kafka — KHÔNG có cdc_status/is_deleted/
-- _cdc_ts_ms/_cdc_lsn (chỉ CDC mới có). Staging giữ append-only; Silver chọn bản mới nhất
-- theo ingested_at và chỉ phát sinh update khi nội dung source thực sự đổi.
-- ✅ Quyết định thiết kế: dùng CSV ngoài, KHÔNG dùng mass.mailing/mailing.trace của Odoo.
{{ config(
    materialized='incremental',
    incremental_strategy='append',
    on_schema_change='sync_all_columns'
) }}
select
    raw_data:email_id::string              as email_id,
    raw_data:campaign_id::string           as source_campaign_id,
    try_to_number(raw_data:campaign_id::string) as campaign_id,
    raw_data:year::number                  as year,
    raw_data:send_date::date               as send_date,
    raw_data:month::number                 as month,
    raw_data:quarter::string               as quarter,
    raw_data:email_type::string            as email_type,
    raw_data:goal::string                  as goal,
    raw_data:list_name::string             as list_name,
    raw_data:subject_line::string          as subject_line,
    raw_data:sent::number                  as sent,
    raw_data:list_size::number             as list_size,
    raw_data:delivered::number             as delivered,
    raw_data:bounced_total::number         as bounced_total,
    raw_data:hard_bounce::number           as hard_bounce,
    raw_data:soft_bounce::number           as soft_bounce,
    try_to_decimal(raw_data:deliverability::string, 38, 6) as deliverability,
    raw_data:opens::number                 as opens,
    raw_data:unique_opens::number          as unique_opens,
    try_to_decimal(raw_data:open_rate::string, 38, 6) as open_rate,
    raw_data:clicks::number                as clicks,
    raw_data:unique_clicks::number         as unique_clicks,
    try_to_decimal(raw_data:ctr::string, 38, 6) as ctr,
    try_to_decimal(raw_data:ctor::string, 38, 6) as ctor,
    raw_data:unsubscribes::number          as unsubscribes,
    try_to_decimal(raw_data:unsubscribe_rate::string, 38, 6) as unsubscribe_rate,
    raw_data:spam_reports::number          as spam_reports,
    raw_data:conversions::number           as conversions,
    try_to_decimal(raw_data:revenue_usd::string, 38, 6) as revenue_usd,
    try_to_decimal(raw_data:cost_usd::string, 38, 6) as cost_usd,
    try_to_decimal(raw_data:roas::string, 38, 6) as roas,
    try_to_decimal(raw_data:revenue_per_email::string, 38, 6) as revenue_per_email,
    raw_data:_source_batch_id::string             as source_batch_id,
    raw_data:_source_file_hash::string            as source_file_hash,
    raw_data:_source_loaded_at::timestamp_ntz     as source_loaded_at,
    raw_data:record_hash::string            as record_hash,
    raw_data:ingested_at::timestamp_ntz     as ingested_at
from {{ source('bronze', 'email_campaigns') }}
{{ incremental_filter() }}
