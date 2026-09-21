-- GRAIN   : 1 hàng = 1 VERSION LỊCH SỬ của 1 res_partner (SCD2 đầy đủ — gold KHÔNG filter
--           current nữa, giữ TOÀN BỘ lịch sử như silver, chỉ thêm surrogate key + rename +
--           conformed schema). is_current=true đánh dấu bản hiện hành, is_deleted đã lọc từ silver.
-- SOURCE  : silver → sil_customer_enriched (snap_res_partner)
-- DERIVED : n/a (pass-through + is_current/partner_type từ silver)
-- TEST    : unique(customer_sk), not_null(partner_id), relationships hợp lệ mọi fact.customer_sk
-- ⚠️ ĐỔI KIẾN TRÚC (2026-07-28): gold trước đây current-only (unique_key=partner_id, filter
-- dbt_valid_to IS NULL) — nay đổi sang giữ full history để fact có thể temporal join theo
-- thời điểm Silver xử lý record. "Current view" đẩy xuống
-- mart (WHERE is_current=true). unique_key=dbt_scd_id (ổn định theo version, KHÔNG phải
-- partner_id — partner_id giờ KHÔNG unique, có nhiều version/partner).
-- Gold intentionally MERGE toàn bộ Silver dimension mỗi run. Dimension nhỏ hơn fact và
-- cách này bảo đảm closure/correction của cùng dbt_scd_id luôn cập nhật xuống Gold.
{{ config(
    materialized='incremental',
    incremental_strategy='merge',
    unique_key='dbt_scd_id',
    on_schema_change='sync_all_columns'
) }}
select
    {{ dbt_utils.generate_surrogate_key(['dbt_scd_id']) }}    as customer_sk,
    partner_id,
    commercial_partner_id,
    customer_name,
    segment,
    city,
    state,
    zip,
    country,
    region,
    is_company,
    customer_rank,
    supplier_rank,
    partner_type,
    email,
    phone,
    rfm_profile,
    is_active,
    is_current,
    dbt_valid_from,
    dbt_valid_to,
    dbt_scd_id,
    source_cdc_ts_ms,
    source_cdc_lsn,
    enrichment_version_key,
    enrichment_updated_at,
    greatest_ignore_nulls(
        dbt_valid_from,
        dbt_valid_to,
        enrichment_updated_at
    )                                  as dim_updated_at,
    dbt_valid_from                     as dbt_updated_at,
    {{ pipeline_now() }}                as gold_refreshed_at
from {{ ref('sil_customer_enriched') }}
