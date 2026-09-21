-- GRAIN   : 1 channel (static — không SCD2)
-- SOURCE  : silver → sil_channel_enriched
-- DERIVED : n/a
-- TEST    : unique(channel_sk), not_null(channel_code)
{{ config(materialized='table') }}
select
    {{ dbt_utils.generate_surrogate_key(['channel_code']) }} as channel_sk,
    channel_code,
    channel_name,
    medium_name,
    channel_group,
    active,
    {{ pipeline_now() }}                as gold_refreshed_at
from {{ ref('sil_channel_enriched') }}
