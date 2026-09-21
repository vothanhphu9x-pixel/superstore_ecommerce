{#
    Debezium (connector config: time.precision.mode mặc định = adaptive, JsonConverter với
    schemas.enable=false) không emit timestamp/date dạng ISO string — nó emit dạng số nguyên
    epoch theo semantic type gốc (io.debezium.time.MicroTimestamp / io.debezium.time.Date).
    Postgres TIMESTAMP (precision mặc định = 6) -> epoch MICROSECONDS.
    Postgres DATE -> epoch DAYS.
    Cast thẳng ::TIMESTAMP trên số này sẽ ra sai lệch — phải dùng 2 macro dưới.
#}

{% macro deb_ts(col) -%}
    TO_TIMESTAMP_NTZ({{ col }}::NUMBER, 6)
{%- endmacro %}

{% macro deb_date(col) -%}
    DATEADD(day, {{ col }}::NUMBER, '1970-01-01'::DATE)
{%- endmacro %}

{#
    Debezium serialize cột JSONB của Postgres thành CHUỖI JSON (io.debezium.data.Json —
    STRING schema), KHÔNG phải nested object. Field dịch đa ngôn ngữ của Odoo lưu dạng
    jsonb {"en_US": "..."}; field company-dependent (vd standard_price) lưu dạng
    jsonb {"1": 123.45} với key = company_id dạng string.
    -> Phải PARSE_JSON(...::STRING) trước khi navigate bằng colon-path.
#}

{% macro deb_jsonb_get(col, key) -%}
    PARSE_JSON({{ col }}::STRING):{{ key }}
{%- endmacro %}

{% macro deb_i18n(col, primary_lang='vi_VN', secondary_lang='en_US') -%}
    COALESCE(
        {{ deb_jsonb_get(col, primary_lang) }},
        {{ deb_jsonb_get(col, secondary_lang) }}
    )::STRING
{%- endmacro %}

{#
    _cdc_ts_ms = payload.source.ts_ms do consumer.py gắn thêm — epoch MILLISECONDS (không phải
    micros như các cột business timestamp qua deb_ts). Đây là thời điểm sự kiện xảy ra thật ở
    Postgres WAL, dùng để xác định "bản mới nhất" khi order/dedup CDC — KHÔNG dùng ingested_at
    cho việc này (ingested_at chỉ là lúc data land vào Snowflake, có thể trễ/replay/out-of-order).
#}
{% macro deb_cdc_ts(col='raw_data:_cdc_ts_ms') -%}
    TO_TIMESTAMP_NTZ({{ col }}::NUMBER, 3)
{%- endmacro %}