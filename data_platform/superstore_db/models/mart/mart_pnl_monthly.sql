-- GRAIN  : 1 P&L report line x 1 accounting month.
-- SOURCE : fact_journal_entries + dim_account.
-- SIGN   : debit-normal = debit-credit; credit-normal = credit-debit.
-- REFRESH: full rebuild để journal correction/reclassification xóa được aggregate cũ.
{{ config(materialized='table') }}

with entries as (
    select
        fje.fact_je_sk,
        to_number(
            to_char(date_trunc('month', d.date_actual), 'YYYYMMDD')
        ) as month_date_key,
        coalesce(da.report_line, 'Unclassified') as report_line,
        fje.debit_amount,
        fje.credit_amount,
        case
            when coalesce(da.is_debit_normal, true)
                then fje.debit_amount - fje.credit_amount
            else fje.credit_amount - fje.debit_amount
        end as net_amount,
        da.account_sk is null as is_unclassified
    from {{ ref('fact_journal_entries') }} fje
    join {{ ref('dim_date') }} d
        on d.date_key = fje.entry_date_key
    left join {{ ref('dim_account') }} da
        on da.account_sk = fje.account_sk
    where fje.is_deleted = false
      and fje.move_state = 'posted'
      and (
          da.statement = 'income_statement'
          or da.account_sk is null
      )
),

monthly as (
    select
        report_line,
        month_date_key,
        min(fact_je_sk) as src_fact_je_sk,
        count(*) as journal_line_count,
        count_if(is_unclassified) as unclassified_line_count,
        sum(debit_amount) as debit_amount,
        sum(credit_amount) as credit_amount,
        sum(net_amount) as net_amount
    from entries
    group by report_line, month_date_key
)

select
    {{ dbt_utils.generate_surrogate_key([
        'monthly.report_line',
        'monthly.month_date_key'
    ]) }} as mart_pnl_sk,
    monthly.src_fact_je_sk,
    monthly.report_line,
    monthly.month_date_key,
    monthly.journal_line_count,
    monthly.unclassified_line_count,
    monthly.debit_amount,
    monthly.credit_amount,
    monthly.net_amount
from monthly
