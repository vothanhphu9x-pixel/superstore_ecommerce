-- GRAIN   : 1 hàng = 1 VERSION LỊCH SỬ của 1 hr_contract (SCD2 đầy đủ — xem giải thích đổi
--           kiến trúc ở dim_customer, cùng lý do/cùng ngày). is_current=true = bản hiện hành.
-- SOURCE  : silver → sil_employee_enriched (snap_hr_contract)
-- DERIVED : n/a (pass-through + is_current, user_id→employee_id map qua stg_res_users)
-- TEST    : unique(employee_sk), not_null(employee_id), relationships hợp lệ fact_sales.salesperson_sk, fact_purchase.buyer_sk
-- unique_key=dbt_scd_id (employee_id KHÔNG unique — nhiều version/employee theo hợp đồng).
-- MERGE toàn bộ Silver dimension để closure/correction của version cũ không bị watermark bỏ sót.
{{ config(
    materialized='incremental',
    incremental_strategy='merge',
    unique_key='dbt_scd_id',
    on_schema_change='sync_all_columns'
) }}
select
    {{ dbt_utils.generate_surrogate_key(['dbt_scd_id']) }}    as employee_sk,
    employee_id,
    contract_id,
    user_id,
    employee_name,
    department_name,
    job_title,
    wage_amount,
    wage_band,
    employee_type,
    contract_start,
    contract_end,
    first_contract_start,
    round(
        datediff('day', first_contract_start, coalesce(contract_end, {{ pipeline_today() }})) / 365.25,
        2
    )                                  as tenure_years,
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
from {{ ref('sil_employee_enriched') }}
