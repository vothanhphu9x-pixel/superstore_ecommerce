{% snapshot snap_res_partner %}

{{
    config(
      target_database='SUPERSTORE_DB',
      target_schema='DBT_SNAPSHOTS',
      unique_key='partner_id',
      strategy='check',
      check_cols=['write_date', 'is_deleted'],
      invalidate_hard_deletes=True
    )
}}

-- dbt snapshot (SCD2), strategy=check, check_cols=[write_date, is_deleted]. key=partner_id.
-- Wrap stg_res_partner (naming_convention §1: snapshot chỉ wrap staging, không join).
-- stg_res_partner giờ là append-only (1 dòng/CDC event) — dbt snapshot yêu cầu đúng 1 dòng
-- /unique_key mỗi lần chạy, nên phải lấy bản mới nhất TẠI ĐÂY trước khi snapshot.
-- Order theo _cdc_ts_ms/_cdc_lsn (thứ tự sự kiện thật ở Postgres WAL), KHÔNG theo ingested_at
-- (chỉ là lúc data land vào Snowflake — CDC at-least-once có thể replay/out-of-order).
-- invalidate_hard_deletes=True: nếu partner_id biến mất khỏi kết quả select này (hard delete
-- thật ở nguồn, không phải soft-delete active=false), dbt tự đóng dbt_valid_to thay vì để
-- bản ghi "sống hoài" trong dim.
select * from {{ ref('stg_res_partner') }}
qualify row_number() over (
    partition by partner_id order by _cdc_ts_ms desc, _cdc_lsn desc
) = 1

{% endsnapshot %}
