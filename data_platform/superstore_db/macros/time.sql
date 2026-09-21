{#
  Chuẩn thời gian duy nhất của pipeline:
  - Lưu giờ địa phương Việt Nam dưới dạng TIMESTAMP_NTZ.
  - Không phụ thuộc TIMEZONE của account/session Snowflake.
  - Snapshot, Silver, Gold và Mart phải dùng cùng macro này.
#}

{% macro pipeline_now() -%}
    to_timestamp_ntz(
        convert_timezone('Asia/Ho_Chi_Minh', current_timestamp())
    )
{%- endmacro %}

{% macro pipeline_today() -%}
    to_date(
        convert_timezone('Asia/Ho_Chi_Minh', current_timestamp())
    )
{%- endmacro %}

{#
  Override implementation Snowflake của dbt snapshot. Adapter dispatch ưu tiên macro
  trong project, nên dbt_valid_from/dbt_valid_to dùng cùng giờ Việt Nam với Silver/Gold.
#}
{% macro snowflake__snapshot_get_time() -%}
    {{ pipeline_now() }}
{%- endmacro %}
