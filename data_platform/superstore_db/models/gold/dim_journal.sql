-- GRAIN: 1 sổ nhật ký kế toán hiện hành. SOURCE: stg_account_journal (không silver — dùng staging
-- trực tiếp, domain-de.dbml FINANCE_GENERAL_LEDGER). Domain-specific dim (KHÔNG conformed) —
-- dùng bởi fact_journal_entries, fact_payment_allocation.
-- TEST: unique(journal_sk), unique(journal_code)
{{ config(materialized='table') }}

with journal_latest as (
    select *
    from {{ ref('stg_account_journal') }}
    qualify row_number() over (partition by journal_id order by _cdc_ts_ms desc, _cdc_lsn desc) = 1
)
select
    {{ dbt_utils.generate_surrogate_key(['code']) }} as journal_sk,
    code                                as journal_code,
    name                                as journal_name,
    type                                as journal_type,
    (is_deleted = false)                as active,
    {{ pipeline_now() }}                as gold_refreshed_at
from journal_latest
