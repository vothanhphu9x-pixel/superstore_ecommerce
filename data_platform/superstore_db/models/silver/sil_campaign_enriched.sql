-- GRAIN: 1 campaign (static — không SCD2). campaign_id của CSV là utm_campaign.id thật.
-- JOIN bằng ID kỹ thuật đã xác minh; tên chỉ là thuộc tính hiển thị, không dùng làm khóa.
-- source_name lấy qua crm_lead.source_id phổ biến nhất của campaign (utm_campaign không có FK
-- trực tiếp tới utm_source) — có thể NULL nếu campaign chưa gắn lead nào.
{{ config(materialized='table') }}

with latest_master_batch as (
    select max(coalesce(source_loaded_at, ingested_at)) as loaded_at
    from {{ ref('stg_marketing_campaigns_master') }}
),
campaign_master_latest as (
    select m.*
    from {{ ref('stg_marketing_campaigns_master') }} m
    cross join latest_master_batch b
    where coalesce(m.source_loaded_at, m.ingested_at) = b.loaded_at
    qualify row_number() over (partition by campaign_id order by ingested_at desc) = 1
),
utm_campaign_latest as (
    select *
    from {{ ref('stg_utm_campaign') }}
    where is_deleted = false
    qualify row_number() over (partition by utm_campaign_id order by _cdc_ts_ms desc, _cdc_lsn desc) = 1
),
crm_lead_latest as (
    select *
    from {{ ref('stg_crm_lead') }}
    where is_deleted = false
    qualify row_number() over (partition by crm_lead_id order by _cdc_ts_ms desc, _cdc_lsn desc) = 1
),
utm_source_latest as (
    select *
    from {{ ref('stg_utm_source') }}
    where is_deleted = false
    qualify row_number() over (partition by source_id order by _cdc_ts_ms desc, _cdc_lsn desc) = 1
),
campaign_source_counts as (
    select
        cl.campaign_id  as utm_campaign_id,
        us.source_name,
        count(*)        as lead_count
    from crm_lead_latest cl
    join utm_source_latest us on us.source_id = cl.source_id
    where cl.campaign_id is not null
    group by cl.campaign_id, us.source_name
),
campaign_source as (
    select utm_campaign_id, source_name
    from campaign_source_counts
    qualify row_number() over (partition by utm_campaign_id order by lead_count desc) = 1
),
medium_latest as (
    select *
    from {{ ref('stg_utm_medium') }}
    where is_deleted = false
    qualify row_number() over (partition by utm_medium_id order by _cdc_ts_ms desc, _cdc_lsn desc) = 1
),
campaign_medium_counts as (
    select
        cl.campaign_id  as utm_campaign_id,
        um.name         as medium_name,
        count(*)        as lead_count
    from crm_lead_latest cl
    join medium_latest um on um.utm_medium_id = cl.medium_id
    where cl.campaign_id is not null
    group by cl.campaign_id, um.name
),
campaign_medium as (
    select utm_campaign_id, medium_name
    from campaign_medium_counts
    qualify row_number() over (partition by utm_campaign_id order by lead_count desc) = 1
)
select
    coalesce(cmm.campaign_id, uc.utm_campaign_id)         as campaign_id,
    uc.utm_campaign_id,
    coalesce(cmm.campaign_name, uc.name)                  as campaign_name,
    uc.title                                              as campaign_title,
    cs.source_name,
    cmed.medium_name,
    coalesce(cmm.status, case when uc.active then 'active' else 'inactive' end) as status,
    coalesce(uc.active, true)                             as active
from campaign_master_latest cmm
full outer join utm_campaign_latest uc
    on uc.utm_campaign_id = cmm.campaign_id
left join campaign_source cs   on cs.utm_campaign_id = uc.utm_campaign_id
left join campaign_medium cmed on cmed.utm_campaign_id = uc.utm_campaign_id
