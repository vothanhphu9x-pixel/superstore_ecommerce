-- Chỉ posted moves là sổ kế toán chính thức. Cho phép sai số 0.01 do monetary rounding.
select
    move_id,
    sum(debit_amount) as debit_amount,
    sum(credit_amount) as credit_amount,
    sum(debit_amount) - sum(credit_amount) as difference_amount
from {{ ref('fact_journal_entries') }}
where is_deleted = false
  and move_state = 'posted'
group by move_id
having abs(sum(debit_amount) - sum(credit_amount)) > 0.01
