{% snapshot snap_hr_contract %}

{{
    config(
      target_database='SUPERSTORE_DB',
      target_schema='DBT_SNAPSHOTS',
      unique_key='contract_id',
      strategy='check',
      check_cols=['employee_id', 'wage', 'date_start', 'date_end', 'state', 'is_deleted'],
      invalidate_hard_deletes=True
    )
}}

-- dbt snapshot (SCD2), strategy=check.
-- Theo dõi cả employee_id/state để việc chuyển chủ hợp đồng hoặc đổi trạng thái không bị
-- bỏ qua chỉ vì wage và ngày hợp đồng không đổi.
-- key=contract_id. Wrap stg_hr_contract (naming_convention §1).
-- Order theo _cdc_ts_ms/_cdc_lsn (thứ tự sự kiện thật ở nguồn), KHÔNG theo ingested_at.
select * from {{ ref('stg_hr_contract') }}
qualify row_number() over (
    partition by contract_id order by _cdc_ts_ms desc, _cdc_lsn desc
) = 1

{% endsnapshot %}
