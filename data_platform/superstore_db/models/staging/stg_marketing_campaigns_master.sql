-- [+] Ánh xạ 1-1 CSV data_source/marketing_campaigns_master.csv. GRAIN: 1 campaign.
-- Nguồn: batch load qua csv_loader/loader.py, KHÔNG qua Debezium/Kafka — vì vậy KHÔNG có
-- cdc_status/is_deleted/_cdc_ts_ms/_cdc_lsn (chỉ CDC mới có). "Bản mới nhất" dùng ingested_at
-- làm chuẩn — hợp lý cho batch file load (1 writer, không có concern replay/out-of-order như CDC).
-- ⚠️ channels PHÂN TÁCH BẰNG DẤU GẠCH ĐỨNG "|", KHÔNG PHẢI DẤU PHẨY như domain-de.dbml/
-- pipeline-schema-map.html ghi — verify trực tiếp trên file thật (VD: "google_search|meta_facebook").
-- is_underperformer lưu dạng chuỗi "YES"/"NO" trong CSV gốc, không phải boolean thật.
{{ config(
    materialized='incremental',
    incremental_strategy='append',
    on_schema_change='sync_all_columns'
) }}
select
    -- File production lấy ID thật từ Odoo utm_campaign. TRY_TO_NUMBER giúp staging
    -- không crash nếu generator offline từng sinh C0001; test not_null sẽ chặn file
    -- đó trước Silver thay vì cho phép join sai.
    raw_data:campaign_id::string           as source_campaign_id,
    try_to_number(raw_data:campaign_id::string) as campaign_id,
    raw_data:campaign_name::string         as campaign_name,
    raw_data:year::number                  as year,
    raw_data:objective::string             as objective,
    raw_data:target_segment::string        as target_segment,
    raw_data:product_focus::string         as product_focus,
    raw_data:channels::string              as channels,
    raw_data:start_date::date              as start_date,
    raw_data:end_date::date                as end_date,
    raw_data:duration_days::number         as duration_days,
    raw_data:total_budget_usd::number      as total_budget_usd,
    raw_data:budget_multiplier::number     as budget_multiplier,
    raw_data:status::string                as status,
    (raw_data:is_underperformer::string = 'YES') as is_underperformer,
    raw_data:notes::string                 as notes,
    raw_data:_source_batch_id::string      as source_batch_id,
    raw_data:_source_file_hash::string     as source_file_hash,
    raw_data:_source_loaded_at::timestamp_ntz as source_loaded_at,
    raw_data:record_hash::string           as record_hash,
    raw_data:ingested_at::timestamp_ntz    as ingested_at
from {{ source('bronze', 'marketing_campaigns_master') }}
{{ incremental_filter() }}
