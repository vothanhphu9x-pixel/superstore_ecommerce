-- GRAIN: 1 channel (static — không SCD2). Nguồn chính: explode cột channels của campaign
-- master. Bổ sung direct/organic/referral từ UTM medium để đơn không có paid campaign vẫn
-- có attribution trung thực và không bị dồn vào NULL.
-- utm_medium mặc định của Odoo (VD "Email", "Google Adwords") không khớp channel_code
-- snake_case của CSV. superstore_data_generator.py tạo/bổ sung các code chuẩn qua ORM;
-- lower(name) bảo vệ riêng trường hợp medium mặc định "Direct" dùng title case.
-- channel_group là business classification tự derive (Paid/Organic/Email theo tiền tố
-- channel_code), KHÔNG phải field nguồn nào — cần xác nhận với BA trước khi dùng production.
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
),
medium_latest as (
    select *
    from {{ ref('stg_utm_medium') }}
    where is_deleted = false
    qualify row_number() over (partition by utm_medium_id order by _cdc_ts_ms desc, _cdc_lsn desc) = 1
),
channel_codes as (
    select distinct trim(f.value::string) as channel_code
    from campaign_master_latest m,
         table(split_to_table(m.channels, '|')) f
    where m.channels is not null

    union

    select lower(name) as channel_code
    from medium_latest
    where lower(name) in ('direct', 'organic', 'referral')
)
select
    cc.channel_code,
    initcap(replace(cc.channel_code, '_', ' ')) as channel_name,
    um.name                                     as medium_name,
    case
        when cc.channel_code = 'email_marketing' then 'Email'
        when cc.channel_code like 'google_%' or cc.channel_code like 'meta_%' then 'Paid'
        else 'Organic'
    end                                          as channel_group,
    true                                         as active
from channel_codes cc
left join medium_latest um on lower(um.name) = cc.channel_code
