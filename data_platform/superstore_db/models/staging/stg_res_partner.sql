-- 1:1 res.partner. GRAIN: 1 CDC event (append-only — KHÔNG dedup, xem naming_convention).
-- Field list khớp snowflake-schema-domain-de.dbml (REFERENCE_CUSTOMER).
{{ config(
    materialized='incremental',
    incremental_strategy='append',
    on_schema_change='sync_all_columns'
) }}
select
    raw_data:id::number                as partner_id,
    raw_data:name::string              as name,
    raw_data:is_company::boolean       as is_company,
    raw_data:parent_id::number         as parent_id,
    raw_data:commercial_partner_id::number as commercial_partner_id,
    raw_data:customer_rank::number     as customer_rank,
    raw_data:supplier_rank::number     as supplier_rank,
    raw_data:state_id::number          as state_id,
    raw_data:country_id::number        as country_id,
    raw_data:city::string              as city,
    raw_data:zip::string               as zip,
    raw_data:email::string             as email,
    raw_data:phone::string             as phone,
    raw_data:comment::string           as comment,
    -- ref không có trong field list của naming_convention/domain-de.dbml nhưng verify tồn tại
    -- thật trên res_partner qua information_schema — cần cho dim_customer.rfm_profile
    -- (gold_layer_sql dùng đúng field này; domain-de.dbml có vẻ bỏ sót khi liệt kê).
    raw_data:ref::string               as ref,
    raw_data:active::boolean           as active,
    {{ deb_ts('raw_data:write_date') }} as write_date,
    raw_data:cdc_status::string        as cdc_status,
    raw_data:is_deleted::boolean       as is_deleted,
    raw_data:_cdc_ts_ms::number        as _cdc_ts_ms,
    raw_data:_cdc_lsn::number          as _cdc_lsn,
    raw_data:ingested_at::timestamp_ntz as ingested_at
from {{ source('bronze', 'res_partner') }}
{{ incremental_filter() }}
