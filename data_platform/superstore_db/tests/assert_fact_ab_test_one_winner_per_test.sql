-- Test source đã kết thúc: mỗi test phải có đúng một winning variant.
select
    test_id
from {{ ref('fact_ab_test') }}
group by test_id
having count_if(is_winner) <> 1
