-- GRAIN: 1 work center hiện hành. SOURCE: stg_mrp_workcenter (static, no snapshot, không qua
-- silver — đọc thẳng staging nên tự dedup "bản mới nhất" + lọc is_deleted tại đây).
-- TEST: unique(workcenter_sk), not_null(workcenter_code)
-- unique_key=workcenter_id (natural key). Bảng nhỏ — không cần incremental filter watermark.
{{ config(materialized='table') }}

with workcenter_latest as (
    -- Order theo _cdc_ts_ms/_cdc_lsn (thứ tự sự kiện thật ở nguồn), KHÔNG theo ingested_at.
    select *
    from {{ ref('stg_mrp_workcenter') }}
    qualify row_number() over (partition by workcenter_id order by _cdc_ts_ms desc, _cdc_lsn desc) = 1
)
select
    {{ dbt_utils.generate_surrogate_key(['workcenter_id']) }} as workcenter_sk,
    workcenter_id,
    code                                as workcenter_code,
    name                                as workcenter_name,
    default_capacity,
    time_efficiency,
    (coalesce(active, true) and is_deleted = false) as active,
    {{ pipeline_now() }}                as gold_refreshed_at
from workcenter_latest
