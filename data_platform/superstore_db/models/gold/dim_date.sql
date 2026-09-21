{{ config(materialized='table') }}

-- Calendar dimension từ 2020 đến 10 năm sau ngày chạy, không có hard stop 2030.
with date_spine as (
    {{ dbt_utils.date_spine(
        datepart="day",
        start_date="'2020-01-01'::date",
        end_date="dateadd(year, 10, " ~ pipeline_today() ~ ")"
    ) }}
),
dates as (
    select date_day::date as date_actual
    from date_spine
)
select
    to_number(to_char(date_actual, 'YYYYMMDD'))    as date_key,
    date_actual,
    dayofweekiso(date_actual)                      as day_of_week,
    dayname(date_actual)                           as day_name,
    day(date_actual)                               as day_of_month,
    dayofyear(date_actual)                         as day_of_year,
    weekofyear(date_actual)                        as week_number,
    month(date_actual)                             as month,
    monthname(date_actual)                         as month_name,
    quarter(date_actual)                           as quarter,
    year(date_actual)                              as year,
    year(date_actual)                              as fiscal_year,
    quarter(date_actual)                           as fiscal_quarter,
    dayofweekiso(date_actual) in (6, 7)             as is_weekend,
    false                                           as is_holiday
from dates
