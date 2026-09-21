-- GRAIN: 1 crm_lead hiện hành. CDC chỉ dùng phát hiện thay đổi.
-- silver_updated_at là thời điểm dòng thực sự được INSERT/UPDATE tại Silver;
-- date_open/date_closed vẫn là business time và không chọn SCD2 version.
{{ config(
    materialized='incremental',
    incremental_strategy='merge',
    unique_key='crm_lead_id',
    on_schema_change='sync_all_columns',
    full_refresh=false
) }}

with lead_latest as (
    select *
    from {{ ref('stg_crm_lead') }}
    qualify row_number() over (
        partition by crm_lead_id
        order by _cdc_ts_ms desc, _cdc_lsn desc
    ) = 1
),
source_rows as (
    select
        ld.*,
        {{ dbt_utils.generate_surrogate_key([
            'ld._cdc_ts_ms',
            'ld._cdc_lsn'
        ]) }} as source_version_key
    from lead_latest ld
),
changed_rows as (
    select src.*
    from source_rows src
    {% if is_incremental() %}
    left join {{ this }} tgt on tgt.crm_lead_id = src.crm_lead_id
    where tgt.crm_lead_id is null
       or coalesce(src.source_version_key, '__NULL__')
          <> coalesce(tgt.source_version_key, '__NULL__')
    {% endif %}
)

select
    src.*,
    {{ pipeline_now() }} as silver_updated_at
from changed_rows src
