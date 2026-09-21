-- GRAIN: 1 version lịch sử của 1 partner (SCD2 — giữ TOÀN BỘ version).
-- Incremental MERGE theo dbt_scd_id. Khi boundary hoặc lookup enrichment đổi,
-- reload toàn bộ versions của partner đó để version cũ vừa đóng được cập nhật.
{{ config(
    materialized='incremental',
    incremental_strategy='merge',
    unique_key='dbt_scd_id',
    on_schema_change='sync_all_columns',
    full_refresh=false
) }}

{% set target_has_enrichment_key =
    is_incremental() and relation_has_column(this, 'enrichment_version_key')
%}

with country_state_latest as (
    select *
    from {{ ref('stg_res_country_state') }}
    qualify row_number() over (
        partition by state_id
        order by _cdc_ts_ms desc, _cdc_lsn desc
    ) = 1
),
country_latest as (
    select *
    from {{ ref('stg_res_country') }}
    qualify row_number() over (
        partition by country_id
        order by _cdc_ts_ms desc, _cdc_lsn desc
    ) = 1
),
state_region as (
    select
        state_id,
        country_id,
        iff(is_deleted, null, code) as code,
        _cdc_ts_ms,
        case
            when is_deleted then 'Unknown'
            when code in ('CA','WA','OR','NV','AZ','NM','CO','UT','ID','MT','WY','AK','HI') then 'West'
            when code in ('NY','NJ','CT','MA','RI','VT','NH','ME','PA','DE','DC') then 'East'
            when code in ('TX','FL','GA','NC','SC','AL','MS','LA','AR','TN','KY','VA','WV','MD','OK') then 'South'
            when code is null then 'Unknown'
            else 'Central'
        end as region
    from country_state_latest
),
category_rel_latest as (
    select *
    from {{ ref('stg_res_partner_res_partner_category_rel') }}
    qualify row_number() over (
        partition by partner_id, category_id
        order by _cdc_ts_ms desc, _cdc_lsn desc
    ) = 1
),
category_latest as (
    select *
    from {{ ref('stg_res_partner_category') }}
    qualify row_number() over (
        partition by category_id
        order by _cdc_ts_ms desc, _cdc_lsn desc
    ) = 1
),
partner_tag_rows as (
    select
        rel.partner_id,
        iff(
            rel.is_deleted = false and cat.is_deleted = false,
            cat.name,
            null
        ) as tag_name,
        greatest_ignore_nulls(rel._cdc_ts_ms, cat._cdc_ts_ms) as tag_cdc_ts_ms
    from category_rel_latest rel
    join category_latest cat
        on cat.category_id = rel.category_id
    where cat.name in ('Consumer', 'Corporate', 'Home Office')
),
partner_tags as (
    select
        partner_id,
        listagg(distinct tag_name, ', ') within group (order by tag_name) as segment,
        max(tag_cdc_ts_ms) as tags_cdc_ts_ms
    from partner_tag_rows
    group by partner_id
),
source_versions as (
    select *
    from {{ ref('snap_res_partner') }}
    where is_deleted = false
),
source_enriched as (
    select
        snap.*,
        coalesce(snap.commercial_partner_id, snap.partner_id) as resolved_commercial_partner_id,
        pt.segment,
        sr.code as state_code,
        case
            when c.code = 'US' then sr.region
            when c.country_id is not null then 'International'
            else 'Unknown'
        end as resolved_region,
        coalesce(iff(c.is_deleted, null, c.name), 'Unknown') as country_name,
        {{ dbt_utils.generate_surrogate_key([
            "coalesce(pt.segment, '__NULL__')",
            "coalesce(sr.code, '__NULL__')",
            "coalesce(sr.region, '__NULL__')",
            "coalesce(c.name, '__NULL__')",
            "coalesce(c.is_deleted, false)"
        ]) }} as enrichment_version_key,
        {{ deb_cdc_ts("greatest_ignore_nulls(pt.tags_cdc_ts_ms, sr._cdc_ts_ms, c._cdc_ts_ms)") }}
            as enrichment_updated_at
    from source_versions snap
    left join partner_tags pt
        on pt.partner_id = snap.partner_id
    left join state_region sr
        on sr.state_id = snap.state_id
    left join country_latest c
        on c.country_id = coalesce(snap.country_id, sr.country_id)
),
changed_partners as (
    {% if is_incremental() %}
    select distinct src.partner_id
    from source_enriched src
    left join {{ this }} tgt
        on tgt.dbt_scd_id = src.dbt_scd_id
    where tgt.dbt_scd_id is null
       or coalesce(tgt.dbt_valid_to, '9999-12-31'::timestamp)
          <> coalesce(src.dbt_valid_to, '9999-12-31'::timestamp)
       or coalesce(tgt.is_current, false) <> (src.dbt_valid_to is null)
       {% if target_has_enrichment_key %}
       or coalesce(tgt.enrichment_version_key, '__NULL__')
          <> coalesce(src.enrichment_version_key, '__NULL__')
       {% else %}
       -- Rollout lần đầu: target cũ chưa có enrichment_version_key.
       or 1 = 1
       {% endif %}
    {% else %}
    select distinct partner_id
    from source_enriched
    {% endif %}
)

select
    snap.dbt_scd_id,
    snap.partner_id,
    snap.resolved_commercial_partner_id as commercial_partner_id,
    snap.name as customer_name,
    snap.city,
    snap.state_code as state,
    snap.zip,
    snap.country_name as country,
    snap.resolved_region as region,
    snap.is_company,
    snap.customer_rank,
    snap.supplier_rank,
    case
        when snap.customer_rank > 0 and snap.supplier_rank > 0 then 'both'
        when snap.customer_rank > 0 then 'customer'
        when snap.supplier_rank > 0 then 'vendor'
        else 'other'
    end as partner_type,
    snap.email,
    snap.phone,
    snap.ref as rfm_profile,
    snap.active as is_active,
    (snap.dbt_valid_to is null) as is_current,
    snap.segment,
    snap.dbt_valid_from,
    snap.dbt_valid_to,
    snap._cdc_ts_ms as source_cdc_ts_ms,
    snap._cdc_lsn as source_cdc_lsn,
    snap.enrichment_version_key,
    {{ pipeline_now() }} as enrichment_updated_at
from source_enriched snap
join changed_partners cp
    on cp.partner_id = snap.partner_id
