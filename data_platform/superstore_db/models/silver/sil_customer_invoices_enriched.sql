-- GRAIN   : 1 account_move khách hàng hiện hành (invoice/refund), kể cả tombstone.
-- SOURCE  : staging -> stg_account_move.
-- PURPOSE : nguồn đầy đủ cho AR Aging; khác payment allocation, model này vẫn giữ hóa đơn
--           chưa từng phát sinh thanh toán.
{{ config(
    materialized='incremental',
    incremental_strategy='merge',
    unique_key='move_id',
    on_schema_change='sync_all_columns'
) }}

with move_latest as (
    select *
    from {{ ref('stg_account_move') }}
    qualify row_number() over (
        partition by move_id
        order by _cdc_ts_ms desc, _cdc_lsn desc
    ) = 1
),

source_rows as (
    select
        move_id,
        name as invoice_number,
        date as accounting_date,
        invoice_date,
        invoice_date_due,
        partner_id,
        journal_id,
        campaign_id,
        currency_id,
        company_id,
        move_type,
        state as move_state,
        payment_state,
        amount_untaxed,
        amount_tax,
        amount_total,
        amount_residual,
        is_deleted,
        _cdc_ts_ms,
        _cdc_lsn,
        ingested_at,
        {{ dbt_utils.generate_surrogate_key([
            'move_id',
            '_cdc_ts_ms',
            '_cdc_lsn',
            'is_deleted'
        ]) }} as source_version_key
    from move_latest
    where move_type in ('out_invoice', 'out_refund')
),

changed_rows as (
    select src.*
    from source_rows src
    {% if is_incremental() %}
    left join {{ this }} tgt
        on tgt.move_id = src.move_id
    where tgt.move_id is null
       or coalesce(src.source_version_key, '__NULL__')
          <> coalesce(tgt.source_version_key, '__NULL__')
    {% endif %}
)

select
    src.*,
    {{ pipeline_now() }} as silver_updated_at
from changed_rows src
