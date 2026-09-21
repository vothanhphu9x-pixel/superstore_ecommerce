-- GRAIN   : 1 hàng = 1 crm_lead
-- SOURCE  : silver → sil_crm_lead_enriched
-- DERIVED : close_days = datediff(day, date_open, date_closed);
--           channel_sk resolve qua medium_id → stg_utm_medium.name ≈ dim_channel.channel_code
--           (cùng kỹ thuật sil_channel_enriched — JOIN theo TÊN, không phải FK id)
-- TEST    : unique(fact_crm_sk), not_null(open_date_key), relationships(dim_campaign, dim_channel)
-- customer_sk temporal join theo Silver processing time; date_open chỉ phục vụ business analysis.
{{ config(
    materialized='incremental',
    incremental_strategy='merge',
    unique_key='crm_lead_id',
    on_schema_change='sync_all_columns'
) }}

with stage_latest as (
    select *
    from {{ ref('stg_crm_stage') }}
    where is_deleted = false
    qualify row_number() over (
        partition by stage_id
        order by _cdc_ts_ms desc, _cdc_lsn desc
    ) = 1
),
lost_reason_latest as (
    select *
    from {{ ref('stg_crm_lost_reason') }}
    where is_deleted = false
    qualify row_number() over (
        partition by lost_reason_id
        order by _cdc_ts_ms desc, _cdc_lsn desc
    ) = 1
),
medium_latest as (
    select *
    from {{ ref('stg_utm_medium') }}
    where is_deleted = false
    qualify row_number() over (
        partition by utm_medium_id
        order by _cdc_ts_ms desc, _cdc_lsn desc
    ) = 1
)
select
    {{ dbt_utils.generate_surrogate_key(['ld.crm_lead_id']) }} as fact_crm_sk,
    ld.crm_lead_id,
    to_number(to_char(ld.date_open, 'YYYYMMDD'))       as open_date_key,
    to_number(to_char(ld.date_closed, 'YYYYMMDD'))     as closed_date_key,
    dc.customer_sk,
    dcamp.campaign_sk,
    dch.channel_sk,
    ld.type                                             as lead_type,
    st.name                                             as stage_name,
    ld.probability,
    ld.expected_revenue                                 as expected_revenue_amount,
    coalesce(st.is_won, false)                          as is_won,
    datediff('day', ld.date_open, ld.date_closed)       as close_days,
    lr.name                                             as lost_reason,
    ld.is_deleted,
    ld.silver_updated_at                                as source_silver_updated_at,
    ld.source_version_key,
    ld._cdc_ts_ms                                      as lead_cdc_ts_ms,
    ld._cdc_lsn                                        as lead_cdc_lsn,
    dc.dim_updated_at                                   as customer_dim_updated_at
from {{ ref('sil_crm_lead_enriched') }} ld
left join stage_latest st
    on st.stage_id = ld.stage_id
left join lost_reason_latest lr
    on lr.lost_reason_id = ld.lost_reason_id
left join medium_latest md
    on md.utm_medium_id = ld.medium_id
left join {{ ref('dim_channel') }} dch
    on dch.channel_code = lower(md.name)
left join {{ ref('dim_customer') }} dc
    on dc.partner_id = ld.partner_id
   and ld.silver_updated_at >= dc.dbt_valid_from
   and ld.silver_updated_at < coalesce(dc.dbt_valid_to, '9999-12-31'::timestamp)
left join {{ ref('dim_campaign') }} dcamp
    on dcamp.utm_campaign_id = ld.campaign_id
{% if is_incremental() %}
left join {{ this }} tgt
    on tgt.crm_lead_id = ld.crm_lead_id
where tgt.crm_lead_id is null
   or ld.silver_updated_at > coalesce(
        tgt.source_silver_updated_at,
        '1900-01-01'::timestamp
   )
   or coalesce(dc.customer_sk, '__NULL__') <> coalesce(tgt.customer_sk, '__NULL__')
   -- medium/campaign lookup có thể được backfill sau khi lead source đã đứng yên.
   or coalesce(dcamp.campaign_sk, '__NULL__') <> coalesce(tgt.campaign_sk, '__NULL__')
   or coalesce(dch.channel_sk, '__NULL__') <> coalesce(tgt.channel_sk, '__NULL__')
   or coalesce(
        dc.dim_updated_at,
        '1900-01-01'::timestamp
   ) > coalesce(
        tgt.customer_dim_updated_at,
        '1900-01-01'::timestamp
   )
{% endif %}
