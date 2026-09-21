-- GRAIN   : 1 campaign (static — không SCD2)
-- SOURCE  : silver → sil_campaign_enriched (merge utm_campaign + CSV marketing_campaigns_master)
-- DERIVED : n/a
-- TEST    : unique(campaign_sk), not_null(campaign_id), at_least_one_not_null(campaign_id, utm_campaign_id)
{{ config(materialized='table') }}
select
    {{ dbt_utils.generate_surrogate_key(['campaign_id']) }}  as campaign_sk,
    campaign_id,
    utm_campaign_id,
    campaign_name,
    campaign_title,
    source_name,
    medium_name,
    active,
    {{ pipeline_now() }}                as gold_refreshed_at
from {{ ref('sil_campaign_enriched') }}
