with expected as (
    select
        coalesce(da.report_line, 'Unclassified') as report_line,
        to_number(
            to_char(date_trunc('month', d.date_actual), 'YYYYMMDD')
        ) as month_date_key,
        sum(
            case
                when coalesce(da.is_debit_normal, true)
                    then fje.debit_amount - fje.credit_amount
                else fje.credit_amount - fje.debit_amount
            end
        ) as net_amount
    from {{ ref('fact_journal_entries') }} fje
    join {{ ref('dim_date') }} d
        on d.date_key = fje.entry_date_key
    left join {{ ref('dim_account') }} da
        on da.account_sk = fje.account_sk
    where fje.is_deleted = false
      and fje.move_state = 'posted'
      and (da.statement = 'income_statement' or da.account_sk is null)
    group by report_line, month_date_key
)

select
    coalesce(actual.report_line, expected.report_line) as report_line,
    coalesce(actual.month_date_key, expected.month_date_key) as month_date_key
from {{ ref('mart_pnl_monthly') }} actual
full outer join expected
    on expected.report_line = actual.report_line
   and expected.month_date_key = actual.month_date_key
where actual.report_line is null
   or expected.report_line is null
   or abs(actual.net_amount - expected.net_amount) > 0.01
