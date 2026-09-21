-- Dữ liệu mô phỏng đã được chuẩn hóa: confirmed sale phải có channel phân tích.
select
    order_id
from {{ ref('fact_sales') }}
where order_state in ('sale', 'done')
  and is_deleted = false
  and coalesce(is_cancelled, false) = false
group by order_id
having count_if(channel_sk is null) > 0
