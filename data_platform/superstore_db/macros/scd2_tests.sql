{% test scd2_at_most_one_open(model, business_key, valid_to='dbt_valid_to') %}

select {{ business_key }}
from {{ model }}
where {{ valid_to }} is null
  and {{ business_key }} is not null
group by {{ business_key }}
having count(*) > 1

{% endtest %}

{% test scd2_at_most_one_current(model, business_key, current_column='is_current') %}

select {{ business_key }}
from {{ model }}
where {{ current_column }} = true
  and {{ business_key }} is not null
group by {{ business_key }}
having count(*) > 1

{% endtest %}

{% test scd2_no_overlaps(
    model,
    business_key,
    valid_from='dbt_valid_from',
    valid_to='dbt_valid_to'
) %}

with intervals as (
    select
        {{ business_key }} as business_key,
        {{ valid_from }} as valid_from,
        max(coalesce({{ valid_to }}, '9999-12-31'::timestamp)) over (
            partition by {{ business_key }}
            order by {{ valid_from }}, coalesce({{ valid_to }}, '9999-12-31'::timestamp)
            rows between unbounded preceding and 1 preceding
        ) as previous_max_valid_to
    from {{ model }}
    where {{ business_key }} is not null
      and {{ valid_from }} is not null
)

select *
from intervals
where valid_from < previous_max_valid_to

{% endtest %}

{% test scd2_valid_interval(
    model,
    valid_from='dbt_valid_from',
    valid_to='dbt_valid_to'
) %}

select *
from {{ model }}
where {{ valid_to }} is not null
  and {{ valid_to }} <= {{ valid_from }}

{% endtest %}
