-- GRAIN: 1 account_move_line hiện hành.
-- CDC của line/header/account/journal chỉ dùng phát hiện thay đổi.
-- silver_updated_at chỉ đổi khi một source thực sự làm thay đổi Silver row.
-- am.date là business time, không dùng để chọn version SCD2.
{{ config(
    materialized='incremental',
    incremental_strategy='merge',
    unique_key='account_move_line_id',
    on_schema_change='sync_all_columns'
) }}

with line_latest as (
    select *
    from {{ ref('stg_account_move_line') }}
    qualify row_number() over (
        partition by account_move_line_id
        order by _cdc_ts_ms desc, _cdc_lsn desc
    ) = 1
),
move_latest as (
    select *
    from {{ ref('stg_account_move') }}
    qualify row_number() over (
        partition by move_id
        order by _cdc_ts_ms desc, _cdc_lsn desc
    ) = 1
),
account_latest as (
    select *
    from {{ ref('stg_account_account') }}
    qualify row_number() over (
        partition by account_id
        order by _cdc_ts_ms desc, _cdc_lsn desc
    ) = 1
),
journal_latest as (
    select *
    from {{ ref('stg_account_journal') }}
    qualify row_number() over (
        partition by journal_id
        order by _cdc_ts_ms desc, _cdc_lsn desc
    ) = 1
),
source_rows as (
    select
        aml.account_move_line_id,
        aml.move_id,
        aml.account_id,
        coalesce(aml.partner_id, am.partner_id) as partner_id,
        am.journal_id,
        am.date,
        am.move_type,
        am.state as move_state,
        am.name as ref,
        aml.debit,
        aml.credit,
        (coalesce(aml.is_deleted, false) or coalesce(am.is_deleted, false)) as is_deleted,
        acc.code as account_code,
        jr.code as journal_code,
        aml._cdc_ts_ms as line_cdc_ts_ms,
        aml._cdc_lsn as line_cdc_lsn,
        am._cdc_ts_ms as move_cdc_ts_ms,
        am._cdc_lsn as move_cdc_lsn,
        acc._cdc_ts_ms as account_cdc_ts_ms,
        acc._cdc_lsn as account_cdc_lsn,
        jr._cdc_ts_ms as journal_cdc_ts_ms,
        jr._cdc_lsn as journal_cdc_lsn,
        {{ dbt_utils.generate_surrogate_key([
            'aml._cdc_ts_ms',
            'aml._cdc_lsn',
            'aml.debit',
            'aml.credit',
            'am._cdc_ts_ms',
            'am._cdc_lsn',
            'acc._cdc_ts_ms',
            'acc._cdc_lsn',
            'jr._cdc_ts_ms',
            'jr._cdc_lsn'
        ]) }} as source_version_key
    from line_latest aml
    join move_latest am
        on am.move_id = aml.move_id
    left join account_latest acc
        on acc.account_id = aml.account_id
    left join journal_latest jr
        on jr.journal_id = am.journal_id
),
changed_rows as (
    select src.*
    from source_rows src
    {% if is_incremental() %}
    left join {{ this }} tgt
        on tgt.account_move_line_id = src.account_move_line_id
    where tgt.account_move_line_id is null
       or coalesce(src.source_version_key, '__NULL__')
          <> coalesce(tgt.source_version_key, '__NULL__')
    {% endif %}
)

select
    src.*,
    {{ pipeline_now() }} as silver_updated_at
from changed_rows src
