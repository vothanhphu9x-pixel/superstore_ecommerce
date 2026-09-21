-- 1:1 account.journal. GRAIN: 1 CDC event (append-only). SOURCE: bronze CDC topic odoo.account.journal
{{ config(
    materialized='incremental',
    incremental_strategy='append',
    on_schema_change='sync_all_columns'
) }}
select
    raw_data:id::number                    as journal_id,
    raw_data:code::string                  as code,
    {{ deb_i18n('raw_data:name') }}                  as name,  -- jsonb i18n: journal.name (translate=True)
    -- field thật tên 'type', KHÔNG phải 'journal_type' (domain-de.dbml note)
    raw_data:type::string                  as type,
    raw_data:cdc_status::string            as cdc_status,
    raw_data:is_deleted::boolean           as is_deleted,
    raw_data:_cdc_ts_ms::number            as _cdc_ts_ms,
    raw_data:_cdc_lsn::number              as _cdc_lsn,
    raw_data:ingested_at::timestamp_ntz    as ingested_at
from {{ source('bronze', 'account_journal') }}
{{ incremental_filter() }}
