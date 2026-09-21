-- GRAIN: 1 warehouse hiện hành. SOURCE: stg_stock_warehouse (static, no snapshot, không qua
-- silver — đọc thẳng staging nên tự dedup "bản mới nhất" + lọc is_deleted tại đây).
-- TEST: unique(warehouse_sk), not_null(warehouse_code)
-- ⚠️ city/state/region CHƯA XÁC NHẬN: stock.warehouse không có các cột này trực tiếp trên
-- Odoo core — dùng mapping tĩnh cố định cho 4 kho Superstore (WEST/EAST/CNTL/SOUT), cần xác
-- nhận với ETL gốc nếu số lượng/tên kho thay đổi.
-- unique_key=warehouse_id (natural key). Bảng nhỏ (4 kho) — không cần incremental filter
-- watermark, merge lại toàn bộ staging mỗi lần chạy vẫn rẻ và đơn giản/an toàn hơn.
{{ config(materialized='table') }}

with warehouse_latest as (
    -- Order theo _cdc_ts_ms/_cdc_lsn (thứ tự sự kiện thật ở nguồn), KHÔNG theo ingested_at.
    select *
    from {{ ref('stg_stock_warehouse') }}
    qualify row_number() over (partition by warehouse_id order by _cdc_ts_ms desc, _cdc_lsn desc) = 1
)
select
    {{ dbt_utils.generate_surrogate_key(['warehouse_id']) }}  as warehouse_sk,
    warehouse_id,
    code                                as warehouse_code,
    name                                as warehouse_name,
    case code
        when 'WEST' then 'Los Angeles'
        when 'EAST' then 'Newark'
        when 'CNTL' then 'Chicago'
        when 'SOUT' then 'Houston'
        else null
    end                                 as city,
    case code
        when 'WEST' then 'CA'
        when 'EAST' then 'NJ'
        when 'CNTL' then 'IL'
        when 'SOUT' then 'TX'
        else null
    end                                 as state,
    case code
        when 'WEST' then 'West'
        when 'EAST' then 'East'
        when 'CNTL' then 'Central'
        when 'SOUT' then 'South'
        else 'Unknown'
    end                                 as region,
    (coalesce(active, true) and is_deleted = false) as active,
    {{ pipeline_now() }}                as gold_refreshed_at
from warehouse_latest
