{% snapshot snap_product_template %}

{{
    config(
      target_database='SUPERSTORE_DB',
      target_schema='DBT_SNAPSHOTS',
      unique_key='product_tmpl_id',
      strategy='check',
      check_cols=['list_price', 'write_date', 'is_deleted'],
      invalidate_hard_deletes=True
    )
}}

-- dbt snapshot (SCD2), strategy=check, check_cols=[list_price, write_date, is_deleted].
-- key=product_tmpl_id. Wrap stg_product_template (naming_convention §1).
-- Order theo _cdc_ts_ms/_cdc_lsn (thứ tự sự kiện thật ở nguồn), KHÔNG theo ingested_at.
select * from {{ ref('stg_product_template') }}
qualify row_number() over (
    partition by product_tmpl_id order by _cdc_ts_ms desc, _cdc_lsn desc
) = 1

{% endsnapshot %}
